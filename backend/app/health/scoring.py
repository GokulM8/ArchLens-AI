"""Phase 4 Health Scoring Engine - Calculates deterministic overall health score."""

from typing import List, Dict
from app.health.schemas import (
    HealthResult,
    OverallHealth,
    HealthDimension,
    HealthRating,
    DependencyMetrics,
    CouplingMetrics,
    CentralityMetrics,
    ComplexityMetrics,
    APIMetrics,
    DependencyConcentrationMetrics,
    LayerViolation,
    Risk,
    Hotspot,
    RiskSeverity,
)


class HealthScorer:
    """Calculates deterministic health score based on architectural metrics."""

    # Health rating thresholds
    RATING_THRESHOLDS = {
        (0.90, 1.01): HealthRating.EXCELLENT,
        (0.75, 0.89): HealthRating.GOOD,
        (0.60, 0.74): HealthRating.FAIR,
        (0.40, 0.59): HealthRating.CONCERNING,
        (0.00, 0.39): HealthRating.CRITICAL,
    }

    def calculate_health_score(
        self,
        dependency_metrics: DependencyMetrics,
        coupling_metrics: CouplingMetrics,
        centrality_metrics: CentralityMetrics,
        complexity_metrics: ComplexityMetrics,
        risks: List[Risk],
        layer_violations: List[LayerViolation],
    ) -> OverallHealth:
        """Calculate overall health score from component scores."""

        # Calculate individual dimension scores
        cycle_score = self._score_cycles(dependency_metrics)
        coupling_score = self._score_coupling(coupling_metrics)
        centrality_score = self._score_centrality(centrality_metrics)
        complexity_score = self._score_complexity(complexity_metrics)
        risk_score = self._score_risks(risks)
        layer_score = self._score_layers(layer_violations)

        dimensions = [
            HealthDimension(
                name="Dependency Architecture",
                score=cycle_score,
                weight=0.30,
                factors={"cycles": 1.0 if dependency_metrics.circular_dependency_count == 0 else 0.3},
                issues=["Circular dependencies detected"] if dependency_metrics.circular_dependency_count > 0 else [],
            ),
            HealthDimension(
                name="Layer Integrity",
                score=layer_score,
                weight=0.20,
                factors={"violations": 1.0 if not layer_violations else 0.5},
                issues=["Layer boundary violations detected"] if layer_violations else [],
            ),
            HealthDimension(
                name="Coupling",
                score=coupling_score,
                weight=0.20,
                factors={"average": coupling_score},
                issues=["High coupling detected"] if coupling_metrics.high_coupling_components else [],
            ),
            HealthDimension(
                name="Complexity",
                score=complexity_score,
                weight=0.15,
                factors={"large_modules": complexity_score},
                issues=["Large modules detected"] if complexity_metrics.largest_modules else [],
            ),
            HealthDimension(
                name="Centralization",
                score=centrality_score,
                weight=0.15,
                factors={"centrality": centrality_score},
                issues=["High centrality components"] if centrality_metrics.highly_central_components else [],
            ),
        ]

        # Calculate weighted overall score
        total_weight = sum(d.weight for d in dimensions)
        weighted_score = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight > 0 else 0.5

        # Clamp to [0.0, 1.0]
        overall_score = max(0.0, min(1.0, round(weighted_score, 2)))

        # Determine rating
        rating = self._get_rating(overall_score)

        methodology = (
            "Health score calculated from five dimensions: "
            "Dependency Architecture (30%), Layer Integrity (20%), Coupling (20%), "
            "Complexity (15%), and Centralization (15%). Each dimension is scored 0.0-1.0 "
            "based on detected metrics and architectural violations."
        )

        return OverallHealth(
            score=overall_score,
            rating=rating,
            dimensions=dimensions,
            methodology=methodology,
        )

    @staticmethod
    def _score_cycles(metrics: DependencyMetrics) -> float:
        """Score based on circular dependencies."""
        if metrics.circular_dependency_count == 0:
            return 1.0
        if metrics.circular_dependency_count <= 2:
            return 0.7
        if metrics.circular_dependency_count <= 5:
            return 0.4
        return 0.2

    @staticmethod
    def _score_coupling(metrics: CouplingMetrics) -> float:
        """Score based on coupling metrics."""
        if not metrics.high_coupling_components:
            return 0.9
        if len(metrics.high_coupling_components) <= 2:
            return 0.7
        if len(metrics.high_coupling_components) <= 5:
            return 0.5
        return 0.3

    @staticmethod
    def _score_centrality(metrics: CentralityMetrics) -> float:
        """Score based on centralization metrics."""
        if not metrics.highly_central_components:
            return 0.9
        if len(metrics.highly_central_components) <= 2:
            return 0.7
        return 0.5

    @staticmethod
    def _score_complexity(metrics: ComplexityMetrics) -> float:
        """Score based on size and complexity."""
        # Check largest module size
        if metrics.largest_modules:
            largest_loc = metrics.largest_modules[0].get("lines_of_code", 0)
            if largest_loc < 300:
                return 0.95
            if largest_loc < 500:
                return 0.8
            if largest_loc < 1000:
                return 0.6
            return 0.3
        return 0.8

    @staticmethod
    def _score_risks(risks: List[Risk]) -> float:
        """Score based on detected risks."""
        if not risks:
            return 0.95

        critical_count = sum(1 for r in risks if r.severity == RiskSeverity.CRITICAL)
        high_count = sum(1 for r in risks if r.severity == RiskSeverity.HIGH)
        medium_count = sum(1 for r in risks if r.severity == RiskSeverity.MEDIUM)

        penalty = critical_count * 0.3 + high_count * 0.15 + medium_count * 0.05
        return max(0.0, 0.95 - penalty)

    @staticmethod
    def _score_layers(violations: List[LayerViolation]) -> float:
        """Score based on layer violations."""
        if not violations:
            return 1.0

        critical_count = sum(1 for v in violations if v.severity == RiskSeverity.CRITICAL)
        high_count = sum(1 for v in violations if v.severity == RiskSeverity.HIGH)
        medium_count = sum(1 for v in violations if v.severity == RiskSeverity.MEDIUM)

        penalty = critical_count * 0.3 + high_count * 0.15 + medium_count * 0.05
        return max(0.0, 1.0 - penalty)

    @staticmethod
    def _get_rating(score: float) -> HealthRating:
        """Get health rating based on score."""
        for (min_score, max_score), rating in HealthScorer.RATING_THRESHOLDS.items():
            if min_score <= score < max_score:
                return rating
        return HealthRating.CRITICAL
