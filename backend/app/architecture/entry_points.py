"""Application entry-point detector for ArchLens AI Phase 3.

Identifies execution starting points including web app instances, main scripts, and CLI entry points.
"""

from __future__ import annotations

from typing import List
from app.models.schemas import AnalysisResult
from app.architecture.schemas import EntryPoint, Evidence, EvidenceType


class EntryPointDetector:
    """Detects application entry points deterministically from AnalysisResult."""

    def __init__(self, analysis: AnalysisResult):
        self.analysis = analysis

    def discover(self) -> List[EntryPoint]:
        """Discover all entry points in the analyzed repository."""
        entry_points: List[EntryPoint] = []

        for module in self.analysis.modules:
            path_lower = module.path.lower()
            filename = module.path.split("/")[-1].lower()

            # 1. Main Script Files
            if filename in ("main.py", "app.py", "run.py", "manage.py", "cli.py", "__main__.py"):
                entry_points.append(
                    EntryPoint(
                        id=module.id,
                        path=module.path,
                        name=filename.removesuffix(".py"),
                        entry_type="main_script",
                        confidence=0.85,
                        evidence=[
                            Evidence(
                                type=EvidenceType.PATH,
                                description=f"Filename '{filename}' indicates primary entry point",
                                weight=0.85,
                            )
                        ]
                    )
                )
                continue

            # 2. Check for Web App instantiation or route handlers in module
            # If the module exposes FastAPI/Flask routes or app creation
            matching_routes = [r for r in self.analysis.routes if r.file == module.path]
            if matching_routes and ("main" in filename or "app" in filename):
                entry_points.append(
                    EntryPoint(
                        id=module.id,
                        path=module.path,
                        name=f"{module.path} (Web Application)",
                        entry_type="web_app",
                        confidence=0.90,
                        evidence=[
                            Evidence(
                                type=EvidenceType.FRAMEWORK,
                                description=f"Module exposes {len(matching_routes)} web framework API routes",
                                weight=0.90,
                            )
                        ]
                    )
                )

        return entry_points
