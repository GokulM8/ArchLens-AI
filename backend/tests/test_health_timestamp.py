"""Regression: health.json timestamps are timezone-aware UTC (no utcnow())."""

import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.analyzer import RepositoryAnalyzer
from app.architecture.engine import ArchitectureInferenceEngine
from app.graph.graph_builder import GraphBuilder
from app.health.engine import HealthInferenceEngine

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "fastapi_project"


def test_health_timestamp_is_aware_utc_without_deprecation_warning():
    analysis = RepositoryAnalyzer(str(EXAMPLE)).analyze()
    graph = GraphBuilder(analysis).build()
    arch = ArchitectureInferenceEngine(analysis_result=analysis, graph=graph).analyze()

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        result = HealthInferenceEngine(
            analysis_result=analysis, graph=graph, architecture_result=arch
        ).analyze()

    stamp = result.analysis_timestamp
    # Same wire format as before: ISO-8601 ending in a single "Z".
    assert stamp.endswith("Z") and not stamp.endswith("+00:00Z")
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)
    assert abs(datetime.now(timezone.utc) - parsed) < timedelta(minutes=5)
