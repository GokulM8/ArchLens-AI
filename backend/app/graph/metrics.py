"""Metrics computation for the ArchLens AI Phase 2 graph.

Computes various graph metrics from the NetworkX MultiDiGraph,
including structural metrics, centrality, and code-specific metrics.
"""

from __future__ import annotations

import networkx as nx
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict, Counter

from app.models.schemas import RelationshipType


class GraphMetrics:
    """Computes metrics for the code dependency graph."""

    def __init__(self, graph: nx.MultiDiGraph):
        """Initialize with the graph to analyze.

        Args:
            graph: The NetworkX MultiDiGraph to analyze
        """
        self.graph = graph
        # Precompute some useful views
        self._node_types: Dict[str, str] = {
            node: data.get("type", "unknown")
            for node, data in graph.nodes(data=True)
        }
        self._edge_types: Dict[Tuple[str, str, int], str] = {}
        for u, v, k, data in graph.edges(keys=True, data=True):
            self._edge_types[(u, v, k)] = data.get("type", "unknown")

    def compute_all(self) -> Dict[str, Any]:
        """Compute all available metrics.

        Returns:
            Dictionary containing all computed metrics
        """
        metrics = {}

        # Basic structural metrics
        metrics.update(self._compute_basic_metrics())
        metrics.update(self._compute_connectivity_metrics())
        metrics.update(self._compute_cycle_metrics())
        metrics.update(self._compute_centrality_metrics())
        metrics.update(self._compute_code_specific_metrics())

        return metrics

    def _compute_basic_metrics(self) -> Dict[str, Any]:
        """Compute basic node and edge counts."""
        node_counts = Counter(self._node_types.values())
        edge_counts = Counter(self._edge_types.values())

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": dict(node_counts),
            "edge_types": dict(edge_counts),
        }

    def _compute_connectivity_metrics(self) -> Dict[str, Any]:
        """Compute connectivity-related metrics."""
        # Convert to undirected for connectivity metrics
        undirected = self.graph.to_undirected()

        # Connected components
        connected_components = list(nx.connected_components(undirected))
        num_components = len(connected_components)

        # For directed graphs, we can also compute weakly and strongly connected components
        weakly_connected = list(nx.weakly_connected_components(self.graph))
        num_weakly_connected = len(weakly_connected)

        try:
            strongly_connected = list(nx.strongly_connected_components(self.graph))
            num_strongly_connected = len(strongly_connected)
        except nx.NetworkXPointlessConcept:
            # This can happen if the graph has no nodes
            strongly_connected = []
            num_strongly_connected = 0

        # Isolates (nodes with no edges)
        isolates = list(nx.isolates(self.graph))
        num_isolates = len(isolates)

        # Density
        density = nx.density(self.graph)

        return {
            "connected_components": num_components,
            "weakly_connected_components": num_weakly_connected,
            "strongly_connected_components": num_strongly_connected,
            "isolates": num_isolates,
            "isolate_nodes": [n for n in isolates],
            "density": density,
        }

    def _compute_cycle_metrics(self) -> Dict[str, Any]:
        """Compute cycle-related metrics."""
        # Note: Finding all cycles in a directed graph can be expensive.
        # We'll look for cycles in the condensed graph (SCC) and also try to find
        # cycles in the original graph if it's not too large.

        # First, get strongly connected components
        try:
            scc = list(nx.strongly_connected_components(self.graph))
        except nx.NetworkXPointlessConcept:
            scc = []

        # Count of SCCs with more than one node (or a single node with a self-loop)
        cyclic_sccs = []
        for component in scc:
            if len(component) > 1:
                cyclic_sccs.append(component)
            else:
                # Single node component - check for self-loop
                node = next(iter(component))
                if self.graph.has_edge(node, node):
                    cyclic_sccs.append(component)

        num_cyclic_sccs = len(cyclic_sccs)

        # Try to find cycles (limit to avoid explosion on large graphs)
        try:
            # We'll use nx.simple_cycles but limit the length to avoid too many cycles
            # Also, we can break early if we find too many
            cycles = []
            max_cycles_to_compute = 1000  # Safety limit
            for cycle in nx.simple_cycles(self.graph):
                cycles.append(cycle)
                if len(cycles) >= max_cycles_to_compute:
                    break
        except (nx.NetworkXPointlessConcept, nx.NetworkXError):
            cycles = []

        return {
            "strongly_connected_components": len(scc),
            "cyclic_strongly_connected_components": num_cyclic_sccs,
            "cycles_found": len(cycles),
            "cycle_examples": cycles[:5],  # First 5 cycles as examples
        }

    def _compute_centrality_metrics(self) -> Dict[str, Any]:
        """Compute centrality metrics for key node types."""
        # We'll compute centrality for the whole graph and then break down by type
        # Note: These can be expensive on large graphs.

        metrics = {}

        try:
            # In-degree centrality (for IMPORTS and DEPENDS_ON, higher means more dependencies)
            in_degree_centrality = nx.in_degree_centrality(self.graph)
            metrics["avg_in_degree_centrality"] = sum(in_degree_centrality.values()) / len(in_degree_centrality) if in_degree_centrality else 0

            # Out-degree centrality (for EXPOSES, higher means more routes exposed)
            out_degree_centrality = nx.out_degree_centrality(self.graph)
            metrics["avg_out_degree_centrality"] = sum(out_degree_centrality.values()) / len(out_degree_centrality) if out_degree_centrality else 0

            # Betweenness centrality (nodes that lie on many shortest paths)
            # This is expensive, so we'll approximate or skip for large graphs
            if self.graph.number_of_nodes() < 1000:
                betweenness = nx.betweenness_centrality(self.graph)
                metrics["avg_betweenness_centrality"] = sum(betweenness.values()) / len(betweenness) if betweenness else 0
            else:
                metrics["betweenness_centrality"] = "skipped (graph too large)"

        except nx.NetworkXError:
            # If centrality fails (e.g., on empty graph)
            metrics["centrality_error"] = "Failed to compute centrality metrics"

        return metrics

    def _compute_code_specific_metrics(self) -> Dict[str, Any]:
        """Compute metrics specific to code structure."""
        metrics = {}

        # Ratio of internal to external dependencies
        internal_edges = sum(
            1 for u, v, k, data in self.graph.edges(keys=True, data=True)
            if data.get("type") == RelationshipType.IMPORTS.value
               and data.get("import_type") == "internal"
        )
        external_edges = sum(
            1 for u, v, k, data in self.graph.edges(keys=True, data=True)
            if data.get("type") == RelationshipType.IMPORTS.value
               and data.get("import_type") in ("external", "standard_library")
        )
        total_imports = internal_edges + external_edges

        if total_imports > 0:
            metrics["internal_import_ratio"] = internal_edges / total_imports
            metrics["external_import_ratio"] = external_edges / total_imports
        else:
            metrics["internal_import_ratio"] = 0.0
            metrics["external_import_ratio"] = 0.0

        # Average number of imports per module
        module_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get("type") == "module"
        ]
        if module_nodes:
            imports_per_module = []
            for module in module_nodes:
                # Count outgoing IMPORTS edges
                imp_count = sum(
                    1 for _u, _v, _k, data in self.graph.out_edges(module, keys=True, data=True)
                    if data.get("type") == RelationshipType.IMPORTS.value
                )
                imports_per_module.append(imp_count)
            metrics["avg_imports_per_module"] = sum(imports_per_module) / len(imports_per_module)
        else:
            metrics["avg_imports_per_module"] = 0.0

        # Average number of classes per module
        if module_nodes:
            classes_per_module = []
            for module in module_nodes:
                # Count CONTAINS edges to classes
                class_count = sum(
                    1 for _u, _v, _k, data in self.graph.out_edges(module, keys=True, data=True)
                    if data.get("type") == RelationshipType.CONTAINS.value
                    and self.graph.nodes[_v].get("type") == "class"
                )
                classes_per_module.append(class_count)
            metrics["avg_classes_per_module"] = sum(classes_per_module) / len(classes_per_module)
        else:
            metrics["avg_classes_per_module"] = 0.0

        # Average number of functions per module
        if module_nodes:
            functions_per_module = []
            for module in module_nodes:
                # Count CONTAINS edges to functions
                func_count = sum(
                    1 for _u, _v, _k, data in self.graph.out_edges(module, keys=True, data=True)
                    if data.get("type") == RelationshipType.CONTAINS.value
                    and self.graph.nodes[_v].get("type") == "function"
                )
                functions_per_module.append(func_count)
            metrics["avg_functions_per_module"] = sum(functions_per_module) / len(functions_per_module)
        else:
            metrics["avg_functions_per_module"] = 0.0

        # Number of routes (endpoints)
        route_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get("type") == "route"
        ]
        metrics["total_routes"] = len(route_nodes)

        # Average number of routes per function (that have routes)
        function_nodes_with_routes = []
        for func_node, func_data in self.graph.nodes(data=True):
            if func_data.get("type") == "function":
                # Count outgoing EXPOSES edges
                route_count = sum(
                    1 for u, v, k, data in self.graph.out_edges(func_node, keys=True, data=True)
                    if data.get("type") == RelationshipType.EXPOSES.value
                )
                if route_count > 0:
                    function_nodes_with_routes.append(route_count)

        if function_nodes_with_routes:
            metrics["avg_routes_per_function_with_routes"] = sum(function_nodes_with_routes) / len(function_nodes_with_routes)
        else:
            metrics["avg_routes_per_function_with_routes"] = 0.0

        # Dependency metrics
        dependency_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get("type") == "dependency"
        ]
        metrics["total_external_dependencies"] = len(dependency_nodes)

        # Average number of files depending on each external dependency
        if dependency_nodes:
            deps_per_dependency = []
            for dep_node in dependency_nodes:
                # Count incoming DEPENDS_ON edges
                file_count = sum(
                    1 for u, v, k, data in self.graph.in_edges(dep_node, keys=True, data=True)
                    if data.get("type") == RelationshipType.DEPENDS_ON.value
                )
                deps_per_dependency.append(file_count)
            metrics["avg_files_per_dependency"] = sum(deps_per_dependency) / len(deps_per_dependency)
        else:
            metrics["avg_files_per_dependency"] = 0.0

        return metrics