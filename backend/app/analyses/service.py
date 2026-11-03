"""Run uploaded archives through the deterministic pipeline and store the results."""

from __future__ import annotations

import logging
import multiprocessing
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Tuple

from app.analyses import adapter
from app.analyses.errors import APIError
from app.analyses.ingest import IngestLimits, extract_archive, remove_tree, save_upload
from app.analyses.storage import AnalysisStore, public_metadata, utc_now_iso
from app.architecture.serializer import ArchitectureSerializer
from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)

RESULT_FIELDS = ("summary", "graph", "health", "explanation", "aiSummary")
_MAX_ERROR_CHARS = 300


class AnalysisTimeout(Exception):
    """The pipeline exceeded ARCHLENS_ANALYSIS_TIMEOUT_SECONDS and was killed."""


class WorkerError(Exception):
    """An exception raised inside the pipeline subprocess, re-raised in the parent."""

    def __init__(self, type_name: str, message: str):
        super().__init__(message)
        self.type_name = type_name


def _pipeline_worker(repo_root: str, out_dir: str, conn: Any) -> None:
    """Subprocess body: run the pipeline and send back the view (or the error)."""
    try:
        run = run_pipeline(Path(repo_root), Path(out_dir))
        conn.send(("ok", adapter.build_view(run, Path(repo_root))))
    except BaseException as e:  # report everything; the parent decides
        conn.send(("error", type(e).__name__, str(e)))
    finally:
        conn.close()


def safe_error_message(type_name: str, message: str, workdir: Optional[Path]) -> str:
    """``Type: message`` without server paths, bounded in length."""
    if workdir is not None:
        for prefix in (str(workdir / "src") + os.sep, str(workdir) + os.sep, str(workdir)):
            message = message.replace(prefix, "")
    text = f"{type_name}: {message}" if message else type_name
    return text if len(text) <= _MAX_ERROR_CHARS else text[: _MAX_ERROR_CHARS - 1] + "\u2026"


class AnalysisService:
    def __init__(
        self,
        store: AnalysisStore,
        limits: IngestLimits,
        max_concurrent: int = 2,
        timeout_seconds: float = 0,
    ):
        self.store = store
        self.limits = limits
        self._slots = threading.BoundedSemaphore(max(1, max_concurrent))
        # 0 runs the pipeline in-process (no hard limit); > 0 runs it in a
        # subprocess that is killed when the limit is reached.
        self.timeout_seconds = max(0.0, timeout_seconds)

    @classmethod
    def from_env(cls) -> "AnalysisService":
        try:
            concurrent = int(os.getenv("ARCHLENS_MAX_CONCURRENT_ANALYSES", "2"))
        except ValueError:
            concurrent = 2
        try:
            timeout = float(os.getenv("ARCHLENS_ANALYSIS_TIMEOUT_SECONDS", "").strip() or 0)
        except ValueError:
            timeout = 0
        return cls(AnalysisStore.from_env(), IngestLimits.from_env(), concurrent, timeout)

    # -- pipeline execution ---------------------------------------------------

    def _run(self, repo_root: Path, out_dir: Path) -> Dict[str, Any]:
        """Run the pipeline and build the view, honouring the time limit."""
        if not self.timeout_seconds:
            run = run_pipeline(repo_root, out_dir)
            return adapter.build_view(run, repo_root)

        # "spawn": never fork a multi-threaded server process.
        ctx = multiprocessing.get_context("spawn")
        receiver, sender = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=_pipeline_worker, args=(str(repo_root), str(out_dir), sender), daemon=True
        )
        proc.start()
        sender.close()
        try:
            if not receiver.poll(self.timeout_seconds):
                proc.kill()
                raise AnalysisTimeout()
            try:
                message: Tuple[Any, ...] = receiver.recv()
            except EOFError:  # worker died without reporting (e.g. out of memory)
                raise WorkerError("WorkerCrashed", "the analysis process exited unexpectedly")
        finally:
            receiver.close()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
                proc.join()
        if message[0] == "error":
            raise WorkerError(message[1], message[2])
        return message[1]

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
            try:
                self.store.sweep_expired()
                self.store.make_room()
            except OSError:
                logger.exception("Retention sweep failed")
            meta, token = self.store.create({"kind": "zip", "filename": filename})
            meta["repository"] = repo_root.name
            out_dir = self.store.base_dir / meta["analysisId"]
            try:
                view = self._run(repo_root, out_dir)
            except Exception as e:  # pipeline bug, unparseable input or time limit
                if isinstance(e, AnalysisTimeout):
                    code = "analysis_timeout"
                    message = f"Analysis exceeded the {self.timeout_seconds:g} second time limit."
                    logger.warning("Analysis %s timed out", meta["analysisId"])
                else:
                    code = "analysis_failed"
                    type_name = e.type_name if isinstance(e, WorkerError) else type(e).__name__
                    message = safe_error_message(type_name, str(e), workdir)
                    logger.exception("Analysis %s failed", meta["analysisId"])
                meta.update(
                    status="failed",
                    completedAt=utc_now_iso(),
                    error={"code": code, "message": message},
                )
                self.store.save_metadata(meta)
                raise APIError(
                    422,
                    code,
                    f"Analysis failed: {message}",
                    extra={"analysisId": meta["analysisId"], "accessToken": token},
                )

            self.store.save_view(meta["analysisId"], view)
            meta.update(status="completed", completedAt=utc_now_iso(), empty=view["empty"])
            self.store.save_metadata(meta)
            # The only time the token is returned; the server keeps just its hash.
            return {**self._response(meta, view), "accessToken": token}
        finally:
            remove_tree(workdir)

    # -- read ---------------------------------------------------------------

    def get(self, analysis_id: str) -> Dict[str, Any]:
        meta = self.store.metadata(analysis_id)
        if meta["status"] != "completed":
            return {**public_metadata(meta), **{f: None for f in RESULT_FIELDS}}
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
        return {**public_metadata(meta), **view}
