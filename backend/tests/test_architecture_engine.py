"""Integration tests for Phase 3 ArchitectureInferenceEngine and Serializer."""

import os
import tempfile
import pytest
from app.analyzer import RepositoryAnalyzer
from app.architecture.engine import ArchitectureInferenceEngine
from app.architecture.serializer import ArchitectureSerializer


def test_engine_end_to_end():
    analyzer = RepositoryAnalyzer("../examples/fastapi_project")
    analysis_result = analyzer.analyze()

    engine = ArchitectureInferenceEngine(analysis_result)
    arch_result = engine.analyze()

    assert arch_result.repository_name == analysis_result.repository.name
    assert len(arch_result.components) > 0
    assert arch_result.summary.component_count == len(arch_result.components)
    assert arch_result.summary.entry_point_count == len(arch_result.entry_points)
    assert arch_result.summary.pattern_count == len(arch_result.patterns)


def test_serializer_roundtrip():
    analyzer = RepositoryAnalyzer("../examples/fastapi_project")
    analysis_result = analyzer.analyze()

    engine = ArchitectureInferenceEngine(analysis_result)
    arch_result = engine.analyze()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "architecture.json")
        ArchitectureSerializer.save_to_file(arch_result, file_path)

        assert os.path.exists(file_path)

        loaded_result = ArchitectureSerializer.load_from_file(file_path)
        assert loaded_result.repository_name == arch_result.repository_name
        assert len(loaded_result.components) == len(arch_result.components)
        assert loaded_result.summary.component_count == arch_result.summary.component_count
