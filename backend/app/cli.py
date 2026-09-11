#!/usr/bin/env python3
"""ArchLens AI command-line interface.

Usage examples:
    python -m archlens analyze ./example_project
    python -m archlens analyze ./example_project --output ./output
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from app.analyzer import RepositoryAnalyzer
from app.graph.graph_builder import GraphBuilder
from app.graph.serializer import GraphSerializer
from app.architecture.engine import ArchitectureInferenceEngine
from app.architecture.serializer import ArchitectureSerializer
from app.health.engine import HealthInferenceEngine
from app.health.serializer import HealthSerializer
from app.evolution.engine import EvolutionInferenceEngine
from app.evolution.serializer import EvolutionSerializer


@click.group()
@click.version_option(version="0.1.0", prog_name="archlens")
def cli():
    """ArchLens AI — analyze codebases and reconstruct their architecture."""
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=True, file_okay=False),
    default="output",
    show_default=True,
    help="Directory to write analysis.json, graph.json, and architecture.json",
)
def analyze(path: str, output: str):
    """Analyze a Python repository and produce analysis.json, graph.json, and architecture.json.

    PATH is the repository root directory to analyze.
    """
    output_dir = Path(output)

    try:
        analyzer = RepositoryAnalyzer(path)
        result = analyzer.analyze()
    except (FileNotFoundError, NotADirectoryError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = output_dir / "analysis.json"

    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, sort_keys=False)

    # Generate graph.json (Phase 2)
    graph_path = output_dir / "graph.json"
    builder = GraphBuilder(result)
    graph = builder.build()
    GraphSerializer.save_to_file(graph, str(graph_path))

    # Infer Architecture Intelligence (Phase 3)
    architecture_path = output_dir / "architecture.json"
    engine = ArchitectureInferenceEngine(analysis_result=result, graph=graph)
    arch_result = engine.analyze()
    ArchitectureSerializer.save_to_file(arch_result, str(architecture_path))

    # Infer Architecture Health & Risk Intelligence (Phase 4)
    health_path = output_dir / "health.json"
    health_engine = HealthInferenceEngine(analysis_result=result, graph=graph, architecture_result=arch_result)
    health_result = health_engine.analyze()
    HealthSerializer.save_to_file(health_result, str(health_path))

    # Infer Architecture Evolution & Refactoring Intelligence (Phase 5)
    evolution_path = output_dir / "evolution.json"
    evolution_engine = EvolutionInferenceEngine(
        analysis=result, graph=graph, architecture=arch_result, health=health_result
    )
    evolution_result = evolution_engine.analyze()
    EvolutionSerializer.save_to_file(evolution_result, str(evolution_path))

    click.echo(f"✅ Analyzed {path}")
    click.echo(f"   Files:         {result.statistics.total_python_files}")
    click.echo(f"   Lines:         {result.statistics.total_lines}")
    click.echo(f"   Classes:       {result.statistics.total_classes}")
    click.echo(f"   Functions:     {result.statistics.total_functions}")
    click.echo(f"   Routes:        {result.statistics.total_routes}")
    click.echo(f"   Imports:       {result.statistics.total_imports}")
    click.echo(f"   Dependencies:  {result.statistics.external_dependencies}")
    click.echo(f"")
    click.echo(f"   Components:    {arch_result.summary.component_count}")
    click.echo(f"   Entry Points:  {arch_result.summary.entry_point_count}")
    click.echo(f"   Patterns:      {arch_result.summary.pattern_count}")
    click.echo(f"")
    click.echo(f"   Health Score:  {health_result.overall_health.score}")
    click.echo(f"   Health Rating: {health_result.overall_health.rating.value}")
    click.echo(f"")
    click.echo(f"   Risks:         {sum(health_result.risk_summary.values())}")
    click.echo(f"   Hotspots:      {len(health_result.hotspots)}")
    click.echo(f"")
    click.echo(f"   Refactoring:   {evolution_result.summary.refactoring_opportunities}")
    click.echo(f"   Critical:      {evolution_result.priorities.critical_count}")
    click.echo(f"   High:          {evolution_result.priorities.high_count}")
    click.echo(f"")
    click.echo(f"   Written to:    {analysis_path}")
    click.echo(f"   Graph:         {graph_path}")
    click.echo(f"   Architecture:  {architecture_path}")
    click.echo(f"   Health:        {health_path}")
    click.echo(f"   Evolution:     {evolution_path}")


def main():
    """Entry point for python -m archlens."""
    cli()


if __name__ == "__main__":
    main()
