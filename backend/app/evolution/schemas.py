"""Pydantic v2 schemas for ArchLens AI Phase 5 Architecture Evolution & Refactoring Intelligence."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List
from pydantic import BaseModel, Field


class RefactoringType(str, Enum):
    """Types of architectural refactoring opportunities."""
    SPLIT_LARGE_MODULE = "split_large_module"
    REDUCE_HIGH_COUPLING = "reduce_high_coupling"
    BREAK_CIRCULAR_DEPENDENCY = "break_circular_dependency"
    REDUCE_CENTRALIZATION = "reduce_centralization"
    SIMPLIFY_DEPENDENCY_CHAIN = "simplify_dependency_chain"
    REVIEW_LAYER_VIOLATION = "review_layer_violation"
    SEPARATE_RESPONSIBILITIES = "separate_responsibilities"
    EXTRACT_SHARED_COMPONENT = "extract_shared_component"
    REDUCE_EXTERNAL_DEPENDENCY_CONCENTRATION = "reduce_external_dependency_concentration"


class Priority(str, Enum):
    """Priority levels for refactoring."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImpactLevel(str, Enum):
    """Impact levels for proposed changes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RefactoringOpportunity(BaseModel):
    """A detected refactoring opportunity."""
    id: str = Field(description="Unique refactoring identifier")
    type: RefactoringType = Field(description="Type of refactoring")
    title: str = Field(description="Short title")
    priority: Priority = Field(description="Priority level")
    severity: str = Field(description="Severity level")
    description: str = Field(description="Detailed description")
    rationale: str = Field(description="Why this refactoring is recommended")
    components: List[str] = Field(description="Affected component IDs")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    suggested_action: str = Field(description="What action to take")
    expected_benefit: str = Field(description="Expected benefit")
    estimated_scope: ImpactLevel = Field(description="Estimated scope of change")
    confidence: float = Field(description="Confidence score (0.0-1.0)")


class DependencyInsight(BaseModel):
    """Architectural insight about dependencies."""
    most_connected_components: List[Dict] = Field(default_factory=list)
    deepest_dependency_paths: List[Dict] = Field(default_factory=list)
    most_affected_components: List[Dict] = Field(default_factory=list)
    critical_dependency_edges: List[Dict] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    """Analysis of impact for a proposed refactoring."""
    directly_affected_components: List[str] = Field(default_factory=list)
    indirectly_affected_components: List[str] = Field(default_factory=list)
    affected_layers: List[str] = Field(default_factory=list)
    affected_routes: int = Field(default=0)
    affected_dependencies: int = Field(default=0)
    total_impact_count: int = Field(default=0)
    impact_level: ImpactLevel = Field(default=ImpactLevel.LOW)


class RefactoringPrioritySummary(BaseModel):
    """Summary of refactoring priorities."""
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    total_count: int = Field(default=0)


class EvolutionSummary(BaseModel):
    """Summary of evolution analysis."""
    refactoring_opportunities: int = Field(default=0)
    total_affected_components: int = Field(default=0)
    total_affected_dependencies: int = Field(default=0)
    average_priority: str = Field(default="medium")
    average_confidence: float = Field(default=0.5)
    investigation_recommendation: str = Field(default="")


class EvolutionResult(BaseModel):
    """Complete architecture evolution analysis result."""
    schema_version: str = Field(default="1.0")
    repository_name: str = Field(description="Repository name")
    refactoring_opportunities: List[RefactoringOpportunity] = Field(default_factory=list)
    dependency_insights: DependencyInsight = Field(default_factory=DependencyInsight)
    impact_analysis: Dict[str, ImpactAnalysis] = Field(default_factory=dict)
    priorities: RefactoringPrioritySummary = Field(default_factory=RefactoringPrioritySummary)
    summary: EvolutionSummary = Field(default_factory=EvolutionSummary)
