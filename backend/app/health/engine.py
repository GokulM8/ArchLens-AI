"""Phase 4 Health & Risk Intelligence - Main Engine Orchestrator."""

from typing import Optional
import json
from datetime import datetime

from app.models.schemas import AnalysisResult
from app.graph.graph_builder import GraphBuilder
from app.architecture.engine import ArchitectureInferenceEngine
from app.architecture.schemas import ArchitectureResult
from app.health.schemas import HealthResult, Hotspot, RiskSeverity
from app.health.metrics import HealthMetricsCalculator
from app.health.risks import RiskDetector
from app.health.scoring import HealthScorer
import networkx as nx


class HealthInferenceEngine:
    """Orchestrates Phase 4 architecture health analysis."""

    def __init__(
        self,
        analysis_result: AnalysisResult,
        graph: Optional[nx.MultiDiGraph] = None,
        architecture_result: Optional[ArchitectureResult] = None,
    ):
        self.analysis_result = analysis_result
        self.graph = graph if graph is not None else GraphBuilder(analysis_result).build()

        if architecture_result is None:
            arch_engine = ArchitectureInferenceEngine(analysis_result, self.graph)
            self.architecture_result = arch_engine.analyze()
        else:
            self.architecture_result = architecture_result

    def analyze(self) -> HealthResult:
        """Run the complete health analysis pipeline.

        Returns:
            HealthResult containing health metrics, risks, hotspots, and score.
        """
        # Step 1: Calculate all metrics
        metrics_calculator = HealthMetricsCalculator(
            self.analysis_result,
            self.graph,
            self.architecture_result,
        )

        dependency_metrics = metrics_calculator.calculate_dependency_metrics()
        coupling_metrics = metrics_calculator.calculate_coupling_metrics()
        centrality_metrics = metrics_calculator.calculate_centrality_metrics()
        complexity_metrics = metrics_calculator.calculate_complexity_metrics()
        api_metrics = metrics_calculator.calculate_api_metrics()
        dependency_concentration = metrics_calculator.calculate_dependency_concentration()

        # Step 2: Detect risks and violations
        risk_detector = RiskDetector(self.graph, self.architecture_result)

        layer_violations = risk_detector.detect_layer_violations()
        cycle_risks = risk_detector.detect_circular_dependency_risks(dependency_metrics)
        coupling_risks = risk_detector.detect_high_coupling_risks(coupling_metrics)
        large_module_risks = risk_detector.detect_large_module_risks(complexity_metrics)
        api_concentration_risks = risk_detector.detect_api_concentration_risks(api_metrics)

        all_risks = cycle_risks + coupling_risks + large_module_risks + api_concentration_risks

        # Step 3: Detect hotspots (components with multiple risk signals)
        hotspots = self._identify_hotspots(
            all_risks,
            centrality_metrics,
            coupling_metrics,
            complexity_metrics,
        )

        # Step 4: Calculate overall health score
        scorer = HealthScorer()
        overall_health = scorer.calculate_health_score(
            dependency_metrics,
            coupling_metrics,
            centrality_metrics,
            complexity_metrics,
            all_risks,
            layer_violations,
        )

        # Step 5: Build risk summary
        risk_summary = {}
        for risk in all_risks:
            severity = risk.severity.value
            risk_summary[severity] = risk_summary.get(severity, 0) + 1

        # Build final result
        health_result = HealthResult(
            schema_version="1.0",
            repository_name=self.analysis_result.repository.name,
            analysis_timestamp=datetime.utcnow().isoformat() + "Z",
            overall_health=overall_health,
            dependency_metrics=dependency_metrics,
            coupling_metrics=coupling_metrics,
            centrality_metrics=centrality_metrics,
            complexity_metrics=complexity_metrics,
            api_metrics=api_metrics,
            dependency_concentration_metrics=dependency_concentration,
            layer_violations=layer_violations,
            risks=all_risks,
            hotspots=hotspots,
            risk_summary=risk_summary,
        )

        return health_result

    def _identify_hotspots(
        self,
        risks,
        centrality_metrics,
        coupling_metrics,
        complexity_metrics,
    ) -> list:
        """Identify architectural hotspots (components with multiple risk signals)."""
        hotspots_dict = {}

        # Collect signals for each component
        for risk in risks:
            for comp in risk.components:
                if comp not in hotspots_dict:
                    hotspots_dict[comp] = {
                        "signals": set(),
                        "severity": RiskSeverity.INFO,
                    }
                hotspots_dict[comp]["signals"].add(risk.type.value)
                # Update severity to worst found
                if risk.severity == RiskSeverity.CRITICAL:
                    hotspots_dict[comp]["severity"] = RiskSeverity.CRITICAL
                elif risk.severity == RiskSeverity.HIGH and hotspots_dict[comp]["severity"] != RiskSeverity.CRITICAL:
                    hotspots_dict[comp]["severity"] = RiskSeverity.HIGH

        # Add centrality signals
        for comp_info in centrality_metrics.highly_central_components:
            comp = comp_info["component"]
            if comp not in hotspots_dict:
                hotspots_dict[comp] = {
                    "signals": set(),
                    "severity": RiskSeverity.MEDIUM,
                }
            hotspots_dict[comp]["signals"].add("high_centrality")

        # Add coupling signals
        for comp_info in coupling_metrics.high_coupling_components:
            comp = comp_info["component"]
            if comp not in hotspots_dict:
                hotspots_dict[comp] = {
                    "signals": set(),
                    "severity": RiskSeverity.MEDIUM,
                }
            hotspots_dict[comp]["signals"].add("high_coupling")

        # Build hotspot objects for components with multiple signals
        hotspots = []
        for comp, comp_info in hotspots_dict.items():
            if len(comp_info["signals"]) >= 2:  # Multiple signals = hotspot
                comp_obj = next((c for c in self.architecture_result.components if c.id == comp), None)
                if comp_obj:
                    hotspots.append(Hotspot(
                        component=comp,
                        component_name=comp_obj.name,
                        signals=sorted(list(comp_info["signals"])),
                        severity=comp_info["severity"],
                        description=f"Component exhibits {len(comp_info['signals'])} independent warning signals",
                    ))

        return hotspots
