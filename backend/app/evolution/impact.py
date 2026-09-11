"""Phase 5 Impact Analysis Engine."""

from typing import List, Set, Dict
import networkx as nx

from app.models.schemas import AnalysisResult
from app.architecture.schemas import ArchitectureResult
from app.evolution.schemas import ImpactAnalysis, ImpactLevel, RefactoringOpportunity


class ImpactAnalyzer:
    """Analyzes the impact of proposed refactoring changes."""

    def __init__(
        self,
        analysis: AnalysisResult,
        graph: nx.MultiDiGraph,
        architecture: ArchitectureResult,
    ):
        self.analysis = analysis
        self.graph = graph
        self.architecture = architecture
        self.components_map = {c.id: c for c in architecture.components}

    def analyze_refactoring_impact(
        self, refactoring: RefactoringOpportunity
    ) -> ImpactAnalysis:
        """Analyze impact of a single refactoring opportunity."""
        directly_affected = set(refactoring.components)
        indirectly_affected = self._trace_dependents(directly_affected)
        affected_layers = self._get_affected_layers(directly_affected | indirectly_affected)
        affected_routes = self._count_affected_routes(directly_affected | indirectly_affected)
        affected_deps = self._count_affected_dependencies(directly_affected)

        total_impact = len(directly_affected) + len(indirectly_affected)
        impact_level = self._calculate_impact_level(
            len(directly_affected),
            len(indirectly_affected),
            affected_routes,
            affected_deps,
        )

        return ImpactAnalysis(
            directly_affected_components=list(directly_affected),
            indirectly_affected_components=list(indirectly_affected),
            affected_layers=affected_layers,
            affected_routes=affected_routes,
            affected_dependencies=affected_deps,
            total_impact_count=total_impact,
            impact_level=impact_level,
        )

    def _trace_dependents(self, component_ids: Set[str]) -> Set[str]:
        """Find all components that depend on the given components."""
        dependents = set()

        for comp_id in component_ids:
            if comp_id in self.graph:
                # BFS to find all nodes that have a path TO this component
                visited = set()
                queue = [comp_id]

                while queue:
                    current = queue.pop(0)
                    if current not in visited:
                        visited.add(current)

                        # Add all predecessors (things that import this)
                        for pred in self.graph.predecessors(current):
                            if pred not in component_ids:
                                dependents.add(pred)
                                if pred not in visited:
                                    queue.append(pred)

        return dependents

    def _get_affected_layers(self, component_ids: Set[str]) -> List[str]:
        """Get unique architectural layers of affected components."""
        layers = set()

        for comp_id in component_ids:
            if comp_id in self.components_map:
                comp = self.components_map[comp_id]
                layers.add(comp.layer.value)

        return sorted(list(layers))

    def _count_affected_routes(self, component_ids: Set[str]) -> int:
        """Count routes exposed by affected components."""
        affected_routes = set()

        for route in self.analysis.routes:
            # Check if route belongs to an affected component
            route_module = getattr(route, "file_path", getattr(route, "module_id", None))

            if route_module and route_module in component_ids:
                route_id = getattr(route, "id", getattr(route, "name", route_module))
                affected_routes.add(route_id)

        return len(affected_routes)

    def _count_affected_dependencies(self, component_ids: Set[str]) -> int:
        """Count external dependencies in affected components."""
        affected_deps = set()

        for comp_id in component_ids:
            # Find module by component ID
            module = next((m for m in self.analysis.modules if m.id == comp_id), None)

            if module:
                for imp in module.imports:
                    # External import check
                    if not imp.module.startswith("module:"):
                        affected_deps.add(imp.module)

        return len(affected_deps)

    def _calculate_impact_level(
        self,
        direct_count: int,
        indirect_count: int,
        route_count: int,
        _dep_count: int,
    ) -> ImpactLevel:
        """Calculate overall impact level."""
        # CRITICAL: >10 direct, or >30 indirect, or >5 routes
        if direct_count > 10 or indirect_count > 30 or route_count > 5:
            return ImpactLevel.CRITICAL

        # HIGH: >5 direct, or >15 indirect, or >2 routes
        if direct_count > 5 or indirect_count > 15 or route_count > 2:
            return ImpactLevel.HIGH

        # MEDIUM: >2 direct, or >5 indirect, or >1 route
        if direct_count > 2 or indirect_count > 5 or route_count > 1:
            return ImpactLevel.MEDIUM

        # LOW: minimal impact
        return ImpactLevel.LOW

    def analyze_batch_impact(
        self, refactorings: List[RefactoringOpportunity]
    ) -> Dict[str, ImpactAnalysis]:
        """Analyze impact for multiple refactoring opportunities."""
        impact_map = {}

        for ref in refactorings:
            impact_map[ref.id] = self.analyze_refactoring_impact(ref)

        return impact_map
