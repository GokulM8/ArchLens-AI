"""Phase 5 Architecture Diff Engine."""

from typing import List, Dict, Optional
from dataclasses import dataclass

from app.architecture.schemas import ArchitectureResult


@dataclass
class ComponentDiff:
    """Represents a change to a component."""
    component_id: str
    component_name: str
    change_type: str  # "added", "removed", "role_changed", "layer_changed"
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class DependencyDiff:
    """Represents a change to a dependency."""
    source_id: str
    target_id: str
    change_type: str  # "added", "removed"


@dataclass
class PatternDiff:
    """Represents a change to detected patterns."""
    pattern_name: str
    change_type: str  # "added", "removed"


class ArchitectureDiffer:
    """Compares two architecture states semantically."""

    def __init__(self, baseline: ArchitectureResult, current: ArchitectureResult):
        self.baseline = baseline
        self.current = current

    def diff(self) -> Dict:
        """Generate semantic diff between baseline and current architecture."""
        component_diffs = self._diff_components()
        dependency_diffs = self._diff_dependencies()
        pattern_diffs = self._diff_patterns()
        health_changes = self._diff_summary_metrics()

        return {
            "component_changes": component_diffs,
            "dependency_changes": dependency_diffs,
            "pattern_changes": pattern_diffs,
            "summary_changes": health_changes,
            "total_changes": len(component_diffs) + len(dependency_diffs) + len(pattern_diffs),
        }

    def _diff_components(self) -> List[ComponentDiff]:
        """Detect component-level changes."""
        diffs = []

        baseline_comps = {c.id: c for c in self.baseline.components}
        current_comps = {c.id: c for c in self.current.components}

        # Added components
        for comp_id, comp in current_comps.items():
            if comp_id not in baseline_comps:
                diffs.append(
                    ComponentDiff(
                        component_id=comp_id,
                        component_name=comp.name,
                        change_type="added",
                        new_value=comp.role.value,
                    )
                )

        # Removed components
        for comp_id, comp in baseline_comps.items():
            if comp_id not in current_comps:
                diffs.append(
                    ComponentDiff(
                        component_id=comp_id,
                        component_name=comp.name,
                        change_type="removed",
                        old_value=comp.role.value,
                    )
                )

        # Changed components
        for comp_id, current_comp in current_comps.items():
            if comp_id in baseline_comps:
                baseline_comp = baseline_comps[comp_id]

                if baseline_comp.role != current_comp.role:
                    diffs.append(
                        ComponentDiff(
                            component_id=comp_id,
                            component_name=current_comp.name,
                            change_type="role_changed",
                            old_value=baseline_comp.role.value,
                            new_value=current_comp.role.value,
                        )
                    )

                if baseline_comp.layer != current_comp.layer:
                    diffs.append(
                        ComponentDiff(
                            component_id=comp_id,
                            component_name=current_comp.name,
                            change_type="layer_changed",
                            old_value=baseline_comp.layer.value,
                            new_value=current_comp.layer.value,
                        )
                    )

        return diffs

    def _diff_dependencies(self) -> List[DependencyDiff]:
        """Detect dependency-level changes."""
        diffs = []

        baseline_rels = {(r.source_id, r.target_id) for r in self.baseline.relationships}
        current_rels = {(r.source_id, r.target_id) for r in self.current.relationships}

        # Added dependencies
        for source_id, target_id in current_rels - baseline_rels:
            diffs.append(
                DependencyDiff(
                    source_id=source_id,
                    target_id=target_id,
                    change_type="added",
                )
            )

        # Removed dependencies
        for source_id, target_id in baseline_rels - current_rels:
            diffs.append(
                DependencyDiff(
                    source_id=source_id,
                    target_id=target_id,
                    change_type="removed",
                )
            )

        return diffs

    def _diff_patterns(self) -> List[PatternDiff]:
        """Detect architectural pattern changes."""
        diffs = []

        baseline_patterns = {p.name for p in self.baseline.patterns}
        current_patterns = {p.name for p in self.current.patterns}

        # Added patterns
        for pattern_name in current_patterns - baseline_patterns:
            diffs.append(
                PatternDiff(
                    pattern_name=pattern_name,
                    change_type="added",
                )
            )

        # Removed patterns
        for pattern_name in baseline_patterns - current_patterns:
            diffs.append(
                PatternDiff(
                    pattern_name=pattern_name,
                    change_type="removed",
                )
            )

        return diffs

    def _diff_summary_metrics(self) -> Dict:
        """Detect changes in summary metrics."""
        baseline_summary = self.baseline.summary
        current_summary = self.current.summary

        return {
            "component_count_change": current_summary.component_count - baseline_summary.component_count,
            "entry_point_count_change": current_summary.entry_point_count - baseline_summary.entry_point_count,
            "pattern_count_change": current_summary.pattern_count - baseline_summary.pattern_count,
        }
