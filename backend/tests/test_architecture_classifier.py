"""Unit tests for Phase 3 Role Classifier."""

import pytest
from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.architecture.classifier import ArchitectureClassifier
from app.architecture.schemas import ArchitecturalRole, ArchitecturalLayer


def test_classifier_fastapi_project():
    analyzer = RepositoryAnalyzer("../examples/fastapi_project")
    analysis_result = analyzer.analyze()
    graph = GraphBuilder(analysis_result).build()

    classifier = ArchitectureClassifier(analysis_result, graph)
    components = classifier.classify_all()

    assert len(components) > 0
    role_map = {c.name: c.role for c in components}

    # Verify classification of fastapi_project components
    assert role_map.get("main") in (ArchitecturalRole.ROUTE, ArchitecturalRole.CONFIGURATION, ArchitecturalRole.UTILITY)
    assert role_map.get("products") == ArchitecturalRole.ROUTE
    assert role_map.get("users") == ArchitecturalRole.ROUTE
    assert role_map.get("predictions") == ArchitecturalRole.ROUTE
    assert role_map.get("product_service") == ArchitecturalRole.SERVICE
    assert role_map.get("user_service") == ArchitecturalRole.SERVICE
    assert role_map.get("prediction_service") == ArchitecturalRole.SERVICE
    assert role_map.get("product") == ArchitecturalRole.MODEL
    assert role_map.get("user") == ArchitecturalRole.MODEL
    assert role_map.get("prediction") == ArchitecturalRole.MODEL
    assert role_map.get("database") == ArchitecturalRole.DATABASE
    assert role_map.get("auth") == ArchitecturalRole.AUTHENTICATION


def test_classifier_layer_mapping():
    analyzer = RepositoryAnalyzer("../examples/fastapi_project")
    analysis_result = analyzer.analyze()
    graph = GraphBuilder(analysis_result).build()

    classifier = ArchitectureClassifier(analysis_result, graph)
    components = classifier.classify_all()

    for c in components:
        if c.role == ArchitecturalRole.ROUTE:
            assert c.layer == ArchitecturalLayer.PRESENTATION
        elif c.role == ArchitecturalRole.SERVICE:
            assert c.layer == ArchitecturalLayer.APPLICATION
        elif c.role == ArchitecturalRole.DATABASE:
            assert c.layer == ArchitecturalLayer.INFRASTRUCTURE
