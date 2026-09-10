"""ArchLens AI Phase 3 Architecture Intelligence Package."""

from app.architecture.schemas import (
    ArchitecturalRole,
    ArchitecturalLayer,
    EvidenceType,
    Evidence,
    ArchitectureComponent,
    ArchitectureLayerInfo,
    EntryPoint,
    ArchitecturePattern,
    ArchitectureRelationship,
    ArchitectureSummary,
    ArchitectureResult,
)
from app.architecture.classifier import ArchitectureClassifier
from app.architecture.layers import LayerMapper
from app.architecture.entry_points import EntryPointDetector
from app.architecture.patterns import PatternDetector
from app.architecture.serializer import ArchitectureSerializer
from app.architecture.engine import ArchitectureInferenceEngine

__all__ = [
    "ArchitecturalRole",
    "ArchitecturalLayer",
    "EvidenceType",
    "Evidence",
    "ArchitectureComponent",
    "ArchitectureLayerInfo",
    "EntryPoint",
    "ArchitecturePattern",
    "ArchitectureRelationship",
    "ArchitectureSummary",
    "ArchitectureResult",
    "ArchitectureClassifier",
    "LayerMapper",
    "EntryPointDetector",
    "PatternDetector",
    "ArchitectureSerializer",
    "ArchitectureInferenceEngine",
]
