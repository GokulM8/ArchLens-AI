"""Unit tests for GraphMetrics."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.metrics import GraphMetrics

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


class TestGraphMetrics:
    """Tests for GraphMetrics computation."""

    def test_compute_all(self, graph):
        metrics_calculator = GraphMetrics(graph)
        all_metrics = metrics_calculator.compute_all()

        assert isinstance(all_metrics, dict)
        assert "total_nodes" in all_metrics
        assert "total_edges" in all_metrics
        assert "node_types" in all_metrics
        assert "edge_types" in all_metrics
        assert "density" in all_metrics
        assert "total_routes" in all_metrics
        assert "total_external_dependencies" in all_metrics

    def test_basic_metrics(self, graph):
        metrics_calculator = GraphMetrics(graph)
        basic = metrics_calculator._compute_basic_metrics()

        assert basic["total_nodes"] == graph.number_of_nodes()
        assert basic["total_edges"] == graph.number_of_edges()
        assert "file" in basic["node_types"]
        assert "CONTAINS" in basic["edge_types"]

    def test_connectivity_metrics(self, graph):
        metrics_calculator = GraphMetrics(graph)
        conn = metrics_calculator._compute_connectivity_metrics()

        assert conn["connected_components"] >= 1
        assert conn["weakly_connected_components"] >= 1
        assert isinstance(conn["density"], float)

    def test_cycle_metrics(self, graph):
        metrics_calculator = GraphMetrics(graph)
        cycles = metrics_calculator._compute_cycle_metrics()

        assert "strongly_connected_components" in cycles
        assert "cycles_found" in cycles

    def test_centrality_metrics(self, graph):
        metrics_calculator = GraphMetrics(graph)
        cent = metrics_calculator._compute_centrality_metrics()

        assert "avg_in_degree_centrality" in cent
        assert "avg_out_degree_centrality" in cent

    def test_code_specific_metrics(self, graph):
        metrics_calculator = GraphMetrics(graph)
        code_m = metrics_calculator._compute_code_specific_metrics()

        assert 0.0 <= code_m["internal_import_ratio"] <= 1.0
        assert 0.0 <= code_m["external_import_ratio"] <= 1.0
        assert code_m["total_routes"] > 0
        assert code_m["total_external_dependencies"] > 0
