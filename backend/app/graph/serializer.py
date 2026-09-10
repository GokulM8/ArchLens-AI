"""Serialization utilities for the ArchLens AI Phase 2 graph.

Converts NetworkX MultiDiGraph to and from JSON format for storage and transmission.
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Tuple
import networkx as nx

from app.models.schemas import RelationshipType


class GraphSerializer:
    """Handles serialization and deserialization of the code dependency graph."""

    @staticmethod
    def to_json(graph: nx.MultiDiGraph) -> Dict[str, Any]:
        """Convert NetworkX MultiDiGraph to JSON-serializable dictionary.

        Args:
            graph: The NetworkX MultiDiGraph to serialize

        Returns:
            Dictionary representation of the graph suitable for JSON serialization
        """
        data = {
            "directed": True,
            "multigraph": True,
            "graph": {},
            "nodes": [],
            "links": [],
        }

        # Add graph attributes
        for attr_name, attr_value in graph.graph.items():
            data["graph"][attr_name] = attr_value

        # Add nodes
        for node_id, node_data in graph.nodes(data=True):
            node_entry = {"id": node_id}
            # Add all node attributes
            for attr_name, attr_value in node_data.items():
                node_entry[attr_name] = attr_value
            data["nodes"].append(node_entry)

        # Add edges (links)
        for source, target, key, edge_data in graph.edges(keys=True, data=True):
            link_entry = {
                "source": source,
                "target": target,
                "key": key,
            }
            # Add all edge attributes
            for attr_name, attr_value in edge_data.items():
                link_entry[attr_name] = attr_value
            data["links"].append(link_entry)

        return data

    @staticmethod
    def from_json(data: Dict[str, Any]) -> nx.MultiDiGraph:
        """Create NetworkX MultiDiGraph from JSON data.

        Args:
            data: Dictionary representation of the graph (as produced by to_json)

        Returns:
            Reconstructed NetworkX MultiDiGraph
        """
        # Create empty multidigraph
        graph = nx.MultiDiGraph()

        # Add graph attributes
        graph.graph.update(data.get("graph", {}))

        # Add nodes
        for node_data in data.get("nodes", []):
            node_id = node_data.pop("id")  # Remove 'id' from attributes
            graph.add_node(node_id, **node_data)

        # Add edges
        for link_data in data.get("links", []):
            source = link_data.pop("source")
            target = link_data.pop("target")
            key = link_data.pop("key", 0)  # Default key if not provided
            graph.add_edge(source, target, key=key, **link_data)

        return graph

    @staticmethod
    def to_json_string(graph: nx.MultiDiGraph, indent: int = 2) -> str:
        """Convert NetworkX MultiDiGraph to JSON string.

        Args:
            graph: The NetworkX MultiDiGraph to serialize
            indent: Indentation level for pretty-printing (default: 2)

        Returns:
            JSON string representation of the graph
        """
        data = GraphSerializer.to_json(graph)
        return json.dumps(data, indent=indent, sort_keys=True)

    @staticmethod
    def from_json_string(json_str: str) -> nx.MultiDiGraph:
        """Create NetworkX MultiDiGraph from JSON string.

        Args:
            json_str: JSON string representation of the graph

        Returns:
            Reconstructed NetworkX MultiDiGraph
        """
        data = json.loads(json_str)
        return GraphSerializer.from_json(data)

    @staticmethod
    def save_to_file(graph: nx.MultiDiGraph, file_path: str, indent: int = 2) -> None:
        """Save NetworkX MultiDiGraph to a JSON file.

        Args:
            graph: The NetworkX MultiDiGraph to save
            file_path: Path to the output JSON file
            indent: Indentation level for pretty-printing (default: 2)
        """
        json_str = GraphSerializer.to_json_string(graph, indent)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(json_str)

    @staticmethod
    def load_from_file(file_path: str) -> nx.MultiDiGraph:
        """Load NetworkX MultiDiGraph from a JSON file.

        Args:
            file_path: Path to the input JSON file

        Returns:
            Reconstructed NetworkX MultiDiGraph
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            json_str = f.read()
        return GraphSerializer.from_json_string(json_str)

    @staticmethod
    def to_cytoscape_json(graph: nx.MultiDiGraph) -> Dict[str, Any]:
        """Convert to Cytoscape.js JSON format for visualization.

        Args:
            graph: The NetworkX MultiDiGraph to convert

        Returns:
            Dictionary in Cytoscape.js format
        """
        elements = {"nodes": [], "edges": []}

        # Convert nodes
        for node_id, node_data in graph.nodes(data=True):
            # Cytoscape expects node data under 'data' field
            node_element = {
                "data": {
                    "id": node_id,
                    **node_data
                }
            }
            elements["nodes"].append(node_element)

        # Convert edges
        for source, target, key, edge_data in graph.edges(keys=True, data=True):
            # Cytoscape expects edge data under 'data' field
            # We need to create a unique ID for the edge
            edge_id = f"{source}-{target}-{key}"
            edge_element = {
                "data": {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    **edge_data
                }
            }
            elements["edges"].append(edge_element)

        return elements

    @staticmethod
    def get_summary(graph: nx.MultiDiGraph) -> Dict[str, Any]:
        """Get a summary of the graph's contents.

        Args:
            graph: The NetworkX MultiDiGraph to summarize

        Returns:
            Dictionary with summary statistics
        """
        # Count nodes by type
        node_types: Dict[str, int] = {}
        for _, node_data in graph.nodes(data=True):
            node_type = node_data.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

        # Count edges by type
        edge_types: Dict[str, int] = {}
        for _, _, _, edge_data in graph.edges(keys=True, data=True):
            edge_type = edge_data.get("type", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

        return {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
            "is_directed": graph.is_directed(),
            "is_multigraph": graph.is_multigraph(),
        }