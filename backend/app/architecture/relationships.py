"""High-level architectural relationship extractor for ArchLens AI Phase 3.

Derives architectural relationships from the underlying dependency graph.
"""

from __future__ import annotations

from typing import List, Dict
import networkx as nx

from app.architecture.schemas import (
    ArchitectureComponent,
    ArchitectureRelationship,
    ArchitecturalRole,
)


class RelationshipExtractor:
    """Extracts architectural relationships between classified components."""

    def __init__(self, components: List[ArchitectureComponent], graph: nx.MultiDiGraph):
        self.components = components
        self.graph = graph
        self.comp_map: Dict[str, ArchitectureComponent] = {c.id: c for c in components}

    def extract_all(self) -> List[ArchitectureRelationship]:
        """Extract high-level architectural relationships."""
        relationships: List[ArchitectureRelationship] = []
        seen_pairs = set()

        for u, v, data in self.graph.edges(data=True):
            if data.get("type") == "IMPORTS":
                source_comp = self.comp_map.get(u)
                target_comp = self.comp_map.get(v)

                if source_comp and target_comp and source_comp.id != target_comp.id:
                    pair_key = (source_comp.id, target_comp.id)
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        relationships.append(
                            ArchitectureRelationship(
                                source_id=source_comp.id,
                                target_id=target_comp.id,
                                relationship_type="IMPORTS",
                                source_role=source_comp.role,
                                target_role=target_comp.role,
                            )
                        )

        return relationships
