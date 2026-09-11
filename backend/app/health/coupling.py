"""Coupling analysis for detecting over-connected components."""

from typing import Dict, List
import networkx as nx

from app.health.schemas import CouplingMetrics


class CouplingAnalyzer:
    """Analyzes module coupling and connectivity."""

    def __init__(self, graph: nx.MultiDiGraph, components: List):
        self.graph = graph
        self.components = {c.id: c for c in components}

    def analyze_coupling(self) -> CouplingMetrics:
        """Analyze coupling metrics for all components."""
        coupling_scores = {}

        for node in self.graph.nodes():
            if node in self.components:
                in_degree = self.graph.in_degree(node)
                out_degree = self.graph.out_degree(node)
                total_degree = in_degree + out_degree
                coupling_scores[node] = {
                    "in_degree": in_degree,
                    "out_degree": out_degree,
                    "total_degree": total_degree,
                }

        # Calculate statistics
        if coupling_scores:
            total_degrees = [s["total_degree"] for s in coupling_scores.values()]
            avg_coupling = sum(total_degrees) / len(total_degrees)
            total_degrees_sorted = sorted(total_degrees)
            median_coupling = (
                total_degrees_sorted[len(total_degrees_sorted) // 2]
                if total_degrees_sorted
                else 0
            )
            max_coupling = max(total_degrees)
        else:
            avg_coupling = 0.0
            median_coupling = 0.0
            max_coupling = 0

        # Identify high coupling components
        high_coupling_threshold = avg_coupling * 1.5 if avg_coupling > 0 else 0
        high_coupling_components = []

        for comp_id, scores in coupling_scores.items():
            if scores["total_degree"] > high_coupling_threshold:
                comp = self.components[comp_id]
                high_coupling_components.append({
                    "component": comp_id,
                    "component_name": comp.name,
                    "in_degree": scores["in_degree"],
                    "out_degree": scores["out_degree"],
                    "total_degree": scores["total_degree"],
                    "reason": f"Coupling ({scores['total_degree']}) exceeds repository average ({avg_coupling:.1f})",
                })

        return CouplingMetrics(
            total_components=len(self.components),
            average_coupling=round(avg_coupling, 2),
            median_coupling=round(median_coupling, 2),
            max_coupling=max_coupling,
            high_coupling_components=high_coupling_components,
        )
