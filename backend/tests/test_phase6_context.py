"""Tests for Phase 6.3 — Verified Context Builder."""

import pytest

from app.llm.context import VerifiedContextBuilder
from app.llm.schemas import LLMContext
from tests.conftest import write_artifacts


@pytest.fixture
def builder(context_builder):
    return context_builder


class TestParsing:
    def test_repository_name_from_analysis(self, builder):
        assert builder.repository_name == "sample_repo"

    def test_files_by_path_indexed(self, builder):
        assert "app/main.py" in builder._parsed_artifacts["analysis"]["files_by_path"]

    def test_graph_nodes_and_links_parsed(self, builder):
        graph = builder._parsed_artifacts["graph"]
        assert "module:app" in graph["nodes_by_id"]
        assert graph["links"] == [
            {"source": "module:app.main", "target": "module:app", "key": 0, "type": "IMPORTS"}
        ]

    def test_health_risks_by_id_and_component(self, builder):
        health = builder._parsed_artifacts["health"]
        assert "high_coupling:module:app.main" in health["risks_by_id"]
        assert len(health["risks"]) == 1
        assert "module:app.main" in health["risks_by_component"]

    def test_evolution_opportunities_by_id_and_component(self, builder):
        evolution = builder._parsed_artifacts["evolution"]
        assert "reduce_coupling:module:app.main" in evolution["opportunities_by_id"]
        assert evolution["opportunities"][0]["type"] == "reduce_coupling"
        assert "module:app.main" in evolution["opportunities_by_component"]

    def test_architecture_components_by_id(self, builder):
        architecture = builder._parsed_artifacts["architecture"]
        assert "module:app.main" in architecture["components_by_id"]
        assert architecture["patterns"][0]["name"] == "layered"


class TestRepositoryContext:
    def test_repository_context_shape(self, builder):
        ctx = builder.build_repository_context()
        assert isinstance(ctx, LLMContext)
        assert ctx.repository_name == "sample_repo"
        cc = ctx.custom_context
        assert cc.get("repository") == "sample_repo"
        assert cc.get("component_count") == 1
        assert cc.get("file_count") == 1
        assert cc.get("risk_count") == 1
        assert cc.get("confidence") == "verified"

    def test_repository_context_has_top_risks(self, builder):
        ctx = builder.build_repository_context()
        assert ctx.custom_context["top_risks"][0]["type"] == "high_coupling"

    def test_repository_context_has_patterns(self, builder):
        ctx = builder.build_repository_context()
        assert "layered" in ctx.custom_context["patterns"]

    def test_repository_context_passes_raw_artifacts(self, builder):
        ctx = builder.build_repository_context()
        assert ctx.analysis_data is not None
        assert ctx.graph_data is not None
        assert ctx.architecture_data is not None
        assert ctx.health_data is not None
        assert ctx.evolution_data is not None


class TestComponentContext:
    def test_component_context_basic(self, builder):
        ctx = builder.build_component_context("module:app.main")
        cc = ctx.custom_context
        assert cc["component_id"] == "module:app.main"
        assert cc["role"] == "entry_point"
        assert cc["layer"] == "presentation"
        assert isinstance(cc["dependencies"], list)
        assert isinstance(cc["route_count"], int)

    def test_component_context_unknown_component_does_not_raise(self, builder):
        # Component context is resilient for unknown ids (the LLM is told to
        # flag the gap); only missing TARGETS raise.
        ctx = builder.build_component_context("module:nope")
        assert ctx.custom_context["component_id"] == "module:nope"
        assert ctx.custom_context.get("component_info") is None


class TestDependencyContext:
    def test_dependency_context(self, builder):
        ctx = builder.build_dependency_context("module:app.main", "module:app")
        cc = ctx.custom_context
        assert cc["source_component"] == "module:app.main"
        assert cc["target_component"] == "module:app"
        assert cc["edge_count"] >= 1
        assert cc["relationship_types"] == ["IMPORTS"]
        assert cc["confidence"] == "verified"

    def test_dependency_context_edges_available(self, builder):
        ctx = builder.build_dependency_context("module:app.main", "module:app")
        assert ctx.graph_data["links"][0]["source"] == "module:app.main"

    def test_dependency_context_missing_relationship_raises(self, builder):
        with pytest.raises(ValueError):
            builder.build_dependency_context("module:app", "module:nope")


