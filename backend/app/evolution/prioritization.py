"""Phase 5 Prioritization & Scoring Engine."""

from typing import List
import networkx as nx

from app.models.schemas import AnalysisResult
from app.architecture.schemas import ArchitectureResult
from app.health.schemas import HealthResult
from app.evolution.schemas import (
    RefactoringOpportunity,
    Priority,
    RefactoringPrioritySummary,
)


class PrioritizationEngine:
    """Scores and prioritizes refactoring opportunities deterministically."""

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

    def prioritize_refactorings(
        self, refactorings: List[RefactoringOpportunity]
    ) -> List[RefactoringOpportunity]:
        """Sort refactorings by priority deterministically."""
        # Score each refactoring
        scored = [(ref, self._calculate_priority_score(ref)) for ref in refactorings]

        # Sort by score (descending) then by ID for determinism
        scored.sort(key=lambda x: (-x[1], x[0].id))

        return [ref for ref, _ in scored]

    def _calculate_priority_score(self, refactoring: RefactoringOpportunity) -> float:
        """Calculate a deterministic priority score (0.0-1.0)."""
        score = 0.0

        # Priority weight (CRITICAL=0.4, HIGH=0.3, MEDIUM=0.2, LOW=0.1)
        priority_weights = {
            Priority.CRITICAL: 0.4,
            Priority.HIGH: 0.3,
            Priority.MEDIUM: 0.2,
            Priority.LOW: 0.1,
        }
        score += priority_weights.get(refactoring.priority, 0.1)

        # Severity weight (high=0.3, medium=0.2, low=0.1)
        severity_weights = {"critical": 0.3, "high": 0.3, "medium": 0.2, "low": 0.1}
        score += severity_weights.get(refactoring.severity, 0.1)

        # Component impact (more components = higher score, capped at 0.2)
        impact_component_count = min(1.0, len(refactoring.components) / 10)
        score += 0.2 * impact_component_count

        # Scope weight (CRITICAL=0.15, HIGH=0.1, MEDIUM=0.05, LOW=0.0)
        scope_weights = {
            "critical": 0.15,
            "high": 0.1,
            "medium": 0.05,
            "low": 0.0,
        }
        score += scope_weights.get(refactoring.estimated_scope.value, 0.0)

        # Risk-based boost: if the component appears in health risks
        risk_boost = self._calculate_risk_boost(refactoring)
        score += 0.15 * risk_boost

        # Centrality boost: if the component is highly central
        centrality_boost = self._calculate_centrality_boost(refactoring)
        score += 0.1 * centrality_boost

        # Clamp to [0.0, 1.0]
        return min(1.0, max(0.0, score))

    def _calculate_risk_boost(self, refactoring: RefactoringOpportunity) -> float:
        """Boost score if refactoring addresses health risks."""
        if not self.health.risks:
            return 0.0

        matching_risks = []
        for risk in self.health.risks:
            for comp_id in refactoring.components:
                if comp_id in risk.components:
                    matching_risks.append(risk)
                    break

        if not matching_risks:
            return 0.0

        # More matching risks = higher boost
        risk_severity_weights = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.6,
            "low": 0.3,
            "info": 0.1,
        }

        total_weight = sum(
            risk_severity_weights.get(risk.severity, 0.5) for risk in matching_risks
        )
        avg_weight = total_weight / len(matching_risks)

        return min(1.0, avg_weight)

    def _calculate_centrality_boost(self, refactoring: RefactoringOpportunity) -> float:
        """Boost score if refactoring affects central components."""
        if not self.health.centrality_metrics:
            return 0.0

        central_comps = {
            comp.get("component")
            for comp in self.health.centrality_metrics.highly_central_components
        }

        matching = sum(1 for comp_id in refactoring.components if comp_id in central_comps)

        if matching == 0:
            return 0.0

        # More central components affected = higher boost
        return min(1.0, matching / len(refactoring.components))

    def calculate_summary(
        self, refactorings: List[RefactoringOpportunity]
    ) -> RefactoringPrioritySummary:
        """Calculate summary of refactoring priorities."""
        priority_counts = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 0,
            Priority.MEDIUM: 0,
            Priority.LOW: 0,
        }

        for ref in refactorings:
            priority_counts[ref.priority] += 1

        return RefactoringPrioritySummary(
            critical_count=priority_counts[Priority.CRITICAL],
            high_count=priority_counts[Priority.HIGH],
            medium_count=priority_counts[Priority.MEDIUM],
            low_count=priority_counts[Priority.LOW],
            total_count=len(refactorings),
        )

    def get_top_n_refactorings(
        self, refactorings: List[RefactoringOpportunity], n: int = 5
    ) -> List[RefactoringOpportunity]:
        """Get top N refactorings by priority."""
        prioritized = self.prioritize_refactorings(refactorings)
        return prioritized[:n]
