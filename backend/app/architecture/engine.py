"""ArchitectureInferenceEngine orchestrator for ArchLens AI Phase 3.

Transforms Phase 1 AnalysisResult and Phase 2 NetworkX MultiDiGraph into ArchitectureResult.
"""

from __future__ import annotations

from typing import Optional, Dict, List
import networkx as nx

from app.models.schemas import AnalysisResult
from app.graph.graph_builder import GraphBuilder
from app.architecture.schemas import (
    ArchitectureResult,
    ArchitectureSummary,
    ArchitectureComponent,
)
from app.architecture.classifier import ArchitectureClassifier
from app.architecture.layers import LayerMapper
from app.architecture.entry_points import EntryPointDetector
from app.architecture.patterns import PatternDetector
from app.architecture.relationships import RelationshipExtractor


class ArchitectureInferenceEngine:
    """Orchestrates deterministic Phase 3 rule-based architecture intelligence."""

    def __init__(
        self,
        analysis_result: AnalysisResult,
        graph: Optional[nx.MultiDiGraph] = None,
    ):
        self.analysis_result = analysis_result
        self.graph = graph if graph is not None else GraphBuilder(analysis_result).build()

    def analyze(self) -> ArchitectureResult:
        """Run the full architecture inference pipeline.

        Returns:
            Structured ArchitectureResult containing components, layers, entry points,
            patterns, relationships, and summary.
        """
        # 1. Classify components into Architectural Roles with evidence & confidence
        classifier = ArchitectureClassifier(self.analysis_result, self.graph)
        components: List[ArchitectureComponent] = classifier.classify_all()

        # 2. Map components into Architectural Layers
        layers = LayerMapper.build_layer_groups(components)

        # 3. Discover Entry Points
        entry_detector = EntryPointDetector(self.analysis_result)
        entry_points = entry_detector.discover()

        # 4. Detect Architectural Patterns
        pattern_detector = PatternDetector(components, layers, self.graph)
        patterns = pattern_detector.detect_all()

        # 5. Extract High-Level Architectural Relationships
        relationship_extractor = RelationshipExtractor(components, self.graph)
        relationships = relationship_extractor.extract_all()

        # 6. Build Summary Statistics
        role_counts: Dict[str, int] = {}
        for c in components:
            role_counts[c.role.value] = role_counts.get(c.role.value, 0) + 1

        layer_counts: Dict[str, int] = {}
        for l in layers:
            layer_counts[l.name.value] = len(l.components)

        summary = ArchitectureSummary(
            component_count=len(components),
            roles=role_counts,
            layers=layer_counts,
            entry_point_count=len(entry_points),
            pattern_count=len(patterns),
        )

        return ArchitectureResult(
            schema_version="1.0",
            repository_name=self.analysis_result.repository.name,
            components=components,
            layers=layers,
            entry_points=entry_points,
            patterns=patterns,
            relationships=relationships,
            summary=summary,
        )
