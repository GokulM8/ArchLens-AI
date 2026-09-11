"""Phase 5 Refactoring Recommendation Detection Engine."""

from typing import List, Dict, Set
import networkx as nx

from app.models.schemas import AnalysisResult
from app.architecture.schemas import ArchitectureResult, ArchitecturalRole
from app.health.schemas import HealthResult, Risk
from app.evolution.schemas import (
    RefactoringOpportunity,
    RefactoringType,
    Priority,
    ImpactLevel,
)


class RecommendationDetector:
    """Detects architectural refactoring opportunities deterministically."""

    def __init__(
        self,
        analysis: AnalysisResult,
        graph: nx.MultiDiGraph,
        architecture: ArchitectureResult,
        health: HealthResult,
    ):
        self.analysis = analysis
        self.graph = graph
        self.architecture = architecture
        self.health = health
        self.components_map = {c.id: c for c in architecture.components}
        self.risk_by_component = self._build_risk_map()

    def detect_all_opportunities(self) -> List[RefactoringOpportunity]:
        """Detect all refactoring opportunities."""
        opportunities = []

        opportunities.extend(self._detect_split_large_module())
        opportunities.extend(self._detect_reduce_high_coupling())
        opportunities.extend(self._detect_break_circular_dependency())
        opportunities.extend(self._detect_reduce_centralization())
        opportunities.extend(self._detect_simplify_dependency_chain())
        opportunities.extend(self._detect_review_layer_violation())
        opportunities.extend(self._detect_separate_responsibilities())
        opportunities.extend(self._detect_extract_shared_component())
        opportunities.extend(self._detect_reduce_external_dependency_concentration())

        return opportunities

    def _detect_split_large_module(self) -> List[RefactoringOpportunity]:
        """Detect modules that should be split into smaller ones - with strong evidence."""
        opportunities = []

        for module in self.analysis.modules:
            # Calculate module complexity with multiple signals
            class_count = len(module.classes)
            function_count = len(module.functions)
            total_members = class_count + function_count

            # Require STRONG evidence: not just member count
            loc = self._estimate_loc(module)

            # Only flag if there's meaningful size AND multiple responsibilities
            if total_members < 15:
                # Small modules are fine
                continue

            # Check for multiple distinct responsibilities
            roles_in_module = self._analyze_component_roles(module.id)
            has_multiple_responsibilities = len(roles_in_module) > 2

            # Check if it has high coupling (architectural problem)
            in_degree = self.graph.in_degree(module.id) if module.id in self.graph else 0
            out_degree = self.graph.out_degree(module.id) if module.id in self.graph else 0
            total_coupling = in_degree + out_degree

            # Calculate repository average for context
            all_coupling = [
                self.graph.in_degree(n) + self.graph.out_degree(n)
                for n in self.graph.nodes()
            ]
            avg_coupling = sum(all_coupling) / len(all_coupling) if all_coupling else 0

            # Only recommend split if there are multiple supporting signals
            signals = []
            if total_members > 20:
                signals.append("high_member_count")
            if loc > 300:
                signals.append("large_size")
            if has_multiple_responsibilities:
                signals.append("mixed_responsibilities")
            if total_coupling > avg_coupling * 2:
                signals.append("high_coupling")

            # Require at least 2 signals
            if len(signals) < 2:
                continue

            confidence = min(1.0, 0.4 + (len(signals) * 0.15))

            opportunities.append(
                RefactoringOpportunity(
                    id=f"split_large_module:{module.id}",
                    type=RefactoringType.SPLIT_LARGE_MODULE,
                    title=f"Split large module: {module.path}",
                    priority=Priority.MEDIUM,  # Downgrade from HIGH
                    severity="medium",  # Downgrade from high
                    description=f"Module {module.path} has {total_members} members, ~{loc} lines, and shows signs of mixed responsibilities.",
                    rationale="Large modules with mixed responsibilities are harder to test, reuse, and maintain.",
                    components=[module.id],
                    evidence=[
                        f"Class count: {class_count}",
                        f"Function count: {function_count}",
                        f"Estimated lines of code: {loc}",
                        f"Distinct roles: {len(roles_in_module)}",
                        f"Coupling: {total_coupling} (avg: {avg_coupling:.1f})",
                        f"Signal count: {len(signals)}",
                    ],
                    suggested_action=f"Split {module.path} by responsibility into 2-3 focused modules.",
                    expected_benefit="Improved modularity, testability, and code reuse.",
                    estimated_scope=ImpactLevel.MEDIUM,
                    confidence=confidence,
                )
            )

        return opportunities

    def _detect_reduce_high_coupling(self) -> List[RefactoringOpportunity]:
        """Detect components with excessive coupling - with strong evidence."""
        opportunities = []

        # Calculate coupling metrics
        coupling_by_component = {}
        for node in self.graph.nodes():
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)
            total_coupling = in_degree + out_degree
            coupling_by_component[node] = total_coupling

        if not coupling_by_component:
            return opportunities

        avg_coupling = sum(coupling_by_component.values()) / len(coupling_by_component)
        high_coupling_threshold = avg_coupling * 2.0

        for comp_id, coupling in coupling_by_component.items():
            if coupling > high_coupling_threshold and comp_id in self.components_map:
                comp = self.components_map[comp_id]
                in_deg = self.graph.in_degree(comp_id)
                out_deg = self.graph.out_degree(comp_id)

                # Require additional signals: component should be problematic, not just connected
                # Skip if it's a legitimate utility/service that's supposed to be central
                if comp.role.value in ["utility", "configuration", "database"]:
                    # These roles commonly have high coupling - skip unless extreme
                    if coupling < avg_coupling * 3.5:
                        continue

                # Check if this component is also flagged for size or other issues
                has_other_signals = any(
                    risk.type.value in ["large_module", "large_class"]
                    and comp_id in risk.components
                    for risk in (self.health.risks or [])
                )

                # Only create recommendation if there's supporting evidence
                if not has_other_signals and coupling < avg_coupling * 3.0:
                    # Moderate coupling without other issues - skip
                    continue

                confidence = min(1.0, 0.5 + (coupling / (high_coupling_threshold * 2)))

                opportunities.append(
                    RefactoringOpportunity(
                        id=f"reduce_high_coupling:{comp_id}",
                        type=RefactoringType.REDUCE_HIGH_COUPLING,
                        title=f"Reduce coupling in: {comp.name}",
                        priority=Priority.MEDIUM,  # Downgrade from HIGH
                        severity="medium",  # Downgrade from high
                        description=f"Component {comp.name} has high coupling: {in_deg} incoming, {out_deg} outgoing dependencies.",
                        rationale="High coupling can increase change risk and testability challenges when combined with other issues.",
                        components=[comp_id],
                        evidence=[
                            f"In-degree: {in_deg}",
                            f"Out-degree: {out_deg}",
                            f"Total coupling: {coupling}",
                            f"Repository average: {avg_coupling:.1f}",
                            f"Threshold: {high_coupling_threshold:.1f}",
                        ],
                        suggested_action="Review dependencies and consider extracting interfaces or using dependency injection to reduce coupling.",
                        expected_benefit="Lower change risk, better modularity, improved testability.",
                        estimated_scope=ImpactLevel.MEDIUM,
                        confidence=confidence,
                    )
                )

        return opportunities

    def _detect_break_circular_dependency(self) -> List[RefactoringOpportunity]:
        """Detect circular dependencies that should be broken."""
        opportunities = []

        # Use health result cycles
        if self.health.dependency_metrics and self.health.dependency_metrics.circular_dependencies:
            for cycle in self.health.dependency_metrics.circular_dependencies:
                if isinstance(cycle, dict) and "nodes" in cycle:
                    nodes = cycle["nodes"]
                elif isinstance(cycle, (list, tuple)):
                    nodes = cycle
                else:
                    continue

                if len(nodes) >= 2:
                    comp_ids = [n for n in nodes if n in self.components_map]
                    if comp_ids:
                        comp_names = [self.components_map[c].name for c in comp_ids]
                        confidence = 0.95  # Cycles are deterministic

                        opportunities.append(
                            RefactoringOpportunity(
                                id=f"break_circular:{':'.join(comp_ids)}",
                                type=RefactoringType.BREAK_CIRCULAR_DEPENDENCY,
                                title=f"Break circular dependency: {' → '.join(comp_names)}",
                                priority=Priority.CRITICAL,
                                severity="critical",
                                description=f"Circular dependency detected: {' → '.join(comp_names)} → {comp_names[0]}",
                                rationale="Circular dependencies prevent independent testing, make refactoring difficult, and indicate structural issues.",
                                components=comp_ids,
                                evidence=[
                                    f"Cycle length: {len(nodes)}",
                                    f"Components: {', '.join(comp_names)}",
                                ],
                                suggested_action="Break the cycle by introducing an abstraction, moving shared code, or reversing a dependency.",
                                expected_benefit="Improved architecture, independent component testing, and easier refactoring.",
                                estimated_scope=ImpactLevel.CRITICAL,
                                confidence=confidence,
                            )
                        )

        return opportunities

    def _detect_reduce_centralization(self) -> List[RefactoringOpportunity]:
        """Detect overly centralized components (bottlenecks) - with strong evidence."""
        opportunities = []

        if not self.health.centrality_metrics or not self.health.centrality_metrics.highly_central_components:
            return opportunities

        for central_comp in self.health.centrality_metrics.highly_central_components:
            comp_id = central_comp.get("component")
            in_degree = central_comp.get("in_degree", 0)

            if not comp_id or comp_id not in self.components_map:
                continue

            comp = self.components_map[comp_id]

            # Only flag as refactoring if there's supporting evidence beyond just centrality
            # Check for other risk signals
            has_coupling_risk = any(
                risk.type.value == "high_coupling" and comp_id in risk.components
                for risk in (self.health.risks or [])
            )
            has_size_issue = False
            if comp_id.startswith("module:"):
                module = next((m for m in self.analysis.modules if m.id == comp_id), None)
                if module and len(module.classes) + len(module.functions) > 10:
                    has_size_issue = True

            # Require at least one supporting signal in addition to centrality
            if not (has_coupling_risk or has_size_issue):
                # This is likely a legitimate shared component (config, utils, etc.)
                continue

            confidence = min(1.0, 0.5 + (in_degree / 20))

            opportunities.append(
                RefactoringOpportunity(
                    id=f"reduce_centralization:{comp_id}",
                    type=RefactoringType.REDUCE_CENTRALIZATION,
                    title=f"Reduce centralization: {comp.name}",
                    priority=Priority.MEDIUM,  # Downgrade from HIGH
                    severity="medium",  # Downgrade from high
                    description=f"Component {comp.name} is a centralization hotspot with {in_degree} incoming dependencies, combined with other architectural signals.",
                    rationale="Centralization combined with high coupling or large size increases architectural risk.",
                    components=[comp_id],
                    evidence=[
                        f"In-degree: {in_degree}",
                        f"High coupling: {has_coupling_risk}",
                        f"Large size: {has_size_issue}",
                        central_comp.get("reason", ""),
                    ],
                    suggested_action="Consider distributing responsibilities or introducing intermediate abstraction layers.",
                    expected_benefit="Reduced architectural bottlenecks, improved modularity.",
                    estimated_scope=ImpactLevel.MEDIUM,
                    confidence=confidence,
                )
            )

        return opportunities

    def _detect_simplify_dependency_chain(self) -> List[RefactoringOpportunity]:
        """Detect overly deep dependency chains."""
        opportunities = []

        # Use dependency depth from health metrics
        if self.health.dependency_metrics:
            max_depth = getattr(self.health.dependency_metrics, "max_dependency_depth", 0)

            if max_depth > 5:  # Deep chains
                confidence = min(1.0, 0.6 + (max_depth / 20))

                opportunities.append(
                    RefactoringOpportunity(
                        id="simplify_dependency_chain:overall",
                        type=RefactoringType.SIMPLIFY_DEPENDENCY_CHAIN,
                        title="Simplify deep dependency chains",
                        priority=Priority.MEDIUM,
                        severity="medium",
                        description=f"Architecture contains dependency chains up to {max_depth} levels deep.",
                        rationale="Deep dependency chains make code harder to trace, increase fragility, and slow development.",
                        components=list(self.components_map.keys())[:5],  # Top 5 components
                        evidence=[
                            f"Maximum dependency depth: {max_depth}",
                            f"Average dependency depth: {getattr(self.health.dependency_metrics, 'average_dependency_depth', 0):.1f}",
                        ],
                        suggested_action="Introduce facades, abstract interfaces, or skip levels where direct access is safe.",
                        expected_benefit="Simpler dependency graph, easier to trace, reduced fragility.",
                        estimated_scope=ImpactLevel.MEDIUM,
                        confidence=confidence,
                    )
                )

        return opportunities

    def _detect_review_layer_violation(self) -> List[RefactoringOpportunity]:
        """Detect layer boundary violations - only genuine violations, not normal patterns."""
        opportunities = []

        if not self.health.layer_violations:
            return opportunities

        # Group violations by source component to deduplicate
        violations_by_comp: Dict[str, List] = {}
        for violation in self.health.layer_violations:
            comp_id = violation.source_component
            if comp_id and comp_id in self.components_map:
                if comp_id not in violations_by_comp:
                    violations_by_comp[comp_id] = []
                violations_by_comp[comp_id].append(violation)

        # Expected architectural patterns - these are NOT violations
        # but legitimate layered architecture
        expected_patterns = [
            ("Presentation", "Application"),    # Routes depend on services
            ("Presentation", "Domain"),          # Routes may directly use models (common)
            ("Application", "Data"),             # Services depend on repositories
            ("Application", "Infrastructure"),   # Services depend on config/db
            ("Application", "Domain"),           # Services use models (normal)
        ]

        # Create one recommendation per component with all violations as evidence
        for comp_id, violations in violations_by_comp.items():
            comp = self.components_map[comp_id]
            source_layer = violations[0].source_layer
            target_layers = list(set(v.target_layer for v in violations))

            # Check if this component has ONLY expected patterns
            all_expected = all(
                (source_layer, target) in expected_patterns
                for target in target_layers
            )

            if all_expected:
                # This is normal layered architecture, not a violation worth flagging
                continue

            # This is a genuine violation - at least one unexpected dependency
            confidence = 0.9

            # Build evidence from all violations
            evidence = [
                f"Source layer: {source_layer}",
                f"Violated target layers: {', '.join(sorted(target_layers))}",
                f"Total violations: {len(violations)}",
            ]

            opportunities.append(
                RefactoringOpportunity(
                    id=f"review_layer_violation:{comp_id}",
                    type=RefactoringType.REVIEW_LAYER_VIOLATION,
                    title=f"Review layer violation: {source_layer}",
                    priority=Priority.MEDIUM,
                    severity="medium",
                    description=f"Component {comp.name} violates expected layer boundaries by depending on {', '.join(sorted(target_layers))}.",
                    rationale="Unexpected layer violations can indicate architectural issues worth reviewing.",
                    components=[comp_id],
                    evidence=evidence,
                    suggested_action="Review the dependencies and consider introducing abstraction layers if appropriate.",
                    expected_benefit="Clearer architectural boundaries.",
                    estimated_scope=ImpactLevel.MEDIUM,
                    confidence=confidence,
                )
            )

        return opportunities

    def _detect_separate_responsibilities(self) -> List[RefactoringOpportunity]:
        """Detect components with mixed responsibilities."""
        opportunities = []

        for component in self.architecture.components:
            # Check for mixed architectural roles
            roles_in_component = self._analyze_component_roles(component.id)

            if len(roles_in_component) > 2:
                confidence = min(1.0, 0.4 + (len(roles_in_component) / 10))

                opportunities.append(
                    RefactoringOpportunity(
                        id=f"separate_responsibilities:{component.id}",
                        type=RefactoringType.SEPARATE_RESPONSIBILITIES,
                        title=f"Separate mixed responsibilities: {component.name}",
                        priority=Priority.MEDIUM,
                        severity="medium",
                        description=f"Component {component.name} has mixed responsibilities: {', '.join(roles_in_component)}.",
                        rationale="Mixed responsibilities make components harder to test, reuse, and maintain.",
                        components=[component.id],
                        evidence=[
                            f"Distinct roles: {', '.join(roles_in_component)}",
                            f"Role count: {len(roles_in_component)}",
                        ],
                        suggested_action="Split component into focused, single-responsibility modules.",
                        expected_benefit="Improved testability, reusability, and maintainability.",
                        estimated_scope=ImpactLevel.MEDIUM,
                        confidence=confidence,
                    )
                )

        return opportunities

    def _detect_extract_shared_component(self) -> List[RefactoringOpportunity]:
        """Detect opportunities to extract shared components."""
        opportunities = []

        # Find commonly imported modules
        import_counts: Dict[str, int] = {}
        for module in self.analysis.modules:
            for imp in module.imports:
                mod_name = imp.module
                import_counts[mod_name] = import_counts.get(mod_name, 0) + 1

        # Components imported by 4+ modules are candidates
        for module_id, count in import_counts.items():
            if count >= 4 and module_id in self.components_map:
                comp = self.components_map[module_id]

                # Check if it's utility-like
                if comp.role == ArchitecturalRole.UTILITY or "util" in comp.path.lower():
                    confidence = min(1.0, 0.4 + (count / 15))

                    opportunities.append(
                        RefactoringOpportunity(
                            id=f"extract_shared:{module_id}",
                            type=RefactoringType.EXTRACT_SHARED_COMPONENT,
                            title=f"Formalize shared component: {comp.name}",
                            priority=Priority.LOW,
                            severity="low",
                            description=f"Utility component {comp.name} is imported by {count} modules.",
                            rationale="Commonly used utilities can be formalized into reusable libraries.",
                            components=[module_id],
                            evidence=[
                                f"Import count: {count}",
                                f"Role: {comp.role}",
                            ],
                            suggested_action="Formalize as a documented shared library with clear contract and versioning.",
                            expected_benefit="Better code reuse, consistent interfaces, easier maintenance.",
                            estimated_scope=ImpactLevel.LOW,
                            confidence=confidence,
                        )
                    )

        return opportunities

    def _detect_reduce_external_dependency_concentration(self) -> List[RefactoringOpportunity]:
        """Detect external dependency concentration risks."""
        opportunities = []

        if self.health.dependency_concentration_metrics:
            metrics = self.health.dependency_concentration_metrics
            concentration = metrics.external_dependency_concentration

            if concentration > 0.8:  # >80% of modules use external deps
                confidence = min(1.0, 0.5 + concentration)

                opportunities.append(
                    RefactoringOpportunity(
                        id="reduce_external_concentration:overall",
                        type=RefactoringType.REDUCE_EXTERNAL_DEPENDENCY_CONCENTRATION,
                        title="Reduce external dependency concentration",
                        priority=Priority.MEDIUM,
                        severity="medium",
                        description=f"External dependencies are concentrated in {metrics.modules_with_external_deps} modules ({concentration*100:.0f}%).",
                        rationale="Concentrated external dependencies increase fragility and lock-in.",
                        components=[],
                        evidence=[
                            f"Total external dependencies: {metrics.total_external_dependencies}",
                            f"Modules with external deps: {metrics.modules_with_external_deps}",
                            f"Concentration: {concentration*100:.1f}%",
                        ],
                        suggested_action="Introduce adapter layer(s) or facade pattern to isolate external dependencies.",
                        expected_benefit="Reduced coupling to external libraries, easier to swap implementations.",
                        estimated_scope=ImpactLevel.MEDIUM,
                        confidence=confidence,
                    )
                )

        return opportunities

    def _build_risk_map(self) -> Dict[str, List[Risk]]:
        """Build map of risks by component."""
        risk_map = {}
        if self.health.risks:
            for risk in self.health.risks:
                for comp_id in risk.components:
                    if comp_id not in risk_map:
                        risk_map[comp_id] = []
                    risk_map[comp_id].append(risk)
        return risk_map

    def _analyze_component_roles(self, component_id: str) -> Set[str]:
        """Analyze roles represented in a component."""
        roles = set()

        if component_id in self.components_map:
            comp = self.components_map[component_id]
            roles.add(comp.role.value)

            # Check if module contains multiple distinct role types
            if component_id.startswith("module:"):
                module = next((m for m in self.analysis.modules if m.id == component_id), None)
                if module:
                    # Analyze sub-components
                    for class_id in module.classes:
                        for arch_comp in self.architecture.components:
                            if arch_comp.id == class_id:
                                roles.add(arch_comp.role.value)
                    for func_id in module.functions:
                        for arch_comp in self.architecture.components:
                            if arch_comp.id == func_id:
                                roles.add(arch_comp.role.value)

        return roles

    def _estimate_loc(self, module) -> int:
        """Estimate lines of code for a module."""
        loc = 0

        # Count from classes
        for class_id in module.classes:
            cls_obj = next((c for c in self.analysis.classes if c.id == class_id), None)
            if cls_obj:
                loc += len(cls_obj.methods) * 3

        # Count from functions
        for func_id in module.functions:
            func_obj = next((f for f in self.analysis.functions if f.id == func_id), None)
            if func_obj:
                loc += getattr(func_obj, "lines_of_code", 1)

        return loc
