"""Phase 5 Evolution Inference Engine - Main Orchestrator."""

import networkx as nx

from app.models.schemas import AnalysisResult
from app.architecture.schemas import ArchitectureResult
from app.health.schemas import HealthResult
from app.evolution.schemas import EvolutionResult, EvolutionSummary
from app.evolution.recommendations import RecommendationDetector
from app.evolution.impact import ImpactAnalyzer
from app.evolution.prioritization import PrioritizationEngine


class EvolutionInferenceEngine:
    """Orchestrates Phase 5 architecture evolution analysis."""

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

    def analyze(self) -> EvolutionResult:
        """Execute complete Phase 5 evolution analysis."""
        # Detect refactoring opportunities
        detector = RecommendationDetector(
            self.analysis,
            self.graph,
            self.architecture,
            self.health,
        )
        opportunities = detector.detect_all_opportunities()

        # Analyze impact for each opportunity
        impact_analyzer = ImpactAnalyzer(
            self.analysis,
            self.graph,
            self.architecture,
        )
        impact_map = impact_analyzer.analyze_batch_impact(opportunities)

        # Prioritize refactoring opportunities
        prioritizer = PrioritizationEngine(
            self.analysis,
            self.graph,
            self.architecture,
            self.health,
        )
        prioritized = prioritizer.prioritize_refactorings(opportunities)
        priority_summary = prioritizer.calculate_summary(opportunities)

        # Build evolution summary
        summary = self._build_summary(opportunities, impact_map, priority_summary)

        # Build dependency insights
        insights = self._build_dependency_insights()

        return EvolutionResult(
            repository_name=self.architecture.repository_name,
            refactoring_opportunities=prioritized,
            dependency_insights=insights,
            impact_analysis=impact_map,
            priorities=priority_summary,
            summary=summary,
        )

    def _build_summary(self, opportunities, impact_map, priority_summary) -> EvolutionSummary:
        """Build evolution analysis summary."""
        if not opportunities:
            return EvolutionSummary(
                refactoring_opportunities=0,
                total_affected_components=0,
                total_affected_dependencies=0,
                average_priority="low",
                average_confidence=0.0,
                investigation_recommendation="No significant refactoring opportunities detected.",
            )

        # Calculate affected components across all opportunities
        all_affected = set()
        for opp in opportunities:
            all_affected.update(opp.components)

        # Calculate affected dependencies
        total_deps = 0
        for impact in impact_map.values():
            total_deps += impact.affected_dependencies

        # Calculate average confidence
        avg_confidence = (
            sum(opp.confidence for opp in opportunities) / len(opportunities)
            if opportunities
            else 0.0
        )

        # Determine average priority
        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        avg_priority_score = (
            sum(priority_order.get(opp.priority.value, 0) for opp in opportunities)
            / len(opportunities)
            if opportunities
            else 0.0
        )

        priority_map = {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "low"}
        avg_priority = priority_map.get(int(round(avg_priority_score)), "medium")

        # Recommendation based on priority distribution
        if priority_summary.critical_count > 0:
            recommendation = f"Address {priority_summary.critical_count} critical issues immediately."
        elif priority_summary.high_count >= 3:
            recommendation = f"Plan refactoring for {priority_summary.high_count} high-priority opportunities."
        else:
            recommendation = "Schedule review of medium-priority improvements."

        return EvolutionSummary(
            refactoring_opportunities=len(opportunities),
            total_affected_components=len(all_affected),
            total_affected_dependencies=total_deps,
            average_priority=avg_priority,
            average_confidence=round(avg_confidence, 2),
            investigation_recommendation=recommendation,
        )

    def _build_dependency_insights(self):
        """Build dependency insights from health analysis."""
        from app.evolution.schemas import DependencyInsight

        most_connected = []
        if self.health.centrality_metrics:
            for comp in self.health.centrality_metrics.highly_central_components[:5]:
                most_connected.append({
                    "component": comp.get("component", "unknown"),
                    "component_name": comp.get("component_name", "unknown"),
                    "in_degree": comp.get("in_degree", 0),
                })

        # Deepest dependency paths
        deepest_paths = []
        if self.health.dependency_metrics:
            deepest_paths.append({
                "max_depth": getattr(
                    self.health.dependency_metrics, "max_dependency_depth", 0
                ),
                "avg_depth": getattr(
                    self.health.dependency_metrics, "average_dependency_depth", 0
                ),
            })

        # Most affected components (by risk count)
        most_affected = []
        if self.health.risks:
            risk_count_by_comp = {}
            for risk in self.health.risks:
                for comp_id in risk.components:
                    risk_count_by_comp[comp_id] = risk_count_by_comp.get(comp_id, 0) + 1

            # Top 5
            for comp_id, count in sorted(
                risk_count_by_comp.items(), key=lambda x: x[1], reverse=True
            )[:5]:
                most_affected.append({
                    "component": comp_id,
                    "risk_count": count,
                })

        # Critical dependency edges
        critical_edges = []
        if self.health.risks:
            for risk in self.health.risks:
                if risk.severity == "critical" and len(risk.components) >= 2:
                    critical_edges.append({
                        "components": risk.components[:2],
                        "risk_type": risk.type.value,
                        "severity": risk.severity,
                    })

        return DependencyInsight(
            most_connected_components=most_connected,
            deepest_dependency_paths=deepest_paths,
            most_affected_components=most_affected,
            critical_dependency_edges=critical_edges,
        )
