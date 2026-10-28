"""Adapt deterministic pipeline artifacts into the web UI's view models.

The output shapes mirror ``frontend/src/types/architecture.ts`` (camelCase).
Everything here is derived from Phase 1–5 results; nothing is invented, and
the "explanation"/"aiSummary" fields are deterministic text, not LLM output.
See docs/API.md for the field-by-field mapping.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from app.architecture.schemas import ArchitectureComponent as Component, ArchitectureResult
from app.evolution.architecture_diff import ArchitectureDiffer
from app.health.schemas import HealthResult
from app.models.schemas import AnalysisResult
from app.pipeline import PipelineResult

MAX_GRAPH_NODES = 24
SNIPPET_LINES = 14
MAX_DIFF_CHANGES = 50

LAYER_ORDER = [
    "Presentation", "Application", "Domain", "Data", "Infrastructure",
    "Cross-Cutting", "External", "Testing", "Unknown",
]

ROLE_TO_NODE_TYPE = {
    "route": "gateway",
    "middleware": "gateway",
    "service": "service",
    "authentication": "service",
    "ml": "service",
    "model": "model",
    "database": "datastore",
    "repository": "datastore",
    "external_service": "external",
}


def _node_type(role: str) -> str:
    return ROLE_TO_NODE_TYPE.get(role, "module")


def _layer_index(layer: str) -> int:
    return LAYER_ORDER.index(layer) if layer in LAYER_ORDER else len(LAYER_ORDER) - 1


def _short(component_id: str) -> str:
    """``module:app.routes.users`` → ``app.routes.users``."""
    return component_id.split(":", 1)[-1]


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


@dataclass
class _Unit:
    """A graph node: one component, or a group of components."""

    id: str
    label: str
    members: List[Component]
    group_path: Optional[str] = None
    deps: Counter = field(default_factory=Counter)
    consumers: Counter = field(default_factory=Counter)


def _group_key(component: Component, depth: int) -> str:
    parent = PurePosixPath(component.path).parent.parts
    return "/".join(parent[:depth]) or "(root)"


def _build_units(arch: ArchitectureResult) -> Tuple[List[_Unit], Dict[str, str]]:
    """Return graph units and a component-id → unit-id map."""
    components = list(arch.components)
    if len(components) <= MAX_GRAPH_NODES:
        units = [_Unit(id=c.id, label=_short(c.id), members=[c]) for c in components]
        return units, {c.id: c.id for c in components}

    # Too many to draw legibly: group by package directory, using the
    # deepest grouping that still fits, else the top groups plus "other".
    max_depth = max((len(PurePosixPath(c.path).parent.parts) for c in components), default=1)
    groups: Dict[str, List[Component]] = {}
    for depth in range(max(max_depth, 1), 0, -1):
        groups = defaultdict(list)
        for c in components:
            groups[_group_key(c, depth)].append(c)
        if len(groups) <= MAX_GRAPH_NODES:
            break

    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    if len(ordered) > MAX_GRAPH_NODES:
        head = ordered[: MAX_GRAPH_NODES - 1]
        rest = [c for _, members in ordered[MAX_GRAPH_NODES - 1 :] for c in members]
        ordered = head + [("other", rest)]

    units, mapping = [], {}
    for key, members in ordered:
        unit_id = f"group:{key}"
        units.append(_Unit(id=unit_id, label=key, members=members, group_path=key))
        for c in members:
            mapping[c.id] = unit_id
    return units, mapping


def _snippet(repo_root: Optional[Path], analysis: AnalysisResult, path: str) -> Optional[Dict[str, Any]]:
    """A real ≤14-line excerpt anchored on the file's first definition."""
    if repo_root is None:
        return None
    try:
        lines = (repo_root / path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not any(line.strip() for line in lines):
        return None
    anchors = [c.line for c in analysis.classes if c.file == path]
    for fn in analysis.functions:
        if fn.file == path and fn.class_id is None:
            anchors.append(min([fn.line] + [d.line for d in fn.decorators]))
    start = min(anchors) if anchors else 1
    excerpt = lines[start - 1 : start - 1 + SNIPPET_LINES]
    return {"snippet": "\n".join(excerpt), "snippetLanguage": "python", "snippetStart": start}


def build_graph(
    arch: ArchitectureResult,
    analysis: AnalysisResult,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    units, mapping = _build_units(arch)
    by_id = {u.id: u for u in units}

    edge_weights: Counter = Counter()
    for rel in arch.relationships:
        src, tgt = mapping.get(rel.source_id), mapping.get(rel.target_id)
        if not src or not tgt or src == tgt:
            continue
        edge_weights[(src, tgt)] += 1
        by_id[src].deps[tgt] += 1
        by_id[tgt].consumers[src] += 1

    file_lines = {f.path: f.lines for f in analysis.files}
    degree = Counter()
    for (src, tgt), w in edge_weights.items():
        degree[src] += w
        degree[tgt] += w

    nodes: List[Dict[str, Any]] = []
    for unit in units:
        roles = Counter(c.role.value for c in unit.members)
        layers = Counter(c.layer.value for c in unit.members)
        role = roles.most_common(1)[0][0]
        layer = layers.most_common(1)[0][0]
        # Representative member: most evidence-rich, then largest file.
        rep = max(unit.members, key=lambda c: (c.confidence, file_lines.get(c.path, 0), c.id))
        confidence = round(sum(c.confidence for c in unit.members) / len(unit.members), 2)

        if unit.group_path is None:
            description = f"{role.replace('_', ' ').capitalize()} component in the {layer} layer ({rep.path})."
        else:
            role_text = ", ".join(f"{n} {r}" for r, n in roles.most_common())
            description = f"{len(unit.members)} modules under {unit.group_path}/ ({role_text})."

        metadata: Dict[str, Any] = {
            "role": role,
            "architecturalLayer": layer,
            "dependencies": [by_id[d].label for d, _ in unit.deps.most_common(8)],
            "consumers": [by_id[c].label for c, _ in unit.consumers.most_common(8)],
            "dependencyCount": len(unit.deps),
            "consumerCount": len(unit.consumers),
            "sourcePath": rep.path,
            "lines": [1, max(1, file_lines.get(rep.path, 1))],
            "snippetSignals": [e.description for e in rep.evidence][:6],
        }
        if unit.group_path is not None:
            metadata["groupPath"] = unit.group_path
            metadata["fileCount"] = len(unit.members)
        snippet = _snippet(repo_root, analysis, rep.path)
        if snippet:
            metadata.update(snippet)

        nodes.append({
            "id": unit.id,
            "type": _node_type(role),
            "label": unit.label,
            "description": description,
            "confidence": confidence,
            "layer": _layer_index(layer),
            "metadata": metadata,
        })

    _assign_positions(nodes)

    node_types = {n["id"]: n["type"] for n in nodes}
    edges = [
        {
            "id": f"e{i}",
            "source": src,
            "target": tgt,
            "type": "queries" if node_types[tgt] == "datastore" else "imports",
            "label": f"{w} import{'s' if w != 1 else ''}",
        }
        for i, ((src, tgt), w) in enumerate(sorted(edge_weights.items()))
    ]
    return {"nodes": nodes, "edges": edges}


def _assign_positions(nodes: List[Dict[str, Any]]) -> None:
    """Normalized 0..1 layout: one column per occupied layer, rows spread evenly."""
    columns = sorted({n["layer"] for n in nodes})
    for col_index, layer in enumerate(columns):
        column = sorted((n for n in nodes if n["layer"] == layer), key=lambda n: (n["type"], n["label"]))
        x = col_index / (len(columns) - 1) if len(columns) > 1 else 0.5
        for row, node in enumerate(column):
            node["position"] = {"x": round(x, 4), "y": round((row + 1) / (len(column) + 1), 4)}


# ---------------------------------------------------------------------------
# Summary, health, explanation
# ---------------------------------------------------------------------------


def build_summary(analysis: AnalysisResult, health: HealthResult) -> Dict[str, Any]:
    stats = analysis.statistics
    return {
        "repository": analysis.repository.name,
        "branch": "archive upload",
        "filesScanned": stats.total_files,
        "modules": stats.total_python_files,
        "apiRoutes": stats.total_routes,
        "externalServices": stats.external_dependencies,
        "circularDependencies": health.dependency_metrics.circular_dependency_count,
        "languages": [{"name": "Python", "share": 1}] if stats.total_python_files else [],
    }


def build_health(health: HealthResult) -> Dict[str, Any]:
    overall = health.overall_health
    metrics, strengths = [], []
    for dim in overall.dimensions:
        score = round(dim.score * 100)
        metrics.append({
            "key": dim.name.lower().replace(" ", "_").replace("-", "_"),
            "label": dim.name,
            "value": score,
            "score": score,
            "unit": "/100",
            "hint": dim.issues[0] if dim.issues else f"weight {round(dim.weight * 100)}%",
        })
        if score >= 80 and not dim.issues:
            strengths.append(f"{dim.name} is healthy ({score}/100)")

    cycles = health.dependency_metrics.circular_dependency_count
    warnings = []
    if cycles:
        warnings.append(f"{cycles} circular dependenc{'y' if cycles == 1 else 'ies'} detected")
    else:
        strengths.append("No circular dependencies detected")
    if health.layer_violations:
        v = health.layer_violations[0]
        warnings.append(
            f"{len(health.layer_violations)} layer boundary violation(s), e.g. "
            f"{_short(v.source_component)} ({v.source_layer}) → {_short(v.target_component)} ({v.target_layer})"
        )
    for risk in health.risks[:6]:
        warnings.append(f"{risk.title} ({risk.severity.value}): {risk.description}")

    return {
        "score": round(overall.score * 100),
        "grade": overall.rating.value.capitalize(),
        "strengths": strengths,
        "warnings": warnings,
        "metrics": metrics,
    }


def build_explanation(
    arch: ArchitectureResult, graph: Dict[str, Any], unit_of: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    if not arch.components:
        return None
    in_deg, out_deg = Counter(), Counter()
    for rel in arch.relationships:
        out_deg[rel.source_id] += 1
        in_deg[rel.target_id] += 1
    focus = max(arch.components, key=lambda c: (in_deg[c.id] + out_deg[c.id], c.confidence, c.id))
    role = focus.role.value.replace("_", " ")
    pct = round(focus.confidence * 100)
    verdict = (
        f"ArchLens classifies {focus.path} as a {role} component in the {focus.layer.value} layer "
        f"with {pct}% confidence, based on {len(focus.evidence)} piece(s) of static evidence. "
        f"It is the most connected component: {in_deg[focus.id]} incoming and "
        f"{out_deg[focus.id]} outgoing dependencies."
    )
    return {
        "nodeId": unit_of.get(focus.id, focus.id),
        "question": f"Why is {_short(focus.id)} classified as {role}?",
        "verdict": verdict,
        "evidence": [e.description for e in focus.evidence][:5],
        "confidence": focus.confidence,
    }


def build_overview(
    analysis: AnalysisResult, arch: ArchitectureResult, health: HealthResult
) -> List[str]:
    """Deterministic prose summary (rendered where the UI says "summary")."""
    stats = analysis.statistics
    name = analysis.repository.name
    if not stats.total_python_files:
        return [
            f"No Python modules were found in {name}, so there is no architecture to report. "
            "ArchLens currently analyses Python sources only."
        ]

    paras = [
        f"{name} contains {stats.total_python_files} Python modules ({stats.total_lines:,} lines) "
        f"defining {stats.total_classes} classes and {stats.total_functions} functions, with "
        f"{stats.total_routes} HTTP routes and {stats.external_dependencies} declared external "
        "dependencies."
    ]

    roles = Counter(c.role.value for c in arch.components)
    layers = {c.layer.value for c in arch.components} - {"Unknown"}
    role_text = ", ".join(f"{n} {r.replace('_', ' ')}" for r, n in roles.most_common())
    para = (
        f"ArchLens classified {len(arch.components)} components across {len(layers)} known "
        f"layer(s): {role_text}."
    )
    if arch.patterns:
        patterns = ", ".join(
            f"{p.name.replace('_', ' ')} ({round(p.confidence * 100)}%)" for p in arch.patterns
        )
        para += f" Detected patterns: {patterns}."
    if arch.entry_points:
        para += " Entry point(s): " + ", ".join(e.path for e in arch.entry_points[:3]) + "."
    paras.append(para)

    overall = health.overall_health
    para = f"Overall architecture health is {round(overall.score * 100)}/100 ({overall.rating.value})."
    if overall.dimensions:
        weakest = min(overall.dimensions, key=lambda d: d.score)
        para += f" The weakest dimension is {weakest.name} ({round(weakest.score * 100)}/100)"
        para += f": {weakest.issues[0].lower()}." if weakest.issues else "."
    paras.append(para)

    if health.risks:
        risk = health.risks[0]
        paras.append(f"Top risk: {risk.title} ({risk.severity.value}). {risk.recommendation}")
    else:
        paras.append("No architectural risks crossed the reporting thresholds.")
    return paras


def build_view(run: PipelineResult, repo_root: Optional[Path]) -> Dict[str, Any]:
    """The full UI payload for one pipeline run (everything except metadata)."""
    _, unit_of = _build_units(run.architecture)
    graph = build_graph(run.architecture, run.analysis, repo_root)
    return {
        "empty": run.analysis.statistics.total_python_files == 0,
        "summary": build_summary(run.analysis, run.health),
        "graph": graph,
        "health": build_health(run.health),
        "explanation": build_explanation(run.architecture, graph, unit_of),
        "aiSummary": build_overview(run.analysis, run.architecture, run.health),
    }


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def _change(kind: str, label: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "label": label, "detail": detail}


def build_diff_changes(baseline: ArchitectureResult, current: ArchitectureResult) -> List[Dict[str, str]]:
    raw = ArchitectureDiffer(baseline, current).diff()
    changes: List[Dict[str, str]] = []
    for c in raw["component_changes"]:
        label = _short(c.component_id)
        if c.change_type == "added":
            changes.append(_change("added", label, f"New {c.new_value} component"))
        elif c.change_type == "removed":
            changes.append(_change("removed", label, f"Removed {c.old_value} component"))
        elif c.change_type == "role_changed":
            changes.append(_change("modified", label, f"Role {c.old_value} → {c.new_value}"))
        elif c.change_type == "layer_changed":
            changes.append(_change("modified", label, f"Layer {c.old_value} → {c.new_value}"))
    for d in raw["dependency_changes"]:
        label = f"{_short(d.source_id)} → {_short(d.target_id)}"
        detail = "New dependency" if d.change_type == "added" else "Dependency removed"
        changes.append(_change(d.change_type, label, detail))
    for p in raw["pattern_changes"]:
        detail = "Pattern detected" if p.change_type == "added" else "Pattern no longer detected"
        changes.append(_change(p.change_type, p.pattern_name.replace("_", " "), detail))

    order = {"added": 0, "modified": 1, "removed": 2}
    changes.sort(key=lambda ch: (order[ch["kind"]], ch["label"]))
    if len(changes) > MAX_DIFF_CHANGES:
        hidden = len(changes) - (MAX_DIFF_CHANGES - 1)
        changes = changes[: MAX_DIFF_CHANGES - 1] + [
            _change("modified", f"…and {hidden} more", "Truncated; compare architecture.json for the full list")
        ]
    return changes


def version_label(meta: Dict[str, Any]) -> str:
    created = (meta.get("createdAt") or "").replace("T", " ").rstrip("Z")[:16]
    return f"{meta.get('repository') or 'analysis'} · {created}"

