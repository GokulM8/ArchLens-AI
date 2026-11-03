"""Filesystem storage for analyses: one directory per analysis id.

Layout under ``ARCHLENS_ANALYSES_DIR`` (default ``output/analyses``)::

    <analysis_id>/metadata.json   status, repository, timestamps, error, token hash
    <analysis_id>/view.json       adapted AnalysisResult served to the UI
    <analysis_id>/{analysis,graph,architecture,health,evolution}.json

Access: every analysis has a random access token, returned once when it is
created. Only its SHA-256 hash is stored, and reads require the token, so an
analysis id alone grants nothing and there is no way to list other visitors'
analyses. A missing or wrong token is indistinguishable from an unknown id.

Retention: analyses older than ``ARCHLENS_RETENTION_HOURS`` (default 72;
0 keeps them forever) are deleted on access and by a sweep on every upload.

Capacity: ``ARCHLENS_MAX_STORED_ANALYSES`` (default 0 = unlimited) caps how many
analyses are kept at once; before a new one is stored the oldest are evicted.
Use it on small or ephemeral disks (e.g. Render's free plan).

Durability: storage is plain files. On a host with an ephemeral filesystem
every analysis is lost on restart, redeploy or spin-down; clients must treat a
404 for a previously created analysis as "gone" (the frontend does).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.analyses.errors import APIError

_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_NOT_FOUND = ("analysis_not_found", "Analysis not found.")
# Internal metadata fields never returned to clients.
_PRIVATE_FIELDS = ("accessTokenHash",)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _write_json(path: Path, data: Any) -> None:
    """Write atomically so readers never see a half-written file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def public_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in meta.items() if k not in _PRIVATE_FIELDS}


class AnalysisStore:
    def __init__(self, base_dir: Path, retention_hours: float = 72, max_stored: int = 0):
        self.base_dir = Path(base_dir)
        self.retention = timedelta(hours=retention_hours) if retention_hours > 0 else None
        self.max_stored = max(0, max_stored)

    @classmethod
    def from_env(cls) -> "AnalysisStore":
        try:
            retention = float(os.getenv("ARCHLENS_RETENTION_HOURS", "").strip() or 72)
        except ValueError:
            retention = 72
        try:
            max_stored = int(os.getenv("ARCHLENS_MAX_STORED_ANALYSES", "").strip() or 0)
        except ValueError:
            max_stored = 0
        return cls(Path(os.getenv("ARCHLENS_ANALYSES_DIR", "output/analyses")), retention, max_stored)

    # -- paths / access -------------------------------------------------------

    def analysis_dir(self, analysis_id: str) -> Path:
        """Directory for a *validated* id; unknown or malformed ids are 404."""
        if not _ID_RE.match(analysis_id or ""):
            raise APIError(404, *_NOT_FOUND)
        path = self.base_dir / analysis_id
        if not (path / "metadata.json").is_file():
            raise APIError(404, *_NOT_FOUND)
        return path

    def authorize(self, analysis_id: str, token: Optional[str]) -> None:
        """404 unless ``token`` is this analysis's access token and it has not expired."""
        path = self.analysis_dir(analysis_id)
        meta = self._read_optional(path / "metadata.json") or {}
        stored = meta.get("accessTokenHash")
        # Analyses stored before tokens existed have no hash and stay inaccessible.
        if not token or not isinstance(stored, str) or not hmac.compare_digest(_hash_token(token), stored):
            raise APIError(404, *_NOT_FOUND)
        if self._expired(meta):
            self.delete(analysis_id)
            raise APIError(404, *_NOT_FOUND)

    def create(self, source: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """New running analysis; returns its metadata and the one-time access token."""
        analysis_id = uuid.uuid4().hex
        token = secrets.token_urlsafe(32)
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
            "accessTokenHash": _hash_token(token),
        }
        _write_json(path / "metadata.json", meta)
        return meta, token

    def delete(self, analysis_id: str) -> None:
        path = self.analysis_dir(analysis_id)
        shutil.rmtree(path, ignore_errors=True)

    # -- retention --------------------------------------------------------------

    def _expired(self, meta: Dict[str, Any]) -> bool:
        if self.retention is None:
            return False
        created = _parse_iso(meta.get("createdAt"))
        return created is None or datetime.now(timezone.utc) - created > self.retention

    def sweep_expired(self) -> int:
        """Delete every analysis past the retention period. Returns how many."""
        if self.retention is None or not self.base_dir.is_dir():
            return 0
        removed = 0
        for child in self.base_dir.iterdir():
            if not _ID_RE.match(child.name) or not child.is_dir():
                continue
            meta = self._read_optional(child / "metadata.json")
            # Unreadable metadata: fall back to the directory's age.
            if meta is None:
                meta = {
                    "createdAt": datetime.fromtimestamp(child.stat().st_mtime, timezone.utc).isoformat()
                }
            if self._expired(meta):
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        return removed

    def make_room(self) -> int:
        """Evict the oldest analyses so one more fits under ``max_stored``. Returns how many."""
        if not self.max_stored or not self.base_dir.is_dir():
            return 0
        entries = []
        for child in self.base_dir.iterdir():
            if not _ID_RE.match(child.name) or not child.is_dir():
                continue
            meta = self._read_optional(child / "metadata.json") or {}
            created = _parse_iso(meta.get("createdAt")) or datetime.fromtimestamp(
                child.stat().st_mtime, timezone.utc
            )
            entries.append((created, child))
        excess = len(entries) - (self.max_stored - 1)
        if excess <= 0:
            return 0
        entries.sort(key=lambda e: e[0])
        for _, child in entries[:excess]:
            shutil.rmtree(child, ignore_errors=True)
        return excess

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
