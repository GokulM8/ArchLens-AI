"""Validation utilities for the ArchLens AI Phase 2 graph.

Validates the integrity and consistency of the NetworkX MultiDiGraph
generated from analysis results.
"""

from __future__ import annotations

import networkx as nx
from typing import Dict, List
from dataclasses import dataclass, field

from app.models.schemas import RelationshipType


@dataclass
class ValidationResult:
    """Result of graph validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add a validation error."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)


class GraphValidator:
    """Validates the integrity of the code dependency graph."""

    def __init__(self, graph: nx.MultiDiGraph):
        """Initialize with the graph to validate.

        Args:
            graph: The NetworkX MultiDiGraph to validate
        """
        self.graph = graph

    def validate(self) -> ValidationResult:
        """Run all validation checks on the graph.

        Returns:
            ValidationResult containing any errors or warnings
        """
        result = ValidationResult()

        # Run validation checks
        self._validate_node_types(result)
        self._validate_edge_types(result)
        self._validate_referential_integrity(result)
        self._validate_hierarchy(result)
        self._validate_import_consistency(result)
        self._validate_no_self_loops(result)

        return result

    def _validate_node_types(self, result: ValidationResult) -> None:
        """Validate that all nodes have correct types and required fields."""
        valid_types = {
            "repository", "directory", "file", "module",
            "class", "function", "route", "dependency"
        }

        for node_id, node_data in self.graph.nodes(data=True):
            node_type = node_data.get("type")

            if not node_type:
                result.add_error(f"Node {node_id} is missing 'type' attribute")
                continue

            if node_type not in valid_types:
                result.add_error(f"Node {node_id} has invalid type '{node_type}'")
                continue

            # Type-specific validation
            if node_type == "repository":
                if "label" not in node_data:
                    result.add_warning(f"Repository node {node_id} missing label")
                if "path" not in node_data:
                    result.add_error(f"Repository node {node_id} missing path")

            elif node_type == "directory":
                if "path" not in node_data:
                    result.add_error(f"Directory node {node_id} missing path")

            elif node_type == "file":
                required_fields = ["path", "size_bytes", "lines"]
                for field in required_fields:
                    if field not in node_data:
                        result.add_error(f"File node {node_id} missing {field}")

            elif node_type == "module":
                if "path" not in node_data:
                    result.add_error(f"Module node {node_id} missing path")

            elif node_type == "class":
                required_fields = ["file", "line_start", "line_end"]
                for field in required_fields:
                    if field not in node_data:
                        result.add_error(f"Class node {node_id} missing {field}")

            elif node_type == "function":
                required_fields = ["file", "line_start", "line_end"]
                for field in required_fields:
                    if field not in node_data:
                        result.add_error(f"Function node {node_id} missing {field}")

            elif node_type == "route":
                required_fields = ["method", "path", "function_id"]
                for field in required_fields:
                    if field not in node_data:
                        result.add_error(f"Route node {node_id} missing {field}")

            elif node_type == "dependency":
                if "name" not in node_data:
                    result.add_error(f"Dependency node {node_id} missing name")

    def _validate_edge_types(self, result: ValidationResult) -> None:
        """Validate that all edges have correct types and required fields."""
        valid_types = {t.value for t in RelationshipType}

        for source, target, edge_data in self.graph.edges(data=True):
            edge_type = edge_data.get("type")

            if not edge_type:
                result.add_error(f"Edge {source} -> {target} is missing 'type' attribute")
                continue

            if edge_type not in valid_types:
                result.add_error(f"Edge {source} -> {target} has invalid type '{edge_type}'")
                continue

            # Type-specific validation
            if edge_type == RelationshipType.IMPORTS.value:
                if "import_type" not in edge_data:
                    result.add_warning(f"IMPORTS edge {source} -> {target} missing import_type")
                if "line" not in edge_data:
                    result.add_warning(f"IMPORTS edge {source} -> {target} missing line")

            elif edge_type == RelationshipType.CONTAINS.value:
                # CONTAINS edges don't require additional fields
                pass

            elif edge_type == RelationshipType.EXPOSES.value:
                if "line" not in edge_data:
                    result.add_warning(f"EXPOSES edge {source} -> {target} missing line")

            elif edge_type == RelationshipType.DEPENDS_ON.value:
                if "import_type" not in edge_data:
                    result.add_warning(f"DEPENDS_ON edge {source} -> {target} missing import_type")
                if "line" not in edge_data:
                    result.add_warning(f"DEPENDS_ON edge {source} -> {target} missing line")

    def _validate_referential_integrity(self, result: ValidationResult) -> None:
        """Validate that all references point to existing nodes."""
        node_ids = set(self.graph.nodes())

        for source, target, edge_data in self.graph.edges(data=True):
            if source not in node_ids:
                result.add_error(f"Edge references non-existent source node: {source}")
            if target not in node_ids:
                result.add_error(f"Edge references non-existent target node: {target}")

    def _validate_hierarchy(self, result: ValidationResult) -> None:
        """Validate hierarchical relationships make sense."""
        # Check that repository is root (has no incoming CONTAINS edges)
        repo_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get("type") == "repository"
        ]

        for repo_id in repo_nodes:
            incoming_contain = [
                (s, t) for s, t, d in self.graph.in_edges(repo_id, data=True)
                if d.get("type") == RelationshipType.CONTAINS.value
            ]
            if incoming_contain:
                result.add_warning(
                    f"Repository node {repo_id} has incoming CONTAINS edges: {incoming_contain}"
                )

        # Check that files don't contain repositories (wrong direction)
        for source, target, edge_data in self.graph.edges(data=True):
            if edge_data.get("type") == RelationshipType.CONTAINS.value:
                source_type = self.graph.nodes[source].get("type")
                target_type = self.graph.nodes[target].get("type")

                # File should not contain repository
                if source_type == "file" and target_type == "repository":
                    result.add_error(
                        f"Invalid containment: file {source} contains repository {target}"
                    )

                # Dependency should not contain anything
                if source_type == "dependency":
                    result.add_error(
                        f"Invalid containment: dependency {source} contains {target_type} {target}"
                    )

    def _validate_import_consistency(self, result: ValidationResult) -> None:
        """Validate IMPORTS edges are consistent with module information."""
        for source, target, edge_data in self.graph.edges(data=True):
            if edge_data.get("type") != RelationshipType.IMPORTS.value:
                continue

            source_module_id = source
            target_module_id = target

            # Both should be modules
            source_type = self.graph.nodes[source_module_id].get("type")
            target_type = self.graph.nodes[target_module_id].get("type")

            if source_type != "module":
                result.add_warning(
                    f"IMPORTS edge source {source} is not a module (type: {source_type})"
                )
            if target_type != "module":
                result.add_warning(
                    f"IMPORTS edge target {target} is not a module (type: {target_type})"
                )

    def _validate_no_self_loops(self, result: ValidationResult) -> None:
        """Validate that there are no self-loops (except possibly for special cases)."""
        for node_id in self.graph.nodes():
            if self.graph.has_edge(node_id, node_id):
                # Get all edge data for self-loops
                self_loop_data = list(self.graph.get_edge_data(node_id, node_id).values())

                # Self-loops are generally not valid in code graphs
                result.add_error(f"Node {node_id} has self-loop(s): {self_loop_data}")

    def get_node_statistics(self) -> Dict[str, int]:
        """Get count of nodes by type."""
        counts: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts

    def get_edge_statistics(self) -> Dict[str, int]:
        """Get count of edges by type."""
        counts: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            edge_type = data.get("type", "unknown")
            counts[edge_type] = counts.get(edge_type, 0) + 1
        return counts