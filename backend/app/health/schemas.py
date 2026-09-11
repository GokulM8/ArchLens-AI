"""Pydantic v2 data models for ArchLens AI Phase 4 Architecture Health & Risk Intelligence.

Defines schemas for health metrics, risks, hotspots, and the top-level health.json structure.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    """Risk severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskType(str, Enum):
    """Types of architectural risks detected."""
    CIRCULAR_DEPENDENCY = "circular_dependency"
    LAYER_VIOLATION = "layer_violation"
    HIGH_COUPLING = "high_coupling"
    HIGH_CENTRALITY = "high_centrality"
    DEEP_DEPENDENCY_CHAIN = "deep_dependency_chain"
    LARGE_MODULE = "large_module"
    LARGE_CLASS = "large_class"
    LARGE_FUNCTION = "large_function"
    API_CONCENTRATION = "api_concentration"
    EXTERNAL_DEPENDENCY_CONCENTRATION = "external_dependency_concentration"
    ARCHITECTURAL_HOTSPOT = "architectural_hotspot"


class HealthRating(str, Enum):
    """Health rating categories based on score."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    CONCERNING = "concerning"
    CRITICAL = "critical"


class CircularDependency(BaseModel):
    """A detected circular dependency cycle."""
    components: List[str] = Field(description="Module IDs forming the cycle")
    length: int = Field(description="Number of components in the cycle")
    evidence: str = Field(description="Human-readable cycle representation")


class DependencyMetrics(BaseModel):
    """Module dependency metrics."""
    total_dependencies: int = Field(description="Total dependency relationships")
    circular_dependency_count: int = Field(description="Number of detected cycles")
    circular_dependencies: List[CircularDependency] = Field(
        default_factory=list,
        description="Details of detected cycles"
    )
    max_dependency_depth: int = Field(description="Maximum depth of dependency chain")
    average_dependency_depth: float = Field(description="Average dependency chain depth")


class CouplingMetrics(BaseModel):
    """Coupling analysis results."""
    total_components: int = Field(description="Total architectural components")
    average_coupling: float = Field(description="Average in+out degree")
    median_coupling: float = Field(description="Median in+out degree")
    max_coupling: int = Field(description="Maximum in+out degree")
    high_coupling_components: List[Dict] = Field(
        default_factory=list,
        description="Components with above-average coupling"
    )


class CentralityMetrics(BaseModel):
    """Centralization and bottleneck analysis."""
    highly_central_components: List[Dict] = Field(
        default_factory=list,
        description="Components with high degree centrality"
    )


class ComplexityMetrics(BaseModel):
    """Size and complexity indicators."""
    largest_modules: List[Dict] = Field(
        default_factory=list,
        description="Largest modules by lines of code"
    )
    largest_classes: List[Dict] = Field(
        default_factory=list,
        description="Largest classes by method count"
    )
    largest_functions: List[Dict] = Field(
        default_factory=list,
        description="Longest functions by line count"
    )


class APIMetrics(BaseModel):
    """API surface analysis."""
    total_routes: int = Field(description="Total HTTP routes")
    routes_per_module: Dict[str, int] = Field(
        default_factory=dict,
        description="Route count per module"
    )
    http_method_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of HTTP methods"
    )


class DependencyConcentrationMetrics(BaseModel):
    """External dependency concentration."""
    total_external_dependencies: int = Field(description="Count of external packages")
    modules_with_external_deps: int = Field(description="Modules using external packages")
    external_dependency_concentration: float = Field(
        description="Concentration ratio (0.0-1.0)"
    )


class LayerViolation(BaseModel):
    """A detected layer boundary violation."""
    source_component: str = Field(description="Source module ID")
    target_component: str = Field(description="Target module ID")
    source_layer: str = Field(description="Source component's layer")
    target_layer: str = Field(description="Target component's layer")
    severity: RiskSeverity = Field(description="Severity of the violation")
    reason: str = Field(description="Why this is a violation")


class Risk(BaseModel):
    """Detected architectural risk."""
    id: str = Field(description="Unique risk identifier")
    type: RiskType = Field(description="Type of risk")
    severity: RiskSeverity = Field(description="Severity level")
    title: str = Field(description="Short risk title")
    description: str = Field(description="Detailed description")
    components: List[str] = Field(default_factory=list, description="Affected component IDs")
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting the risk")
    metric: Optional[str] = Field(default=None, description="Associated metric value")
    recommendation: str = Field(description="Recommended action")


class Hotspot(BaseModel):
    """An architectural hotspot (component with multiple risk signals)."""
    component: str = Field(description="Component ID")
    component_name: str = Field(description="Component display name")
    signals: List[str] = Field(description="List of warning signals")
    severity: RiskSeverity = Field(description="Overall severity")
    description: str = Field(description="Hotspot description")


class HealthDimension(BaseModel):
    """A dimension of architecture health."""
    name: str = Field(description="Dimension name")
    score: float = Field(description="Dimension score (0.0-1.0)")
    weight: float = Field(description="Weight in overall score calculation")
    factors: Dict[str, float] = Field(
        default_factory=dict,
        description="Component scores contributing to this dimension"
    )
    issues: List[str] = Field(default_factory=list, description="Issues in this dimension")


class OverallHealth(BaseModel):
    """Overall health assessment."""
    score: float = Field(description="Overall health score (0.0-1.0)")
    rating: HealthRating = Field(description="Health rating category")
    dimensions: List[HealthDimension] = Field(
        description="Individual health dimensions"
    )
    methodology: str = Field(
        description="Description of how the score was calculated"
    )


class HealthResult(BaseModel):
    """Complete architecture health analysis result."""
    schema_version: str = Field(default="1.0", description="Schema version")
    repository_name: str = Field(description="Repository name")
    analysis_timestamp: Optional[str] = Field(default=None, description="ISO timestamp")

    # Health assessment
    overall_health: OverallHealth = Field(description="Overall health summary")

    # Metrics
    dependency_metrics: DependencyMetrics = Field(description="Dependency analysis")
    coupling_metrics: CouplingMetrics = Field(description="Coupling analysis")
    centrality_metrics: CentralityMetrics = Field(description="Centralization analysis")
    complexity_metrics: ComplexityMetrics = Field(description="Size and complexity metrics")
    api_metrics: APIMetrics = Field(description="API surface metrics")
    dependency_concentration_metrics: DependencyConcentrationMetrics = Field(
        description="External dependency concentration"
    )

    # Risks and hotspots
    layer_violations: List[LayerViolation] = Field(
        default_factory=list,
        description="Detected layer boundary violations"
    )
    risks: List[Risk] = Field(default_factory=list, description="Detected architectural risks")
    hotspots: List[Hotspot] = Field(default_factory=list, description="Architectural hotspots")

    # Summary
    risk_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of risks by severity"
    )
