"""Tests for Phase 6.5 — Grounding Guardrails."""

from types import SimpleNamespace

import pytest

from app.llm.context import VerifiedContextBuilder
from app.llm.guardrails import GroundingGuardrails, ValidationResult
from app.llm.service import LLMOperation


def _bare_dependency_builder():
    """A context builder whose graph uses bare identifiers so the dependency
    regex heuristics can actually resolve them (module ids contain ':' which the
    heuristic token regex cannot parse)."""
    from tests.conftest import make_artifacts

    a, g, arch, h, e = make_artifacts()
    g["links"] = [{"source": "main", "target": "app", "key": 0, "type": "IMPORTS"}]
    arch["components"] = [
        {"id": "main", "name": "main", "path": "app/main.py", "role": "entry_point",
         "layer": "presentation", "confidence": 0.9},
        {"id": "app", "name": "app", "path": "app/__init__.py", "role": "module",
         "layer": "presentation", "confidence": 0.9},
    ]
    return VerifiedContextBuilder(a, g, arch, h, e)


@pytest.fixture
def g(context_builder):
    return GroundingGuardrails(context_builder)


class TestArtifactLoading:
    def test_known_components_loaded(self, g):
        assert "module:app.main" in g.known_components
        assert "main" in g.known_components

    def test_known_files_loaded(self, g):
        assert "app/main.py" in g.known_files

    def test_known_dependencies_loaded(self, g):
        assert ("module:app.main", "module:app") in g.known_dependencies

    def test_known_roles_and_layers(self, g):
        assert "entry_point" in g.known_roles
        assert "presentation" in g.known_layers

    def test_known_risks_and_recommendations(self, g):
        assert "high_coupling" in g.known_risks
        assert "reduce_coupling" in g.known_recommendations

    def test_no_artifacts_guardrails(self):
        empty = GroundingGuardrails(None)
        assert empty.known_components == set()


class TestValidateRepositoryFacts:
    def test_empty_content_is_not_grounding_failure(self, g):
        result = g.validate_repository_facts("")
        assert result.is_valid
        assert "empty" in result.flags

    def test_known_content_is_valid(self, g):
        result = g.validate_repository_facts("Everything lives in app/main.py")
        assert result.is_valid
        assert result.message == "LLM output is grounded in verified artifacts"

    def test_unknown_component_flagged(self, g):
        result = g.validate_repository_facts("The mystery_service now handles auth.")
        assert not result.is_valid
        assert "unknown_component" in result.flags
        assert "mystery_service" in result.evidence["unknown_components"]

    def test_unknown_file_flagged(self, g):
        result = g.validate_repository_facts("Config is loaded from app/ghost.py")
        assert not result.is_valid
        assert "unknown_file" in result.flags

    def test_unknown_role_flagged(self, g):
        result = g.validate_repository_facts("A controller coordinates the flow")
        assert not result.is_valid
        assert "unknown_role" in result.flags

    def test_empty_artifacts_returns_no_artifacts_error(self):
        empty = GroundingGuardrails(None)
        result = empty.validate_repository_facts("anything at all")
        assert not result.is_valid
        assert "no_artifacts" in result.flags

    def test_unknown_dependency_flagged(self):
        guardrails = GroundingGuardrails(_bare_dependency_builder())
        result = guardrails.validate_repository_facts("main imports ghost")
        assert not result.is_valid
        assert "unknown_dependency" in result.flags

    def test_known_dependency_not_flagged(self):
        guardrails = GroundingGuardrails(_bare_dependency_builder())
        result = guardrails.validate_repository_facts("main imports app")
        assert result.is_valid
        assert "unknown_dependency" not in result.flags

    def test_suggested_fix_present_on_failure(self, g):
        result = g.validate_repository_facts("The mystery_service thing")
        assert result.suggested_fix
        assert "Do not invent" in result.suggested_fix


class TestValidateNoSecrets:
    def test_sk_secret_flagged(self, g):
        result = g.validate_no_secrets_or_pii("my key sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456")
        assert not result.is_valid
        assert "secret" in result.flags

    def test_aws_access_key_flagged(self, g):
        result = g.validate_no_secrets_or_pii("AKIAIOSFODNN7EXAMPLE")
        assert not result.is_valid
        assert "secret" in result.flags

    def test_pem_private_key_flagged(self, g):
        result = g.validate_no_secrets_or_pii("-----BEGIN RSA PRIVATE KEY-----")
        assert not result.is_valid
        assert "secret" in result.flags

    def test_email_flagged_as_pii(self, g):
        result = g.validate_no_secrets_or_pii("contact me at someone@example.com")
        assert not result.is_valid
        assert "pii" in result.flags

    def test_clean_content_valid(self, g):
        result = g.validate_no_secrets_or_pii("This response contains no credentials.")
        assert result.is_valid


class TestValidateResponseStructure:
    def _op(self):
        return LLMOperation.RISK_EXPLANATION

    def test_complete_response_valid(self, g):
        response = SimpleNamespace(content="Some analysis text.", metadata={"provider": "mock"})
        result = g.validate_response_structure(response, self._op())
        assert result.is_valid

    def test_empty_content_flagged(self, g):
        response = SimpleNamespace(content="   ", metadata={"provider": "mock"})
        result = g.validate_response_structure(response, self._op())
        assert not result.is_valid
        assert "structure" in result.flags

    def test_missing_metadata_flagged(self, g):
        response = SimpleNamespace(content="Text", metadata=None)
        result = g.validate_response_structure(response, self._op())
        assert not result.is_valid


class TestExtraction:
    def test_extract_component_candidates(self, g):
        candidates = g.extract_component_candidates("hello_world and foo_bar")
        assert "hello_world" in candidates
        assert "foo_bar" in candidates

    def test_extract_dependency_candidates_sentence(self, g):
        deps = g.extract_dependency_candidates("service depends on database")
        assert ("service", "database") in deps

    def test_extract_dependency_candidates_arrow(self, g):
        deps = g.extract_dependency_candidates("a -> b")
        assert ("a", "b") in deps

    def test_extract_file_candidates(self, g):
        files = g.extract_file_candidates("see app/main.py and utils/helpers.py")
        assert "app/main.py" in files
        assert "utils/helpers.py" in files

    def test_extract_role_candidates(self, g):
        roles = g.extract_role_candidates("the service and a controller")
        assert "controller" in [r.lower() for r in roles]


class TestValidationResultShape:
    def test_validation_result_defaults(self):
        result = ValidationResult(is_valid=True, message="ok")
        assert result.evidence is None
        assert result.suggested_fix is None
        assert result.flags == []