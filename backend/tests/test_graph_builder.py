"""Unit and integration tests for GraphBuilder."""

from __future__ import annotations

from pathlib import Path
import pytest
import networkx as nx

from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
EXAMPLE_PROJECT = PROJECT_ROOT / "examples" / "fastapi_project"


@pytest.fixture(scope="module")
def analysis():
    """Analyze the example project once for graph builder tests."""
    analyzer = RepositoryAnalyzer(str(EXAMPLE_PROJECT))
    return analyzer.analyze()


@pytest.fixture(scope="module")
def graph(analysis):
    """Build the NetworkX graph from analysis results."""
    builder = GraphBuilder(analysis)
    return builder.build()


class TestGraphBuilderNodes:
    """Tests for node generation in GraphBuilder."""

    def test_returns_multidigraph(self, graph):
        assert isinstance(graph, nx.MultiDiGraph)

    def test_repository_node_exists(self, graph, analysis):
        repo_id = f"repository:{analysis.repository.name}"
        assert graph.has_node(repo_id)
        node_data = graph.nodes[repo_id]
        assert node_data["type"] == "repository"
        assert node_data["label"] == analysis.repository.name

    def test_directory_nodes(self, graph):
        dir_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "directory"]
        assert len(dir_nodes) > 0
        assert "directory:app" in graph
        assert "directory:app/routes" in graph

    def test_file_nodes(self, graph):
        file_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "file"]
        assert len(file_nodes) > 0
        assert "file:app/main.py" in graph
        node_data = graph.nodes["file:app/main.py"]
        assert node_data["path"] == "app/main.py"

    def test_module_nodes(self, graph):
        module_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "module"]
        assert len(module_nodes) > 0
        assert "module:app.main" in graph

    def test_class_nodes(self, graph):
        class_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "class"]
        assert len(class_nodes) > 0

    def test_function_nodes(self, graph):
        func_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "function"]
        assert len(func_nodes) > 0

    def test_route_nodes(self, graph):
        route_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "route"]
        assert len(route_nodes) > 0
        assert "route:get:/health" in graph

    def test_dependency_nodes(self, graph):
        dep_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "dependency"]
        assert len(dep_nodes) > 0


class TestGraphBuilderEdges:
    """Tests for edge generation in GraphBuilder."""

    def test_contains_edges(self, graph):
        contains_edges = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("type") == "CONTAINS"
        ]
        assert len(contains_edges) > 0

    def test_imports_edges(self, graph):
        imports_edges = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("type") == "IMPORTS"
        ]
        assert len(imports_edges) > 0

    def test_exposes_edges(self, graph):
        exposes_edges = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("type") == "EXPOSES"
        ]
        assert len(exposes_edges) > 0

    def test_depends_on_edges(self, graph):
        depends_edges = [
            (u, v) for u, v, d in graph.edges(data=True)
            if d.get("type") == "DEPENDS_ON"
        ]
        assert len(depends_edges) > 0


class TestGraphBuilderStatistics:
    """Tests for GraphBuilder statistics."""

    def test_get_statistics(self, analysis):
        builder = GraphBuilder(analysis)
        builder.build()
        stats = builder.get_statistics()

        assert "nodes" in stats
        assert "edges" in stats
        total_nodes = stats["total_nodes"]
        total_edges = stats["total_edges"]
        nodes_dict = stats["nodes"]
        assert isinstance(total_nodes, int) and total_nodes > 0
        assert isinstance(total_edges, int) and total_edges > 0
        assert isinstance(nodes_dict, dict) and nodes_dict.get("file", 0) > 0
