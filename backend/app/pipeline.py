"""Deterministic Phase 1–5 pipeline, shared by the CLI and the HTTP API.

Runs analysis → graph → architecture → health → evolution over a repository
directory and writes the five JSON artifacts into ``output_dir``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.serializer import GraphSerializer
from app.architecture.engine import ArchitectureInferenceEngine
from app.architecture.schemas import ArchitectureResult
from app.architecture.serializer import ArchitectureSerializer
from app.health.engine import HealthInferenceEngine
from app.health.schemas import HealthResult
from app.health.serializer import HealthSerializer
from app.evolution.engine import EvolutionInferenceEngine
from app.evolution.schemas import EvolutionResult
from app.evolution.serializer import EvolutionSerializer
from app.models.schemas import AnalysisResult

ARTIFACT_NAMES = ("analysis", "graph", "architecture", "health", "evolution")


@dataclass
class PipelineResult:
    """In-memory results of one pipeline run plus where the artifacts were written."""

    analysis: AnalysisResult
    graph: nx.MultiDiGraph
    architecture: ArchitectureResult
    health: HealthResult
    evolution: EvolutionResult
    output_dir: Path

    def artifact_path(self, name: str) -> Path:
        return self.output_dir / f"{name}.json"


def run_pipeline(repo_path: str | Path, output_dir: str | Path) -> PipelineResult:
    """Analyze ``repo_path`` and write all five artifacts to ``output_dir``.

    Raises FileNotFoundError / NotADirectoryError if ``repo_path`` is invalid.
    """
    output_dir = Path(output_dir)

    # Phase 1 — static analysis
    result = RepositoryAnalyzer(str(repo_path)).analyze()
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "analysis.json", "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, sort_keys=False)

    # Phase 2 — dependency graph
    graph = GraphBuilder(result).build()
    GraphSerializer.save_to_file(graph, str(output_dir / "graph.json"))

    # Phase 3 — architecture intelligence
    arch_result = ArchitectureInferenceEngine(analysis_result=result, graph=graph).analyze()
    ArchitectureSerializer.save_to_file(arch_result, str(output_dir / "architecture.json"))

    # Phase 4 — health & risk intelligence
    health_result = HealthInferenceEngine(
        analysis_result=result, graph=graph, architecture_result=arch_result
    ).analyze()
    HealthSerializer.save_to_file(health_result, str(output_dir / "health.json"))

    # Phase 5 — evolution & refactoring intelligence
    evolution_result = EvolutionInferenceEngine(
        analysis=result, graph=graph, architecture=arch_result, health=health_result
    ).analyze()
    EvolutionSerializer.save_to_file(evolution_result, str(output_dir / "evolution.json"))

    return PipelineResult(
        analysis=result,
        graph=graph,
        architecture=arch_result,
        health=health_result,
        evolution=evolution_result,
        output_dir=output_dir,
    )
