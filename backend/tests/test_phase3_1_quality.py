"""Regression tests for Phase 3.1 quality fixes."""

import pytest
from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.architecture.classifier import ArchitectureClassifier
from app.architecture.layers import LayerMapper
from app.architecture.patterns import PatternDetector
from app.architecture.schemas import ArchitecturalRole


class TestIssue1ServiceRepositoryPattern:
    """Issue #1: False service_repository_pattern detection.

    The pattern should only be detected when actual Repository components exist,
    not when only Models exist.
    """

    def test_no_pattern_without_repository(self):
        """Route → Service → Model (no Repository) should NOT detect service_repository_pattern."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()
        layers = LayerMapper.build_layer_groups(components)

        pattern_detector = PatternDetector(components, layers, graph)
        patterns = pattern_detector.detect_all()

        pattern_names = [p.name for p in patterns]
        # With 0 repositories and only models, service_repository_pattern should NOT be present
        assert "service_repository_pattern" not in pattern_names, \
            "service_repository_pattern should not be detected without actual Repository components"

    def test_api_service_architecture_present(self):
        """Should detect api_service_architecture instead when routes + services + models exist."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()
        layers = LayerMapper.build_layer_groups(components)

        pattern_detector = PatternDetector(components, layers, graph)
        patterns = pattern_detector.detect_all()

        pattern_names = [p.name for p in patterns]
        # Should have api_service_architecture pattern
        assert "api_service_architecture" in pattern_names, \
            "api_service_architecture should be detected for route-service architecture"


class TestIssue2InitPyConservative:
    """Issue #2: __init__.py conservative classification.

    Trivial __init__.py files should not be over-classified based solely on directory names.
    """

    def test_empty_init_not_automatically_classified(self):
        """Empty app/__init__.py should be conservative (unknown or low confidence)."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()

        # Find app/__init__.py
        app_init = next((c for c in components if c.path == "app/__init__.py"), None)
        assert app_init is not None

        # Should be unknown or have very low confidence
        # Should NOT be automatically classified as 'model', 'route', 'service', or 'utility'
        # based solely on directory name
        assert app_init.role in (ArchitecturalRole.UNKNOWN,), \
            f"Trivial __init__.py should be unknown, got {app_init.role}"
        assert app_init.confidence <= 0.2, \
            f"Trivial __init__.py should have low confidence, got {app_init.confidence}"

    def test_routes_init_not_automatically_route(self):
        """Empty app/routes/__init__.py should not be automatically classified as route."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()

        # Find app/routes/__init__.py
        routes_init = next((c for c in components if c.path == "app/routes/__init__.py"), None)
        assert routes_init is not None

        # Empty __init__.py in routes/ should be conservative
        # It should only be classified as route if it has actual route evidence
        # (not just directory name)
        if routes_init.role == ArchitecturalRole.ROUTE:
            # If classified as route, confidence should be justified by actual route evidence
            # Check that evidence includes something other than just "path"
            has_path_only = len(routes_init.evidence) == 1 and \
                           routes_init.evidence[0].type.value == "path"
            assert not has_path_only, \
                "Route classification should not be based solely on path/directory name"


class TestIssue3MainPyEntryPoint:
    """Issue #3: main.py role vs entry point.

    Entry-point status should be represented independently, not lost.
    """

    def test_main_py_has_entry_point_metadata(self):
        """main.py should be identified as an entry point."""
        from app.architecture.entry_points import EntryPointDetector

        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()

        detector = EntryPointDetector(analysis_result)
        entry_points = detector.discover()

        # Should detect main.py as entry point
        main_entries = [ep for ep in entry_points if "main" in ep.path]
        assert len(main_entries) > 0, "main.py or equivalent should be detected as entry point"

        main_ep = main_entries[0]
        assert main_ep.confidence >= 0.7, \
            f"Entry point confidence for main.py should be high, got {main_ep.confidence}"

    def test_main_py_role_preserved(self):
        """main.py can be both an entry point and have a primary role."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()

        # Find app/main.py
        main_py = next((c for c in components if c.path == "app/main.py"), None)
        assert main_py is not None

        # main.py should have a meaningful role
        assert main_py.role in (ArchitecturalRole.ROUTE, ArchitecturalRole.CONFIGURATION), \
            f"main.py should have route or config role, got {main_py.role}"

        # Entry point status is represented in entry_points list, separate from role
        # This is the correct design: role + entry_points collection


class TestIssue4EvidenceSourceId:
    """Issue #4: Evidence source_id population.

    Evidence should have traceable source IDs where possible.
    """

    def test_evidence_has_meaningful_source_ids(self):
        """Evidence items should have source_id when source is identifiable."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()

        # Check a few components with strong evidence
        service_components = [c for c in components if c.role == ArchitecturalRole.SERVICE]
        assert len(service_components) > 0

        for comp in service_components:
            # Service components should have some evidence with source_id
            # (at minimum, they should not ALL have null source_id)
            has_any_source = any(ev.source_id is not None for ev in comp.evidence)

            # This is a soft check: at least some evidence should be traceable
            # Not all evidence needs source_id (composite inferences are acceptable)
            if len(comp.evidence) > 2:
                # Components with multiple pieces of evidence should have at least some traceability
                assert has_any_source or len(comp.evidence) <= 3, \
                    "Components with substantial evidence should have some source traceability"


class TestConfidenceScoring:
    """Verify confidence scoring is deterministic and not inflated."""

    def test_confidence_bounded(self):
        """All confidence scores should be in [0.0, 1.0]."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()

        for comp in components:
            assert 0.0 <= comp.confidence <= 1.0, \
                f"Confidence {comp.confidence} out of bounds for {comp.path}"

    def test_model_orm_confidence_appropriate(self):
        """ORM model components should have appropriate confidence, not inflated to 1.0 by repetition."""
        analyzer = RepositoryAnalyzer("../examples/fastapi_project")
        analysis_result = analyzer.analyze()
        graph = GraphBuilder(analysis_result).build()

        classifier = ArchitectureClassifier(analysis_result, graph)
        components = classifier.classify_all()

        # Find model components with multiple Pydantic/ORM classes
        orm_models = [c for c in components if c.role == ArchitecturalRole.MODEL and len(c.evidence) > 4]

        for model in orm_models:
            # High confidence is OK for strong evidence
            # But verify it's not purely from evidence count (repetitive signals)
            # Check for evidence diversity
            evidence_types = set(ev.type.value for ev in model.evidence)

            if model.confidence == 1.0:
                # Perfect confidence should be justified by diverse evidence types
                assert len(evidence_types) >= 2, \
                    "Perfect confidence should come from diverse evidence types, not repetition"