class TestRiskContext:
    def test_risk_context(self, builder):
        ctx = builder.build_risk_context("high_coupling:module:app.main")
        cc = ctx.custom_context
        assert cc["risk_type"] == "high_coupling"
        assert cc["severity"] == "high"
        assert cc["affected_component"] == "module:app.main"
        assert ctx.health_data["risks"][0]["id"].startswith("high_coupling")

    def test_risk_context_unknown_raises(self, builder):
        with pytest.raises(ValueError):
            builder.build_risk_context("unknown:risk")


class TestRecommendationContext:
    def test_recommendation_context(self, builder):
        ctx = builder.build_recommendation_context("reduce_coupling:module:app.main")
        cc = ctx.custom_context
        assert cc["recommendation_type"] == "reduce_coupling"
        assert cc["affected_component"] == "module:app.main"
        assert cc["priority"] == "high"
        assert ss_of(ctx.health_data)  # health_data keyed as {"risks": [...]}
        assert ctx.evolution_data["refactoring_opportunities"][0]["type"] == "reduce_coupling"

    def test_recommendation_unknown_raises(self, builder):
        with pytest.raises(ValueError):
            builder.build_recommendation_context("unknown:rec")


class TestImpactContext:
    def test_impact_context(self, builder):
        ctx = builder.build_impact_context("module:app.main")
        cc = ctx.custom_context
        assert "impact_level" in cc
        assert "directly_affected_components" in cc
        assert "depends_on" in cc
        assert "total_impact_count" in cc
        assert cc["confidence"] == "verified"


class TestDispatchAndBudget:
    def test_select_component_requires_target(self, builder):
        with pytest.raises(ValueError):
            builder.select_context_for_operation("component_explanation", None, None)

    def test_select_architecture_default(self, builder):
        ctx = builder.select_context_for_operation("architecture_explanation", None, None)
        assert ctx.repository_name == "sample_repo"

    def test_select_risk_requires_target(self, builder):
        with pytest.raises(ValueError):
            builder.select_context_for_operation("risk_explanation", None, None)

    def test_select_recommendation_requires_target(self, builder):
        with pytest.raises(ValueError):
            builder.select_context_for_operation("recommendation_explanation", None, None)

    def test_select_dependency_requires_separator(self, builder):
        with pytest.raises(ValueError):
            builder.select_context_for_operation("dependency_explanation", "module:app.main", None)

    def test_select_dependency_parses_source_target(self, builder):
        ctx = builder.select_context_for_operation(
            "dependency_explanation", "module:app.main||module:app", None
        )
        cc = ctx.custom_context
        assert (cc["source_component"], cc["target_component"]) == ("module:app.main", "module:app")

    def test_component_target_prefix_stripped(self, builder):
        ctx = builder.select_context_for_operation(
            "component_explanation", "component:module:app.main", None
        )
        assert ctx.custom_context["component_id"] == "module:app.main"

    def test_context_in_budget(self, builder):
        ctx = builder.build_repository_context()
        assert builder.context_in_budget(ctx) is True

    def test_default_max_tokens_is_cap_not_target(self, builder):
        assert VerifiedContextBuilder.DEFAULT_MAX_TOKENS == 100_000

    def test_validate_context_completeness(self, builder):
        ctx = builder.build_repository_context()
        warnings = builder.validate_context_completeness(ctx)
        assert isinstance(warnings, list)


class TestFromArtifactsDir:
    def test_from_artifacts_dir_roundtrip(self, tmp_path):
        write_artifacts(tmp_path)
        builder = VerifiedContextBuilder.from_artifacts_dir(tmp_path)
        assert builder.repository_name == "sample_repo"
        assert builder._parsed_artifacts["health"]["risks_by_id"]

    def test_from_artifacts_dir_accepts_path_str(self, tmp_path):
        write_artifacts(str(tmp_path))
        builder = VerifiedContextBuilder.from_artifacts_dir(str(tmp_path))
        assert builder.repository_name == "sample_repo"

    def test_from_artifacts_dir_missing_file_raises(self, tmp_path):
        # Write only analysis.json — everything else missing.
        write_artifacts(tmp_path)
        (tmp_path / "graph.json").unlink()
        with pytest.raises(FileNotFoundError):
            VerifiedContextBuilder.from_artifacts_dir(tmp_path)


def ss_of(health_data) -> bool:
    """True when health_data is a {"risks": [...]} mapping (not the raw form)."""
    return isinstance(health_data, dict) and "risks" in health_data and len(health_data.get("risks", [])) >= 0