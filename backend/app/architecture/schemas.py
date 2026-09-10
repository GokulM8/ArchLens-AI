"""Pydantic v2 data models for ArchLens AI Phase 3 Architecture Intelligence.

Defines schemas for components, evidence, layers, entry points, patterns,
relationships, and the top-level architecture.json structure.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ArchitecturalRole(str, Enum):
    """Supported architectural roles for code components."""
    ROUTE = "route"
    SERVICE = "service"
    REPOSITORY = "repository"
    MODEL = "model"
    DATABASE = "database"
    UTILITY = "utility"
    CONFIGURATION = "configuration"
    MIDDLEWARE = "middleware"
    AUTHENTICATION = "authentication"
    EXTERNAL_SERVICE = "external_service"
    ML = "ml"
    TEST = "test"
    UNKNOWN = "unknown"


class ArchitecturalLayer(str, Enum):
    """High-level architectural layers."""
    PRESENTATION = "Presentation"
    APPLICATION = "Application"
    DOMAIN = "Domain"
    DATA = "Data"
    INFRASTRUCTURE = "Infrastructure"
    CROSS_CUTTING = "Cross-Cutting"
    EXTERNAL = "External"
    TESTING = "Testing"
    UNKNOWN = "Unknown"


class EvidenceType(str, Enum):
    """Categories of classification evidence."""
    PATH = "path"
    MODULE_NAME = "module_name"
    DECORATOR = "decorator"
    IMPORTS = "imports"
    IMPORTED_BY = "imported_by"
    STRUCTURE = "structure"
    DEPENDENCY = "dependency"
    GRAPH = "graph"
    ROUTE = "route"
    FRAMEWORK = "framework"


class Evidence(BaseModel):
    """A single piece of evidence supporting an architectural inference."""
    type: EvidenceType = Field(description="Type of evidence observed")
    description: str = Field(description="Human-readable description of the evidence")
    weight: float = Field(default=0.10, description="Numerical contribution to confidence score")
    source_id: Optional[str] = Field(default=None, description="Optional entity or node ID source")


class ArchitectureComponent(BaseModel):
    """Inferred architectural component (module or file level)."""
    id: str = Field(description="Entity ID matching analysis.json or graph.json")
    name: str = Field(description="Display name or module/file name")
    path: str = Field(description="Relative file path")
    role: ArchitecturalRole = Field(description="Inferred primary architectural role")
    layer: ArchitecturalLayer = Field(description="Mapped architectural layer")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    evidence: List[Evidence] = Field(default_factory=list, description="Traceable evidence list")
    alternative_roles: List[ArchitecturalRole] = Field(
        default_factory=list,
        description="Secondary roles supported by partial evidence"
    )


class ArchitectureLayerInfo(BaseModel):
    """Information about an architectural layer and its components."""
    name: ArchitecturalLayer = Field(description="Layer name")
    components: List[str] = Field(default_factory=list, description="IDs of components in this layer")
    description: str = Field(description="Description of the layer's responsibility")


class EntryPoint(BaseModel):
    """An application entry point."""
    id: str = Field(description="Component/module ID")
    path: str = Field(description="Relative path")
    name: str = Field(description="Entry point label")
    entry_type: str = Field(description="Type of entry point (e.g., 'main_script', 'fastapi_app', 'cli')")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    evidence: List[Evidence] = Field(default_factory=list, description="Supporting evidence")


class ArchitecturePattern(BaseModel):
    """A detected architectural pattern."""
    name: str = Field(description="Pattern identifier (e.g., 'service_repository_pattern')")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence strings")
    description: str = Field(description="Explanation of the detected pattern")


class ArchitectureRelationship(BaseModel):
    """A high-level relationship between architectural components."""
    source_id: str = Field(description="Source component ID")
    target_id: str = Field(description="Target component ID")
    relationship_type: str = Field(description="Type of relationship (e.g., 'DEPENDS_ON', 'CALLS')")
    source_role: ArchitecturalRole = Field(description="Role of source component")
    target_role: ArchitecturalRole = Field(description="Role of target component")


class ArchitectureSummary(BaseModel):
    """Summary statistics for the architecture inference."""
    component_count: int = 0
    roles: Dict[str, int] = Field(default_factory=dict)
    layers: Dict[str, int] = Field(default_factory=dict)
    entry_point_count: int = 0
    pattern_count: int = 0


class ArchitectureResult(BaseModel):
    """Top-level output schema for architecture.json."""
    schema_version: str = Field(default="1.0", description="Schema version for forwards compatibility")
    repository_name: str = Field(description="Analyzed repository name")
    components: List[ArchitectureComponent] = Field(default_factory=list)
    layers: List[ArchitectureLayerInfo] = Field(default_factory=list)
    entry_points: List[EntryPoint] = Field(default_factory=list)
    patterns: List[ArchitecturePattern] = Field(default_factory=list)
    relationships: List[ArchitectureRelationship] = Field(default_factory=list)
    summary: ArchitectureSummary = Field(default_factory=ArchitectureSummary)
