"""Unit tests for GraphSerializer."""

from __future__ import annotations

from pathlib import Path
import pytest
import networkx as nx

from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.serializer import GraphSerializer

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


class TestGraphSerializer:
    """Tests for GraphSerializer serialization and deserialization."""

    def test_to_json_and_from_json(self, graph):
        data = GraphSerializer.to_json(graph)
        assert isinstance(data, dict)
        assert "directed" in data
        assert "nodes" in data
        assert "links" in data

        reconstructed = GraphSerializer.from_json(data)
        assert isinstance(reconstructed, nx.MultiDiGraph)
        assert reconstructed.number_of_nodes() == graph.number_of_nodes()
        assert reconstructed.number_of_edges() == graph.number_of_edges()

    def test_to_json_string_and_from_json_string(self, graph):
        json_str = GraphSerializer.to_json_string(graph)
        assert isinstance(json_str, str)

        reconstructed = GraphSerializer.from_json_string(json_str)
        assert reconstructed.number_of_nodes() == graph.number_of_nodes()
        assert reconstructed.number_of_edges() == graph.number_of_edges()

    def test_save_to_file_and_load_from_file(self, graph, tmp_path):
        out_file = tmp_path / "test_graph.json"
        GraphSerializer.save_to_file(graph, str(out_file))
        assert out_file.exists()

        reconstructed = GraphSerializer.load_from_file(str(out_file))
        assert reconstructed.number_of_nodes() == graph.number_of_nodes()
        assert reconstructed.number_of_edges() == graph.number_of_edges()

    def test_to_cytoscape_json(self, graph):
        cyto = GraphSerializer.to_cytoscape_json(graph)
        assert isinstance(cyto, dict)
        assert "nodes" in cyto
        assert "edges" in cyto
        assert len(cyto["nodes"]) == graph.number_of_nodes()
        assert len(cyto["edges"]) == graph.number_of_edges()

        first_node = cyto["nodes"][0]
        assert "data" in first_node
        assert "id" in first_node["data"]

        if cyto["edges"]:
            first_edge = cyto["edges"][0]
            assert "data" in first_edge
            assert "source" in first_edge["data"]
            assert "target" in first_edge["data"]

    def test_get_summary(self, graph):
        summary = GraphSerializer.get_summary(graph)
        assert summary["node_count"] == graph.number_of_nodes()
        assert summary["edge_count"] == graph.number_of_edges()
        assert summary["is_directed"] is True
        assert summary["is_multigraph"] is True
        assert "file" in summary["node_types"]
        assert "CONTAINS" in summary["edge_types"]
