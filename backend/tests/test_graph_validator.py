"""Unit tests for GraphValidator."""

from __future__ import annotations

from pathlib import Path
import pytest
import networkx as nx

from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.graph_validator import GraphValidator, ValidationResult

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
EXAMPLE_PROJECT = PROJECT_ROOT / "examples" / "fastapi_project"


@pytest.fixture(scope="module")
def analysis():
    analyzer = RepositoryAnalyzer(str(EXAMPLE_PROJECT))
    return analyzer.analyze()


@pytest.fixture(scope="module")
def graph(analysis):
    builder = GraphBuilder(analysis)
    return builder.build()


class TestGraphValidatorValidGraph:
    """Tests for validating a correct graph."""

    def test_validation_passes(self, graph):
        validator = GraphValidator(graph)
        result = validator.validate()
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_get_node_statistics(self, graph):
        validator = GraphValidator(graph)
        node_stats = validator.get_node_statistics()
        assert isinstance(node_stats, dict)
        assert node_stats.get("file", 0) > 0
        assert node_stats.get("module", 0) > 0

    def test_get_edge_statistics(self, graph):
        validator = GraphValidator(graph)
        edge_stats = validator.get_edge_statistics()
        assert isinstance(edge_stats, dict)
        assert edge_stats.get("CONTAINS", 0) > 0
        assert edge_stats.get("IMPORTS", 0) > 0


class TestGraphValidatorInvalidGraph:
    """Tests for detecting errors in invalid graphs."""

    def test_missing_node_type(self):
        g = nx.MultiDiGraph()
        g.add_node("node1")  # No 'type' attribute
        validator = GraphValidator(g)
        res = validator.validate()
        assert res.is_valid is False
        assert any("missing 'type' attribute" in err for err in res.errors)

    def test_invalid_node_type(self):
        g = nx.MultiDiGraph()
        g.add_node("node1", type="invalid_type")
        validator = GraphValidator(g)
        res = validator.validate()
        assert res.is_valid is False
        assert any("invalid type 'invalid_type'" in err for err in res.errors)

    def test_self_loop_detection(self):
        g = nx.MultiDiGraph()
        g.add_node("module:a", type="module", path="a.py")
        g.add_edge("module:a", "module:a", type="IMPORTS")
        validator = GraphValidator(g)
        res = validator.validate()
        assert res.is_valid is False
        assert any("has self-loop(s)" in err for err in res.errors)

    def test_missing_edge_type(self):
        g = nx.MultiDiGraph()
        g.add_node("module:a", type="module", path="a.py")
        g.add_node("module:b", type="module", path="b.py")
        g.add_edge("module:a", "module:b")  # missing 'type'
        validator = GraphValidator(g)
        res = validator.validate()
        assert res.is_valid is False
        assert any("missing 'type' attribute" in err for err in res.errors)
