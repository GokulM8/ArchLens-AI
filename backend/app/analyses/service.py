"""Run uploaded archives through the deterministic pipeline and store the results."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, BinaryIO, Dict

from app.analyses import adapter
from app.analyses.errors import APIError
from app.analyses.ingest import IngestLimits, extract_archive, remove_tree, save_upload
from app.analyses.storage import AnalysisStore, utc_now_iso
from app.architecture.serializer import ArchitectureSerializer
from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)

RESULT_FIELDS = ("summary", "graph", "health", "explanation", "aiSummary")


class AnalysisService:
    def __init__(self, store: AnalysisStore, limits: IngestLimits, max_concurrent: int = 2):
        self.store = store
        self.limits = limits
        self._slots = threading.BoundedSemaphore(max(1, max_concurrent))

    @classmethod
    def from_env(cls) -> "AnalysisService":
        try:
            concurrent = int(os.getenv("ARCHLENS_MAX_CONCURRENT_ANALYSES", "2"))
        except ValueError:
            concurrent = 2
        return cls(AnalysisStore.from_env(), IngestLimits.from_env(), concurrent)

    # -- create -------------------------------------------------------------

    def analyze_zip(self, stream: BinaryIO, filename: str) -> Dict[str, Any]:
        """Blocking: save, extract, analyse, store. Returns the full response."""
        if not self._slots.acquire(blocking=False):
            raise APIError(
                429,
                "too_many_analyses",
                "The server is already running the maximum number of analyses. Try again shortly.",
                headers={"Retry-After": "10"},
            )
        try:
            return self._analyze_zip(stream, filename)
        finally:
            self._slots.release()

    def _analyze_zip(self, stream: BinaryIO, filename: str) -> Dict[str, Any]:
        workdir = Path(tempfile.mkdtemp(prefix="archlens-"))
        try:
            archive = workdir / "upload.zip"
            # Validation errors here happen before anything is stored.
            save_upload(stream, archive, self.limits)
            repo_root = extract_archive(archive, workdir / "src", filename, self.limits)
            archive.unlink()

            self.store.base_dir.mkdir(parents=True, exist_ok=True)
            meta = self.store.create({"kind": "zip", "filename": filename})
            meta["repository"] = repo_root.name
            out_dir = self.store.base_dir / meta["analysisId"]
            try:
                run = run_pipeline(repo_root, out_dir)
                view = adapter.build_view(run, repo_root)
            except Exception as e:  # pipeline bug or unparseable input
                logger.exception("Analysis %s failed", meta["analysisId"])
                meta.update(
                    status="failed",
                    completedAt=utc_now_iso(),
                    error={"code": "analysis_failed", "message": f"{type(e).__name__}: {e}"},
                )
                self.store.save_metadata(meta)
                raise APIError(
                    422,
                    "analysis_failed",
                    f"Analysis failed: {type(e).__name__}: {e}",
                    extra={"analysisId": meta["analysisId"]},
                )

            self.store.save_view(meta["analysisId"], view)
            meta.update(status="completed", completedAt=utc_now_iso(), empty=view["empty"])
            self.store.save_metadata(meta)
            return self._response(meta, view)
        finally:
            remove_tree(workdir)

    # -- read ---------------------------------------------------------------

    def get(self, analysis_id: str) -> Dict[str, Any]:
        meta = self.store.metadata(analysis_id)
        if meta["status"] != "completed":
            return {**meta, **{f: None for f in RESULT_FIELDS}}
        return self._response(meta, self.store.view(analysis_id))

    def graph(self, analysis_id: str) -> Dict[str, Any]:
        return self.store.view(analysis_id)["graph"]

    def health(self, analysis_id: str) -> Dict[str, Any]:
        return self.store.view(analysis_id)["health"]

    def diff(self, analysis_id: str, baseline_id: str) -> Dict[str, Any]:
        if analysis_id == baseline_id:
            raise APIError(400, "same_analysis", "Choose a different analysis to compare against.")
        current_view = self.store.view(analysis_id)
        baseline_view = self.store.view(baseline_id)
        current = ArchitectureSerializer.load_from_file(
            str(self.store.analysis_dir(analysis_id) / "architecture.json")
        )
        baseline = ArchitectureSerializer.load_from_file(
            str(self.store.analysis_dir(baseline_id) / "architecture.json")
        )
        return {
            "versionA": {
                "label": adapter.version_label(self.store.metadata(baseline_id)),
                "graph": baseline_view["graph"],
            },
            "versionB": {
                "label": adapter.version_label(self.store.metadata(analysis_id)),
                "graph": current_view["graph"],
            },
            "changes": adapter.build_diff_changes(baseline, current),
        }

    @staticmethod
    def _response(meta: Dict[str, Any], view: Dict[str, Any]) -> Dict[str, Any]:
        return {**meta, **view}
