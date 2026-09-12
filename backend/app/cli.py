#!/usr/bin/env python3
"""ArchLens AI command-line interface.

Usage examples:
    python -m archlens analyze ./example_project
    python -m archlens analyze ./example_project --output ./output
"""

from __future__ import annotations

import asyncio
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
from app.llm.factory import LLMProviderFactory
from app.llm.context import VerifiedContextBuilder
from app.llm.guardrails import GroundingGuardrails
from app.llm.service import LLMService


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


# ---------------------------------------------------------------------------
# Phase 6 — LLM Architecture Copilot commands (spec §31)
# ---------------------------------------------------------------------------


def _build_llm_service(output_dir: str) -> LLMService:
    """Build an LLMService over the deterministic artifacts in output_dir."""
    context_builder = VerifiedContextBuilder.from_artifacts_dir(Path(output_dir))
    guardrails = GroundingGuardrails(context_builder)
    return LLMService(LLMProviderFactory, context_builder, guardrails)


def _render_response(response) -> None:
    """Render an LLMOperationResponse to the terminal, exiting non-zero on failure."""
    if response.success:
        click.echo(response.content)
        if response.error is not None:  # validation warning
            click.echo(f"\n⚠️  {response.error.message}", err=True)
        return

    click.echo("Error: " + (response.explanation or "LLM operation failed."), err=True)
    if response.error and response.error.details:
        click.echo(json.dumps(response.error.details, indent=2), err=True)
    for suggestion in response.suggestions:
        click.echo(f"- {suggestion}", err=True)
    sys.exit(1)


def _run_operation(coro):
    return asyncio.run(coro)


@cli.group()
def explain():
    """Explain architecture, components, dependencies, risks, and more (requires LLM config)."""
    pass


@explain.command("architecture")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=True, file_okay=False),
    default="output",
    show_default=True,
    help="Directory containing ArchLens artifacts (analysis/graph/architecture/health/evolution).",
)
def explain_architecture(output: str):
    """Explain the overall repository architecture based on deterministic artifacts."""
    service = _build_llm_service(output)
    response = _run_operation(service.explain_architecture({}))
    _render_response(response)


@explain.command("component")
@click.argument("component_id")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_component(component_id: str, output: str):
    """Explain a specific component by its architecture id (e.g. module:app.main)."""
    service = _build_llm_service(output)
    response = _run_operation(service.explain_component(component_id))
    _render_response(response)


@explain.command("dependency")
@click.argument("source")
@click.argument("target")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_dependency(source: str, target: str, output: str):
    """Explain the dependency relationship from SOURCE to TARGET."""
    service = _build_llm_service(output)
    response = _run_operation(service.explain_dependency(source, target))
    _render_response(response)


@explain.command("risk")
@click.argument("risk_id")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_risk(risk_id: str, output: str):
    """Explain an architectural risk by its health.json id."""
    service = _build_llm_service(output)
    response = _run_operation(service.explain_risk(risk_id))
    _render_response(response)


@explain.command("recommendation")
@click.argument("recommendation_id")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_recommendation(recommendation_id: str, output: str):
    """Explain an evolution recommendation by its evolution.json id."""
    service = _build_llm_service(output)
    response = _run_operation(service.explain_recommendation(recommendation_id))
    _render_response(response)


@explain.command("impact")
@click.argument("component_id")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_impact(component_id: str, output: str):
    """Analyze the impact of changing a component."""
    service = _build_llm_service(output)
    response = _run_operation(service.explain_impact(component_id))
    _render_response(response)


@explain.command("refactor-plan")
@click.argument("recommendation_id")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_refactor_plan(recommendation_id: str, output: str):
    """Generate a refactoring plan for an evolution recommendation."""
    service = _build_llm_service(output)
    response = _run_operation(service.generate_refactoring_plan(recommendation_id))
    _render_response(response)


@explain.command("summary")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def explain_summary(output: str):
    """Summarize the repository architecture and patterns."""
    service = _build_llm_service(output)
    response = _run_operation(service.summarize_repository({}))
    _render_response(response)


@cli.command()
@click.argument("question")
@click.option("--output", "-o", type=click.Path(dir_okay=True, file_okay=False), default="output", show_default=True)
def ask(question: str, output: str):
    """Ask an architecture question answered from the deterministic artifacts."""
    service = _build_llm_service(output)
    response = _run_operation(service.ask(question))
    _render_response(response)


def main():
    """Entry point for python -m archlens."""
    cli()


if __name__ == "__main__":
    main()
