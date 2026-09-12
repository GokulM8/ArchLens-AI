"""Verified Context Builder — builds focused contexts from deterministic artifacts.

Consumes the five ArchLens deterministic artifacts and constructs a structured
verified context for LLM operations. Deterministic artifacts are the source of
truth; the LLM reasons over them and never discovers architecture from raw code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.llm.schemas import LLMContext


class VerifiedContextBuilder:
    """Builds verified contexts for LLM operations from deterministic artifacts."""

    # Canonical artifact filenames produced by `archlens analyze`.
    ARTIFACT_FILES = (
        "analysis.json",
        "graph.json",
        "architecture.json",
        "health.json",
        "evolution.json",
    )

    # Budget: the maximum supported context budget, not the normal target.
    DEFAULT_MAX_TOKENS = 100_000

    def __init__(
        self,
        analysis_data: Optional[Dict[str, Any]] = None,
        graph_data: Optional[Dict[str, Any]] = None,
        architecture_data: Optional[Dict[str, Any]] = None,
        health_data: Optional[Dict[str, Any]] = None,
        evolution_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the context builder with deterministic artifacts.

        Args:
            analysis_data: Static analysis results from Phase 1 (analysis.json)
            graph_data: Code graph from Phase 2 (graph.json)
            architecture_data: Architecture intelligence from Phase 3 (architecture.json)
            health_data: Health metrics from Phase 4 (health.json)
            evolution_data: Evolution insights from Phase 5 (evolution.json)
        """
        self.raw_analysis = analysis_data or {}
        self.raw_graph = graph_data or {}
        self.raw_architecture = architecture_data or {}
        self.raw_health = health_data or {}
        self.raw_evolution = evolution_data or {}

        # Parsed artifacts in a normalized, quick-reference structure.
        self._parsed_artifacts: Dict[str, Any] = self._parse_artifacts()

        self.repository_name = self._parsed_artifacts.get("repository_name", "unknown")

    @classmethod
    def from_artifacts_dir(cls, output_dir: str | Path) -> "VerifiedContextBuilder":
        """Load all five deterministic artifacts from an `archlens analyze` output dir.

        Args:
            output_dir: Directory containing analysis.json, graph.json, etc.

        Returns:
            VerifiedContextBuilder populated from the artifact files.

        Raises:
            FileNotFoundError: If any artifact file is missing.
        """
        output_dir = Path(output_dir)
        data: Dict[str, Any] = {}

        for filename in cls.ARTIFACT_FILES:
            path = output_dir / filename
            if not path.exists():
                raise FileNotFoundError(
                    f"Missing ArchLens artifact: {path}. Run `archlens analyze <path>` first."
                )
            with open(path, "r", encoding="utf-8") as f:
                data[filename.replace(".json", "")] = json.load(f)

        return cls(
            analysis_data=data.get("analysis"),
            graph_data=data.get("graph"),
            architecture_data=data.get("architecture"),
            health_data=data.get("health"),
            evolution_data=data.get("evolution"),
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_artifacts(self) -> Dict[str, Any]:
        """Parse artifacts into normalized quick-reference structures."""
        parsed: Dict[str, Any] = {"repository_name": "unknown"}

        self._parse_analysis(parsed)
        self._parse_graph(parsed)
        self._parse_architecture(parsed)
        self._parse_health(parsed)
        self._parse_evolution(parsed)

        return parsed

    def _parse_analysis(self, parsed: Dict[str, Any]) -> None:
        """Parse analysis.json contents."""
        analysis: Dict[str, Any] = {}

        repo = self.raw_analysis.get("repository") or {}
        if repo.get("name"):
            parsed["repository_name"] = repo["name"]
        analysis["root_path"] = repo.get("root_path", "")
        analysis["analyzed_at"] = repo.get("analyzed_at", "")

        # Index files by path and by module id.
        analysis["files_by_path"] = {
            f["path"]: f for f in self.raw_analysis.get("files", [])
        }
        analysis["modules_by_id"] = {
            m["id"]: m for m in self.raw_analysis.get("modules", [])
        }
        analysis["classes_by_id"] = {
            c["id"]: c for c in self.raw_analysis.get("classes", [])
        }
        analysis["functions_by_id"] = {
            f["id"]: f for f in self.raw_analysis.get("functions", [])
        }
        analysis["routes"] = list(self.raw_analysis.get("routes", []))
        analysis["external_dependencies"] = list(
            self.raw_analysis.get("dependencies", [])
        )
        analysis["relationships"] = list(self.raw_analysis.get("relationships", []))

        # Index routes by module id for component context.
        routes_by_module: Dict[str, List[Dict[str, Any]]] = {}
        for route in analysis["routes"]:
            function_id = route.get("function_id", "")
            function = analysis["functions_by_id"].get(function_id)
            module_id = None
            if function:
                module_id = function.get("module_id")
            if not module_id and function:
                # Derive module id from file path.
                file_path = function.get("file", "")
                module_id = self._file_to_module_id(file_path)
            routes_by_module.setdefault(module_id or "", []).append(route)
        analysis["routes_by_module"] = routes_by_module

        analysis["statistics"] = self.raw_analysis.get("statistics", {})
        parsed["analysis"] = analysis

    def _parse_graph(self, parsed: Dict[str, Any]) -> None:
        """Parse graph.json contents (NetworkX JSON: nodes + links)."""
        graph: Dict[str, Any] = {}

        graph["nodes_by_id"] = {
            n["id"]: {k: v for k, v in n.items() if k != "id"}
            for n in self.raw_graph.get("nodes", [])
        }
        graph["links"] = []
        for link in self.raw_graph.get("links", []):
            entry = {
                "source": link.get("source", ""),
                "target": link.get("target", ""),
                "key": link.get("key", 0),
                "type": link.get("type", "IMPORTS"),
            }
            # Carry over useful relationship attributes.
            for attr in ("relationship", "file", "line"):
                if link.get(attr) is not None:
                    entry[attr] = link[attr]
            graph["links"].append(entry)

        # Index outgoing and incoming edges per node.
        out_edges: Dict[str, List[Dict[str, Any]]] = {}
        in_edges: Dict[str, List[Dict[str, Any]]] = {}
        for link in graph["links"]:
            out_edges.setdefault(link["source"], []).append(link)
            in_edges.setdefault(link["target"], []).append(link)
        graph["out_edges"] = out_edges
        graph["in_edges"] = in_edges

        graph["summary"] = self.raw_graph.get("graph", {})
        parsed["graph"] = graph

    def _parse_architecture(self, parsed: Dict[str, Any]) -> None:
        """Parse architecture.json contents."""
        architecture: Dict[str, Any] = {}

        architecture["components_by_id"] = {}
        for comp in self.raw_architecture.get("components", []):
            architecture["components_by_id"][comp.get("id", "")] = comp

        architecture["layers"] = list(self.raw_architecture.get("layers", []))
        architecture["layers_by_name"] = {
            layer.get("name"): layer for layer in architecture["layers"]
        }
        architecture["entry_points"] = list(
            self.raw_architecture.get("entry_points", [])
        )
        architecture["patterns"] = list(self.raw_architecture.get("patterns", []))
        architecture["relationships"] = list(
            self.raw_architecture.get("relationships", [])
        )
        architecture["summary"] = self.raw_architecture.get("summary", {})
        parsed["architecture"] = architecture

    def _parse_health(self, parsed: Dict[str, Any]) -> None:
        """Parse health.json contents."""
        health: Dict[str, Any] = {}

        overall = self.raw_health.get("overall_health", {})
        health["overall_score"] = overall.get("score")
        health["overall_rating"] = overall.get("rating")
        health["dimensions"] = overall.get("dimensions", [])

        health["risks_by_id"] = {
            r.get("id"): r for r in self.raw_health.get("risks", [])
        }
        health["risks"] = list(self.raw_health.get("risks", []))
        health["hotspots"] = list(self.raw_health.get("hotspots", []))
        health["layer_violations"] = list(
            self.raw_health.get("layer_violations", [])
        )

        # Index risks and hotspots by component for component context.
        risks_by_component: Dict[str, List[Dict[str, Any]]] = {}
        for risk in health["risks"]:
            for comp_id in risk.get("components", []):
                risks_by_component.setdefault(comp_id, []).append(risk)
        health["risks_by_component"] = risks_by_component

        hotspots_by_component: Dict[str, Dict[str, Any]] = {}
        for hotspot in health["hotspots"]:
            hotspots_by_component[hotspot.get("component", "")] = hotspot
        health["hotspots_by_component"] = hotspots_by_component

        health["coupling_metrics"] = self.raw_health.get("coupling_metrics", {})
        health["dependency_metrics"] = self.raw_health.get("dependency_metrics", {})
        health["complexity_metrics"] = self.raw_health.get("complexity_metrics", {})
        health["risk_summary"] = self.raw_health.get("risk_summary", {})
        parsed["health"] = health

    def _parse_evolution(self, parsed: Dict[str, Any]) -> None:
        """Parse evolution.json contents."""
        evolution: Dict[str, Any] = {}

        evolution["opportunities_by_id"] = {
            o.get("id"): o
            for o in self.raw_evolution.get("refactoring_opportunities", [])
        }
        evolution["opportunities"] = list(
            self.raw_evolution.get("refactoring_opportunities", [])
        )
        evolution["dependency_insights"] = self.raw_evolution.get(
            "dependency_insights", {}
        )
        evolution["impact_analysis"] = self.raw_evolution.get("impact_analysis", {})
        evolution["priorities"] = self.raw_evolution.get("priorities", {})
        evolution["summary"] = self.raw_evolution.get("summary", {})

        # Index opportunities by component.
        opportunities_by_component: Dict[str, List[Dict[str, Any]]] = {}
        for opp in evolution["opportunities"]:
            for comp_id in opp.get("components", []):
                opportunities_by_component.setdefault(comp_id, []).append(opp)
        evolution["opportunities_by_component"] = opportunities_by_component
        parsed["evolution"] = evolution

    def _file_to_module_id(self, file_path: str) -> str:
        """Best-effort conversion of a relative file path to a module id."""
        if not file_path:
            return ""
        stem = file_path[:-3] if file_path.endswith(".py") else file_path
        stem = stem.replace("/", ".")
        return f"module:{stem}"

    # ------------------------------------------------------------------
    # Repository context
    # ------------------------------------------------------------------

    def build_repository_context(self) -> LLMContext:
        """Build a comprehensive repository context for high-level operations."""
        analysis = self._parsed_artifacts.get("analysis", {})
        arch = self._parsed_artifacts.get("architecture", {})
        health = self._parsed_artifacts.get("health", {})
        evolution = self._parsed_artifacts.get("evolution", {})
        graph = self._parsed_artifacts.get("graph", {})

        custom_context = {
            "repository": self.repository_name,
            "component_count": len(arch.get("components_by_id", {})),
            "module_count": len(analysis.get("modules_by_id", {})),
            "file_count": len(analysis.get("files_by_path", {})),
            "path_count": len(graph.get("links", [])),
            "edge_count": len(graph.get("links", [])),
            "route_count": len(analysis.get("routes", [])),
            "health_score": health.get("overall_score"),
            "health_rating": health.get("overall_rating"),
            "risk_count": len(health.get("risks", [])),
            "hotspot_count": len(health.get("hotspots", [])),
            "refactoring_count": len(evolution.get("opportunities", [])),
            "top_risks": self._summarize_risks(limit=5),
            "hotspots": [h.get("component_name", h.get("component")) for h in health.get("hotspots", [])[:10]],
            "patterns": [p.get("name") for p in arch.get("patterns", [])],
            "layers": list(arch.get("layers_by_name", {}).keys()),
            "entry_points": [
                ep.get("name") for ep in arch.get("entry_points", [])
            ],
            "top_refactorings": [
                o.get("title")
                for o in sorted(
                    evolution.get("opportunities", []),
                    key=lambda o: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                        o.get("priority"), 4
                    ),
                )[:10]
            ],
            "confidence": "verified",
        }

        return LLMContext(
            repository_name=self.repository_name,
            analysis_data=self.raw_analysis,
            graph_data=self.raw_graph,
            architecture_data=self.raw_architecture,
            health_data=self.raw_health,
            evolution_data=self.raw_evolution,
            user_focus=None,
            custom_context=custom_context,
        )

    def _summarize_risks(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the top N risks by severity."""
        health = self._parsed_artifacts.get("health", {})
        risks = list(health.get("risks", []))
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        risks.sort(key=lambda r: severity_rank.get(r.get("severity"), 5))
        return [
            {
                "type": r.get("type"),
                "severity": r.get("severity"),
                "title": r.get("title"),
                "components": r.get("components", []),
            }
            for r in risks[:limit]
        ]

    # ------------------------------------------------------------------
    # Component context
    # ------------------------------------------------------------------

    def build_component_context(
        self, component_id: str, user_focus: Optional[str] = None
    ) -> LLMContext:
        """Build focused context for a specific component."""
        analysis = self._parsed_artifacts.get("analysis", {})
        arch = self._parsed_artifacts.get("architecture", {})
        health = self._parsed_artifacts.get("health", {})
        evolution = self._parsed_artifacts.get("evolution", {})
        graph = self._parsed_artifacts.get("graph", {})

        comp_arch = arch.get("components_by_id", {}).get(component_id)
        module = analysis.get("modules_by_id", {}).get(component_id)

        # Resolve the file path for this component.
        file_path = ""
        if comp_arch and comp_arch.get("path"):
            file_path = comp_arch["path"]
        elif module and module.get("path"):
            file_path = module["path"]

        path_count = max(
            len(graph.get("out_edges", {}).get(component_id, [])),
            len(graph.get("in_edges", {}).get(component_id, [])),
        )

        custom_context = {
            "component_id": component_id,
            "name": comp_arch.get("name") if comp_arch else (module or {}).get("id", component_id),
            "path": file_path,
            "role": comp_arch.get("role") if comp_arch else None,
            "layer": comp_arch.get("layer") if comp_arch else None,
            "confidence": comp_arch.get("confidence") if comp_arch else None,
            "module": comp_arch.get("name") if comp_arch else component_id,
            "dependencies": [e["target"] for e in graph.get("out_edges", {}).get(component_id, [])],
            "dependents": [e["source"] for e in graph.get("in_edges", {}).get(component_id, [])],
            "dependency_count": len(graph.get("out_edges", {}).get(component_id, [])),
            "dependent_count": len(graph.get("in_edges", {}).get(component_id, [])),
            "path_count": path_count,
            "routes": [
                r.get("path") for r in analysis.get("routes_by_module", {}).get(component_id, [])
            ],
            "route_count": len(analysis.get("routes_by_module", {}).get(component_id, [])),
            "class_count": len(
                [
                    c
                    for c in analysis.get("modules_by_id", {})
                    .get(component_id, {})
                    .get("classes", [])
                ]
            ),
            "function_count": len(
                analysis.get("modules_by_id", {})
                .get(component_id, {})
                .get("functions", [])
            ),
            "risks": health.get("risks_by_component", {}).get(component_id, []),
            "risk_types": [
                r.get("type")
                for r in health.get("risks_by_component", {}).get(component_id, [])
            ],
            "hotspot": health.get("hotspots_by_component", {}).get(component_id),
            "refactorings": evolution.get("opportunities_by_component", {}).get(
                component_id, []
            ),
            "impact_analysis": evolution.get("impact_analysis", {}).get(component_id, {}),
            "layer_violations": [
                v
                for v in health.get("layer_violations", [])
                if v.get("source_component") == component_id
                or v.get("target_component") == component_id
            ],
            "confidence": "verified",
        }

        return LLMContext(
            repository_name=self.repository_name,
            analysis_data=self._filtered_analysis_for_component(component_id),
            graph_data=self._filtered_graph_for_component(component_id),
            architecture_data=self._filtered_architecture_for_component(component_id),
            health_data=self._filtered_health_for_component(component_id),
            evolution_data=self._filtered_evolution_for_component(component_id),
            user_focus=user_focus,
            custom_context=custom_context,
        )

    def _component_exists(self, component_id: str) -> bool:
        arch = self._parsed_artifacts.get("architecture", {})
        analysis = self._parsed_artifacts.get("analysis", {})
        return (
            component_id in arch.get("components_by_id", {})
            or component_id in analysis.get("modules_by_id", {})
        )

    def _filtered_analysis_for_component(self, component_id: str) -> Dict[str, Any]:
        """Return analysis data filtered to a single component's module."""
        module = self._parsed_artifacts.get("analysis", {}).get("modules_by_id", {}).get(component_id)
        return {"modules": [module] if module else []}

    def _filtered_graph_for_component(self, component_id: str) -> Dict[str, Any]:
        """Return graph links touching this component (its dependency closure)."""
        graph = self._parsed_artifacts.get("graph", {})
        links = []
        for link in graph.get("links", []):
            source, target = link["source"], link["target"]
            if source == component_id or target == component_id:
                links.append(link)
        return {"nodes": [], "links": links}

    def _filtered_architecture_for_component(self, component_id: str) -> Dict[str, Any]:
        """Return architecture data for a component and its direct neighbors."""
        arch = self._parsed_artifacts.get("architecture", {})
        comp = arch.get("components_by_id", {}).get(component_id)
        return {"components": [comp] if comp else []}

    def _filtered_health_for_component(self, component_id: str) -> Dict[str, Any]:
        """Return health data relevant to this component."""
        health = self._parsed_artifacts.get("health", {})
        return {
            "risks": health.get("risks_by_component", {}).get(component_id, []),
            "hotspots": [
                h for h in health.get("hotspots", []) if h.get("component") == component_id
            ],
            "layer_violations": [
                v
                for v in health.get("layer_violations", [])
                if v.get("source_component") == component_id
                or v.get("target_component") == component_id
            ],
        }

    def _filtered_evolution_for_component(self, component_id: str) -> Dict[str, Any]:
        """Return evolution data relevant to this component."""
        evolution = self._parsed_artifacts.get("evolution", {})
        return {
            "refactoring_opportunities": evolution.get(
                "opportunities_by_component", {}
            ).get(component_id, []),
            "impact_analysis": {
                component_id: evolution.get("impact_analysis", {}).get(component_id, {})
            },
        }

    # ------------------------------------------------------------------
    # Dependency context
    # ------------------------------------------------------------------

    def build_dependency_context(
        self, source_component: str, target_component: str
    ) -> LLMContext:
        """Build focused context for a dependency relationship."""
        graph = self._parsed_artifacts.get("graph", {})

        # Find all links between the two components (either direction).
        links = [
            link
            for link in graph.get("links", [])
            if (link["source"] == source_component and link["target"] == target_component)
            or (link["source"] == target_component and link["target"] == source_component)
        ]

        if not links:
            raise ValueError(
                f"No dependency relationship found between '{source_component}' and '{target_component}'"
            )

        arch = self._parsed_artifacts.get("architecture", {})
        source_info = arch.get("components_by_id", {}).get(source_component)
        target_info = arch.get("components_by_id", {}).get(target_component)

        # Only embed resolved component records (source/target may only exist in
        # the graph, not the architecture index — never emit None entries).
        component_records = [info for info in (source_info, target_info) if info]

        # Determine relationship strength by edge multiplicity / types.
        relationship_types = [link.get("type", "IMPORTS") for link in links]

        custom_context = {
            "source_component": source_component,
            "target_component": target_component,
            "edges": links,
            "edge_count": len(links),
            "relationship_types": relationship_types,
            "directed": "source -> target" if any(
                l["source"] == source_component for l in links
            ) else "target -> source",
            "source_info": source_info,
            "target_info": target_info,
            "source_role": source_info.get("role") if source_info else None,
            "target_role": target_info.get("role") if target_info else None,
            "source_layer": source_info.get("layer") if source_info else None,
            "target_layer": target_info.get("layer") if target_info else None,
            "confidence": "verified",
        }

        return LLMContext(
            repository_name=self.repository_name,
            analysis_data=self._filtered_analysis_for_component(source_component),
            graph_data={"links": links},
            architecture_data={
                "components": component_records
            },
            health_data=self._filtered_health_for_dependency(
                source_component, target_component
            ),
            evolution_data={},
            user_focus=None,
            custom_context=custom_context,
        )

    def _filtered_health_for_dependency(
        self, source_component: str, target_component: str
    ) -> Dict[str, Any]:
        """Return health/risk data for the two components of a dependency."""
        health = self._parsed_artifacts.get("health", {})
        risks = []
        for comp in (source_component, target_component):
            risks.extend(health.get("risks_by_component", {}).get(comp, []))
        return {"risks": risks}

    # ------------------------------------------------------------------
    # Risk context
    # ------------------------------------------------------------------

    def build_risk_context(self, risk_id: str) -> LLMContext:
        """Build focused context for a specific risk finding."""
        health = self._parsed_artifacts.get("health", {})
        risk = health.get("risks_by_id", {}).get(risk_id)

        if not risk:
            raise ValueError(f"No risk found with ID: {risk_id}")

        affected_component = risk.get("components", [""])[0] if risk.get("components") else ""

        # Find related refactoring opportunities affecting the primary component.
        related_opportunities = (
            self._parsed_artifacts.get("evolution", {})
            .get("opportunities_by_component", {})
            .get(affected_component, [])
        )

        comp_info = self._parsed_artifacts.get("architecture", {}).get(
            "components_by_id", {}
        ).get(affected_component)

        custom_context = {
            "risk_id": risk_id,
            "risk_type": risk.get("type"),
            "affected_component": affected_component,
            "affected_components": risk.get("components", []),
            "severity": risk.get("severity"),
            "title": risk.get("title"),
            "description": risk.get("description"),
            "evidence": risk.get("evidence", []),
            "metric": risk.get("metric"),
            "recommendation": risk.get("recommendation"),
            "component_info": comp_info,
            "related_opportunities": related_opportunities,
            "confidence": "verified",
        }

        return LLMContext(
            repository_name=self.repository_name,
            analysis_data=self._filtered_analysis_for_component(affected_component)
            if affected_component
            else {},
            graph_data=self._filtered_graph_for_component(affected_component)
            if affected_component
            else {},
            architecture_data={
                "components": [comp_info] if comp_info else []
            },
            health_data={"risks": [risk]},
            evolution_data={"refactoring_opportunities": related_opportunities},
            user_focus=None,
            custom_context=custom_context,
        )

    # ------------------------------------------------------------------
    # Recommendation / refactoring context
    # ------------------------------------------------------------------

    def build_recommendation_context(self, recommendation_id: str) -> LLMContext:
        """Build focused context for a refactoring recommendation."""
        evolution = self._parsed_artifacts.get("evolution", {})
        opp = evolution.get("opportunities_by_id", {}).get(recommendation_id)

        if not opp:
            raise ValueError(f"No recommendation found with ID: {recommendation_id}")

        affected_components = opp.get("components", [])
        primary = affected_components[0] if affected_components else ""

        health = self._parsed_artifacts.get("health", {})
        related_risks = health.get("risks_by_component", {}).get(primary, [])

        impact = evolution.get("impact_analysis", {}).get(primary, {})

        comp_info = self._parsed_artifacts.get("architecture", {}).get(
            "components_by_id", {}
        ).get(primary)

        custom_context = {
            "recommendation_id": recommendation_id,
            "recommendation_type": opp.get("type"),
            "title": opp.get("title"),
            "severity": opp.get("severity"),
            "priority": opp.get("priority"),
            "description": opp.get("description"),
            "rationale": opp.get("rationale"),
            "affected_components": affected_components,
            "affected_component": primary,
            "evidence": opp.get("evidence", []),
            "suggested_action": opp.get("suggested_action"),
            "expected_benefit": opp.get("expected_benefit"),
            "estimated_scope": opp.get("estimated_scope"),
            "confidence": opp.get("confidence"),
            "related_risks": related_risks,
            "impact_analysis": impact,
            "component_info": comp_info,
            "confidence": "verified",
        }

        return LLMContext(
            repository_name=self.repository_name,
            analysis_data={},
            graph_data={},
            architecture_data={"components": [comp_info] if comp_info else []},
            health_data={"risks": related_risks},
            evolution_data={
                "refactoring_opportunities": [opp],
                "impact_analysis": {primary: impact} if primary else {},
            },
            user_focus=None,
            custom_context=custom_context,
        )

    # ------------------------------------------------------------------
    # Impact context
    # ------------------------------------------------------------------

    def build_impact_context(self, component_id: str) -> LLMContext:
        """Build focused context for impact analysis of a component."""
        evolution = self._parsed_artifacts.get("evolution", {})
        impact = evolution.get("impact_analysis", {}).get(component_id, {})

        graph = self._parsed_artifacts.get("graph", {})
        # Direct dependents of the component.
        depended_up_on = [
            e["source"]
            for e in graph.get("in_edges", {}).get(component_id, [])
        ]
        # Components this component depends on.
        depends_on = [
            e["target"]
            for e in graph.get("out_edges", {}).get(component_id, [])
        ]

        arch = self._parsed_artifacts.get("architecture", {})
        comp_info = arch.get("components_by_id", {}).get(component_id)

        indirectly = impact.get("indirectly_affected_components", [])

        custom_context = {
            "component_id": component_id,
            "component_info": comp_info,
            "directly_affected_components": [
                c for c in depended_up_on
            ],
            "indirectly_affected_components": indirectly,
            "indirect_count": len(indirectly),
            "depends_on": depends_on,
            "total_impact_count": impact.get("total_impact_count", len(depended_up_on)),
            "impact_level": impact.get("impact_level"),
            "affected_routes": impact.get("affected_routes", 0),
            "affected_dependencies": impact.get("affected_dependencies", 0),
            "affected_layers": impact.get("affected_layers", []),
            "confidence": "verified",
        }

        return LLMContext(
            repository_name=self.repository_name,
            analysis_data={},
            graph_data=self._filtered_graph_for_component(component_id),
            architecture_data={"components": [comp_info] if comp_info else []},
            health_data=self._filtered_health_for_component(component_id),
            evolution_data={"impact_analysis": {component_id: impact}},
            user_focus=None,
            custom_context=custom_context,
        )

    # ------------------------------------------------------------------
    # Operation dispatch
    # ------------------------------------------------------------------

    def select_context_for_operation(
        self,
        operation_type: str,
        target: Optional[str] = None,
        user_focus: Optional[str] = None,
    ) -> LLMContext:
        """
        Select the most appropriate focused context for an LLM operation.

        Args:
            operation_type: Operation identifier (e.g., "component_explanation").
            target: Optional target component id, risk id, recommendation id, or
                dependency "source:target".
            user_focus: Optional specific focus area.

        Returns:
            LLMContext focused for the operation.

        Raises:
            ValueError: If a target is required but missing/not found.
        """
        lowered = (operation_type or "").lower()

        if "component" in lowered:
            if not target:
                raise ValueError("Component operation requires a target component id")
            return self.build_component_context(target if not target.startswith("component:") else target.split(":", 1)[1], user_focus)

        if "dependency" in lowered or "relationship" in lowered:
            if not target or "||" not in target:
                raise ValueError("Dependency operation requires a 'source||target' target")
            source, target_comp = target.split("||", 1)
            return self.build_dependency_context(source, target_comp)

        if "risk" in lowered or "health" in lowered:
            if not target:
                raise ValueError("Risk operation requires a risk id")
            if target.startswith("risk:"):
                target = target.split(":", 1)[1]
            return self.build_risk_context(target)

        if "recommendation" in lowered or "refactor" in lowered:
            if not target:
                raise ValueError("Recommendation operation requires a recommendation id")
            if target.startswith("rec:"):
                target = target.split(":", 1)[1]
            return self.build_recommendation_context(target)

        if "impact" in lowered:
            if not target:
                raise ValueError("Impact operation requires a component id")
            if target.startswith("component:"):
                target = target.split(":", 1)[1]
            return self.build_impact_context(target)

        # Default: repository context (architecture explanation, summary, QA).
        return self.build_repository_context()

    # ------------------------------------------------------------------
    # Validation & budget
    # ------------------------------------------------------------------

    def validate_context_completeness(self, context: LLMContext) -> List[str]:
        """
        Validate that a context is complete enough for an LLM operation.

        Args:
            context: The context to validate.

        Returns:
            List of validation warnings (empty if complete).
        """
        warnings: List[str] = []
        cc = context.custom_context or {}

        if not context.repository_name or context.repository_name == "unknown":
            warnings.append("Repository name is unknown")

        # Component contexts must have resolution.
        if "component_id" in cc:
            comp_id = cc.get("component_id")
            if not self._component_exists(str(comp_id)):
                warnings.append(f"Component {comp_id} not found in architecture/analysis data")
            elif cc.get("dependency_count", 0) == 0 and cc.get("route_count", 0) == 0:
                warnings.append(f"Component {comp_id} has no graph or route information")

        return warnings

    def _estimate_tokens(self, *dicts: Optional[Dict[str, Any]]) -> int:
        """Rough token estimate (~4 chars per token) for context size checks."""
        total_chars = 0
        for d in dicts:
            total_chars += len(str(d or {}))
        return total_chars // 4

    def context_in_budget(self, context: LLMContext, max_tokens: Optional[int] = None) -> bool:
        """
        Check whether a context is within the token budget.

        Args:
            context: The context to check.
            max_tokens: Budget ceiling (defaults to 100K).

        Returns:
            True if within budget.
        """
        limit = max_tokens or self.DEFAULT_MAX_TOKENS
        estimate = self._estimate_tokens(
            context.analysis_data,
            context.graph_data,
            context.architecture_data,
            context.health_data,
            context.evolution_data,
            context.custom_context,
        )
        return estimate <= limit

    def optimize_context_size(self, context: LLMContext, max_tokens: Optional[int] = None) -> LLMContext:
        """
        Optimize a context to fit within the token budget while preserving
        essential, verified information.

        Args:
            context: The context to optimize.
            max_tokens: Budget ceiling (defaults to 100K).

        Returns:
            A new LLMContext trimmed to the budget.
        """
        limit = max_tokens or self.DEFAULT_MAX_TOKENS

        if self.context_in_budget(context, limit):
            return context

        # Trim raw artifacts down to focused summaries (smallest relevant context).
        arch = dict(context.architecture_data or {})
        if isinstance(arch.get("components"), list):
            arch["components"] = arch["components"][:20]
        context.architecture_data = arch

        graph = dict(context.graph_data or {})
        if isinstance(graph.get("links"), list):
            graph["links"] = graph["links"][:100]
        context.graph_data = graph

        analysis = dict(context.analysis_data or {})
        if "modules" in analysis and isinstance(analysis["modules"], list):
            analysis["modules"] = analysis["modules"][:10]
        context.analysis_data = analysis

        return context