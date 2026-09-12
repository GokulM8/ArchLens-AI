"""Shared fixtures for ArchLens Phase 6 tests.

All fixtures are deterministic — no real LLM is ever called. The MockLLMProvider
(archlens_llm_provider=mock + an api key) is used exclusively for the copilot
tests; the deterministic engine needs no configuration at all.
"""

import os
import json

import pytest

from app.llm.context import VerifiedContextBuilder
from app.llm.guardrails import GroundingGuardrails


def make_artifacts():
    """Build a minimal but structurally-valid set of the five ArchLens artifacts.

    Mirrors the shapes produced by `archlens analyze`: analysis.json,
    graph.json, architecture.json, health.json, evolution.json.
    """
    analysis = {
        "repository": {"name": "sample_repo", "root_path": "/tmp/sample"},
        "files": [{"path": "app/main.py", "module_id": "module:app.main"}],
        "modules": [
            {"id": "module:app", "name": "app", "path": "app/__init__.py"},
            {"id": "module:app.main", "name": "main", "path": "app/main.py", "file": "app/main.py"},
        ],
        "classes": [
            {"id": "class:app.main.A", "name": "A", "file": "app/main.py", "module_id": "module:app.main"}
        ],
        "functions": [],
        "routes": [{"path": "/health", "method": "GET", "function_id": "", "file": "app/main.py"}],
        "dependencies": [{"name": "fastapi", "version": "0.100"}],
        "relationships": [],
        "statistics": {"total_python_files": 2},
    }
    graph = {
        "directed": True,
        "nodes": [
            {"id": "module:app", "type": "module"},
            {"id": "module:app.main", "type": "module"},
        ],
        "links": [
            {"source": "module:app.main", "target": "module:app", "key": 0, "type": "IMPORTS"}
        ],
    }
    architecture = {
        "components": [
            {
                "id": "module:app.main",
                "name": "main",
                "path": "app/main.py",
                "role": "entry_point",
                "layer": "presentation",
                "confidence": 0.9,
            }
        ],
        "layers": [{"name": "presentation", "level": 0}],
        "entry_points": [{"name": "GET /health", "file": "app/main.py"}],
        "patterns": [{"name": "layered"}],
        "relationships": [],
        "summary": {},
    }
    health = {
        "overall_health": {"score": 0.7, "rating": "good"},
        "risks": [
            {
                "id": "high_coupling:module:app.main",
                "type": "high_coupling",
                "severity": "high",
                "title": "High coupling",
                "description": "Module is highly coupled",
                "components": ["module:app.main"],
                "evidence": [{"metric": "afferent_coupling", "value": 12}],
                "metric": "afferent_coupling",
                "recommendation": "Split the module",
            }
        ],
        "hotspots": [{"component": "module:app.main", "component_name": "main"}],
        "layer_violations": [],
        "coupling_metrics": {},
        "dependency_metrics": {},
        "complexity_metrics": {},
        "risk_summary": {"high": 1},
    }
    evolution = {
        "refactoring_opportunities": [
            {
                "id": "reduce_coupling:module:app.main",
                "type": "reduce_coupling",
                "priority": "high",
                "severity": "high",
                "title": "Reduce coupling",
                "description": "d",
                "rationale": "r",
                "components": ["module:app.main"],
                "evidence": [],
                "suggested_action": "Extract interface",
                "expected_benefit": "Lower coupling",
                "estimated_scope": "medium",
                "confidence": 0.8,
            }
        ],
        "dependency_insights": {},
        "impact_analysis": {"module:app.main": {"direct": ["module:app"], "indirect": []}},
        "priorities": {"critical_count": 0, "high_count": 1},
        "summary": {},
    }
    return analysis, graph, architecture, health, evolution


ARTIFACT_FILENAMES = (
    "analysis.json",
    "graph.json",
    "architecture.json",
    "health.json",
    "evolution.json",
)


def write_artifacts(directory, artifacts=None):
    """Write the five artifact files into ``directory`` (as str or Path)."""
    a, g, arch, h, e = artifacts if artifacts is not None else make_artifacts()
    payloads = {
        "analysis": a,
        "graph": g,
        "architecture": arch,
        "health": h,
        "evolution": e,
    }
    for fname in ARTIFACT_FILENAMES:
        with open(os.path.join(str(directory), fname), "w", encoding="utf-8") as f:
            json.dump(payloads[fname[:-5]], f)
    return directory


@pytest.fixture
def artifacts():
    """Raw artifact dicts (analysis, graph, architecture, health, evolution)."""
    return make_artifacts()


@pytest.fixture
def context_builder(artifacts):
    """A VerifiedContextBuilder over the shared minimal artifacts."""
    return VerifiedContextBuilder(*artifacts)


@pytest.fixture
def guardrails(context_builder):
    """GroundingGuardrails wired to the shared minimal artifacts."""
    return GroundingGuardrails(context_builder)


@pytest.fixture
def mock_env(monkeypatch):
    """Configure the LLM environment for the MockLLMProvider.

    The factory requires BOTH a provider name and an api key (even for mock),
    so this fixture sets both and removes any stale model override.
    """
    monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ARCHLENS_LLM_API_KEY", "test-key")
    monkeypatch.delenv("ARCHLENS_LLM_MODEL", raising=False)
    yield
    monkeypatch.delenv("ARCHLENS_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ARCHLENS_LLM_API_KEY", raising=False)


@pytest.fixture
def no_llm_env(monkeypatch):
    """Remove all LLM configuration (deterministic-only mode)."""
    monkeypatch.delenv("ARCHLENS_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ARCHLENS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ARCHLENS_LLM_MODEL", raising=False)
    yield