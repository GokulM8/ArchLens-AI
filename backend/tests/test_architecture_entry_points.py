"""Unit tests for Phase 3 Entry Point Detector."""

import pytest
from app.analyzer import RepositoryAnalyzer
from app.architecture.entry_points import EntryPointDetector


def test_entry_point_detection_fastapi():
    analyzer = RepositoryAnalyzer("../examples/fastapi_project")
    analysis_result = analyzer.analyze()

    detector = EntryPointDetector(analysis_result)
    entry_points = detector.discover()

    assert len(entry_points) >= 1
    paths = [ep.path for ep in entry_points]
    # main.py or items.py or users.py with routes/main script
    assert any("main" in p for p in paths)
