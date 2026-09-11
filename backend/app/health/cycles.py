"""Cycle detection for dependency graphs."""

from typing import List, Set, Dict, Tuple
import networkx as nx

from app.health.schemas import CircularDependency


class CycleDetector:
    """Detects circular dependencies in the module dependency graph."""

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph

    def detect_cycles(self) -> Tuple[int, List[CircularDependency]]:
        """Detect all cycles in the dependency graph.

        Returns:
            Tuple of (cycle count, list of CircularDependency objects)
        """
        cycles = []

        try:
            # Find all simple cycles
            cycle_list = list(nx.simple_cycles(self.graph))

            # Filter to meaningful dependency cycles (IMPORTS edges only)
            for cycle in cycle_list:
                if self._is_valid_cycle(cycle):
                    cycles.append(self._build_cycle_description(cycle))
        except nx.NetworkXNoCycle:
            pass

        return len(cycles), cycles

    def _is_valid_cycle(self, cycle: List[str]) -> bool:
        """Check if a cycle consists of meaningful IMPORTS dependencies."""
        if len(cycle) < 2:
            return False

        # Verify all edges in the cycle are IMPORTS relationships
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]

            # Check if edge exists and is IMPORTS type
            if self.graph.has_edge(u, v):
                edge_data = self.graph.get_edge_data(u, v)
                # edge_data is a dict of edge keys to data
                has_imports = any(
                    data.get("type") == "IMPORTS"
                    for data in edge_data.values()
                    if isinstance(data, dict)
                )
                if not has_imports:
                    return False
            else:
                return False

        return True

    def _build_cycle_description(self, cycle: List[str]) -> CircularDependency:
        """Build a CircularDependency description from a cycle."""
        evidence_parts = []
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]
            # Extract friendly name from module ID
            u_name = u.split(":")[-1] if ":" in u else u
            v_name = v.split(":")[-1] if ":" in v else v
            evidence_parts.append(f"{u_name} → {v_name}")

        evidence = ", ".join(evidence_parts)

        return CircularDependency(
            components=cycle,
            length=len(cycle),
            evidence=evidence,
        )
