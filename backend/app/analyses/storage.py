"""Filesystem storage for analyses: one directory per analysis id.

Layout under ``ARCHLENS_ANALYSES_DIR`` (default ``output/analyses``)::

    <analysis_id>/metadata.json   status, repository, timestamps, error
    <analysis_id>/view.json       adapted AnalysisResult served to the UI
    <analysis_id>/{analysis,graph,architecture,health,evolution}.json

The directory is the source of truth, so stored analyses survive restarts for
as long as the directory does. There is no retention policy or access control.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.analyses.errors import APIError

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, data: Any) -> None:
    """Write atomically so readers never see a half-written file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


class AnalysisStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    @classmethod
    def from_env(cls) -> "AnalysisStore":
        return cls(Path(os.getenv("ARCHLENS_ANALYSES_DIR", "output/analyses")))

    # -- paths -------------------------------------------------------------

    def analysis_dir(self, analysis_id: str) -> Path:
        """Directory for a *validated* id; unknown or malformed ids are 404."""
        if not _ID_RE.match(analysis_id or ""):
            raise APIError(404, "analysis_not_found", "Analysis not found.")
        path = self.base_dir / analysis_id
        if not (path / "metadata.json").is_file():
            raise APIError(404, "analysis_not_found", "Analysis not found.")
        return path

    def create(self, source: Dict[str, Any]) -> Dict[str, Any]:
        analysis_id = uuid.uuid4().hex
        path = self.base_dir / analysis_id
        path.mkdir(parents=True)
        meta = {
            "analysisId": analysis_id,
            "status": "running",
            "createdAt": utc_now_iso(),
            "completedAt": None,
            "repository": None,
            "source": source,
            "empty": False,
            "error": None,
        }
        _write_json(path / "metadata.json", meta)
        return meta

    # -- metadata / results -------------------------------------------------

    def save_metadata(self, meta: Dict[str, Any]) -> None:
        _write_json(self.base_dir / meta["analysisId"] / "metadata.json", meta)

    def save_view(self, analysis_id: str, view: Dict[str, Any]) -> None:
        _write_json(self.base_dir / analysis_id / "view.json", view)

    def metadata(self, analysis_id: str) -> Dict[str, Any]:
        return self._read(self.analysis_dir(analysis_id) / "metadata.json")

    def view(self, analysis_id: str) -> Dict[str, Any]:
        """The adapted result for a completed analysis (409 otherwise)."""
        meta = self.metadata(analysis_id)
        if meta["status"] != "completed":
            raise APIError(
                409, "analysis_not_completed", f"Analysis is {meta['status']}; no results available."
            )
        return self._read(self.base_dir / analysis_id / "view.json")

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.base_dir.is_dir():
            return []
        items = []
        for child in self.base_dir.iterdir():
            meta_path = child / "metadata.json"
            if _ID_RE.match(child.name) and meta_path.is_file():
                meta = self._read_optional(meta_path)
                if meta:
                    items.append(meta)
        items.sort(key=lambda m: m.get("createdAt") or "", reverse=True)
        return items[:limit]

    @staticmethod
    def _read(path: Path) -> Dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _read_optional(path: Path) -> Optional[Dict[str, Any]]:
        try:
            return AnalysisStore._read(path)
        except (OSError, ValueError):
            return None
