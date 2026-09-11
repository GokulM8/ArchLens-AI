"""Risk detection and analysis engine for Phase 4."""

from typing import List, Dict
import networkx as nx

from app.architecture.schemas import ArchitectureComponent, ArchitectureResult, ArchitecturalLayer
from app.health.schemas import Risk, RiskType, RiskSeverity, LayerViolation


class RiskDetector:
    """Detects architectural risks from metrics and analysis."""

    # Layer hierarchy for determining violation severity
    LAYER_HIERARCHY = {
        ArchitecturalLayer.PRESENTATION: 0,
        ArchitecturalLayer.APPLICATION: 1,
        ArchitecturalLayer.CROSS_CUTTING: 1.5,
        ArchitecturalLayer.DOMAIN: 2,
        ArchitecturalLayer.DATA: 3,
        ArchitecturalLayer.INFRASTRUCTURE: 4,
        ArchitecturalLayer.EXTERNAL: 5,
        ArchitecturalLayer.TESTING: -1,
        ArchitecturalLayer.UNKNOWN: -2,
    }

    def __init__(self, graph: nx.MultiDiGraph, architecture: ArchitectureResult):
        self.graph = graph
        self.architecture = architecture
        self.components_map = {c.id: c for c in architecture.components}

    def detect_layer_violations(self) -> List[LayerViolation]:
        """Detect architectural layer boundary violations."""
        violations = []

        for u, v, data in self.graph.edges(data=True):
            if data.get("type") != "IMPORTS":
                continue

            if u not in self.components_map or v not in self.components_map:
                continue

            source_comp = self.components_map[u]
            target_comp = self.components_map[v]

            violation = self._check_layer_violation(source_comp, target_comp)
            if violation:
                violations.append(violation)

        return violations

    def _check_layer_violation(
        self,
        source: ArchitectureComponent,
        target: ArchitectureComponent,
    ) -> LayerViolation | None:
        """Check if a dependency violates layer boundaries."""
        source_level = self.LAYER_HIERARCHY.get(source.layer, -2)
        target_level = self.LAYER_HIERARCHY.get(target.layer, -2)

        # Downward dependency (lower layer depends on higher) is usually bad
        if target_level > source_level:
            # Calculate severity based on distance
            distance = target_level - source_level
            if distance > 2:
                severity = RiskSeverity.CRITICAL
                reason = "Direct dependency from high layer to infrastructure/external"
            elif distance > 1:
                severity = RiskSeverity.HIGH
                reason = "Cross-layer dependency spanning multiple layers"
            else:
                severity = RiskSeverity.MEDIUM
                reason = "Dependency crosses layer boundary"

            return LayerViolation(
                source_component=source.id,
                target_component=target.id,
                source_layer=source.layer.value,
                target_layer=target.layer.value,
                severity=severity,
                reason=reason,
            )

        return None

    def detect_large_module_risks(self, complexity_metrics) -> List[Risk]:
        """Detect risk from overly large modules."""
        risks = []

        for module_info in complexity_metrics.largest_modules[:5]:
            loc = module_info.get("lines_of_code", 0)
            if loc > 500:  # Arbitrary threshold
                severity = RiskSeverity.MEDIUM if loc < 1000 else RiskSeverity.HIGH
                risks.append(Risk(
                    id=f"large_module_{module_info['module']}",
                    type=RiskType.LARGE_MODULE,
                    severity=severity,
                    title=f"Large Module: {module_info['module_name']}",
                    description=f"Module contains {loc} lines of code, which may indicate mixed responsibilities.",
                    components=[module_info["module"]],
                    evidence=[
                        f"Lines of code: {loc}",
                        f"Classes: {module_info.get('class_count', 0)}",
                        f"Functions: {module_info.get('function_count', 0)}",
                    ],
                    metric=f"{loc} LOC",
                    recommendation="Consider decomposing the module by responsibility or extracting cohesive functionality.",
                ))

        return risks

    def detect_high_coupling_risks(self, coupling_metrics) -> List[Risk]:
        """Detect risks from high coupling."""
        risks = []

        for comp_info in coupling_metrics.high_coupling_components:
            risks.append(Risk(
                id=f"high_coupling_{comp_info['component']}",
                type=RiskType.HIGH_COUPLING,
                severity=RiskSeverity.MEDIUM,
                title=f"High Coupling: {comp_info['component_name']}",
                description=f"Component has {comp_info['total_degree']} dependencies, above repository average.",
                components=[comp_info["component"]],
                evidence=[
                    f"Total degree: {comp_info['total_degree']}",
                    f"In-degree: {comp_info['in_degree']}",
                    f"Out-degree: {comp_info['out_degree']}",
                    f"Repository average: {coupling_metrics.average_coupling:.1f}",
                ],
                metric=str(comp_info["total_degree"]),
                recommendation="Review component responsibilities and consider splitting or introducing abstractions.",
            ))

        return risks

    def detect_circular_dependency_risks(self, dependency_metrics) -> List[Risk]:
        """Detect risks from circular dependencies."""
        risks = []

        if dependency_metrics.circular_dependency_count > 0:
            for i, cycle in enumerate(dependency_metrics.circular_dependencies):
                severity = RiskSeverity.HIGH if len(cycle.components) <= 3 else RiskSeverity.MEDIUM

                risks.append(Risk(
                    id=f"circular_{i}",
                    type=RiskType.CIRCULAR_DEPENDENCY,
                    severity=severity,
                    title=f"Circular Dependency (Length {cycle.length})",
                    description=f"Detected cycle: {cycle.evidence}",
                    components=cycle.components,
                    evidence=[cycle.evidence],
                    metric=f"{cycle.length} components",
                    recommendation="Break the cycle by introducing a new abstraction, reversing a dependency, or extracting shared code.",
                ))

        return risks

    def detect_api_concentration_risks(self, api_metrics) -> List[Risk]:
        """Detect risk from concentrated API surface."""
        risks = []

        if api_metrics.routes_per_module:
            total_routes = api_metrics.total_routes
            avg_routes = total_routes / len(api_metrics.routes_per_module) if api_metrics.routes_per_module else 0

            for module_id, route_count in api_metrics.routes_per_module.items():
                if route_count > avg_routes * 2:
                    module = self.components_map.get(module_id)
                    if module:
                        risks.append(Risk(
                            id=f"api_concentration_{module_id}",
                            type=RiskType.API_CONCENTRATION,
                            severity=RiskSeverity.LOW,
                            title=f"API Concentration: {module.name}",
                            description=f"Module exposes {route_count} routes, {route_count - int(avg_routes)} above average.",
                            components=[module_id],
                            evidence=[
                                f"Routes in module: {route_count}",
                                f"Average routes per module: {avg_routes:.1f}",
                            ],
                            metric=str(route_count),
                            recommendation="Consider splitting routes across multiple controller/route modules for better organization.",
                        ))

        return risks
