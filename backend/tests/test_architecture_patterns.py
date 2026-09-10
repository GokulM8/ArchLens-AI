"""Unit tests for Phase 3 Architectural Pattern Detection."""

import pytest
from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.architecture.classifier import ArchitectureClassifier
from app.architecture.layers import LayerMapper
from app.architecture.patterns import PatternDetector


def test_pattern_detection_fastapi_project():
    analyzer = RepositoryAnalyzer("../examples/fastapi_project")
    analysis_result = analyzer.analyze()
    graph = GraphBuilder(analysis_result).build()

    classifier = ArchitectureClassifier(analysis_result, graph)
    components = classifier.classify_all()
    layers = LayerMapper.build_layer_groups(components)

    pattern_detector = PatternDetector(components, layers, graph)
    patterns = pattern_detector.detect_all()

    assert len(patterns) >= 1
    pattern_names = [p.name for p in patterns]

    # Service-Repository, Layered, and API Service patterns should be detected
    assert "service_repository_pattern" in pattern_names or "api_service_architecture" in pattern_names or "layered_architecture" in pattern_names
