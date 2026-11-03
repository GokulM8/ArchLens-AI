"""Integration tests for the /v1/analyses API (docs/API.md).

Every test runs the real deterministic pipeline over small ZIP archives built
in tmp_path; nothing is mocked except where a failure path is being forced.
"""

import io
import stat
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analyses import router as analyses_router
from app.analyses import service as analyses_service
from app.api import create_app

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "fastapi_project"

FRONTEND_RESULT_KEYS = {"summary", "graph", "health", "explanation", "aiSummary"}


def zip_dir(root: Path, prefix: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and not path.name.startswith("._"):
                zf.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
    return buf.getvalue()


def zip_entries(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture
def analyses_dir(tmp_path, monkeypatch):
    path = tmp_path / "analyses"
    monkeypatch.setenv("ARCHLENS_ANALYSES_DIR", str(path))
    analyses_router.get_analysis_service.cache_clear()
    yield path
    analyses_router.get_analysis_service.cache_clear()


@pytest.fixture
def client(analyses_dir):
    return TestClient(create_app())


@pytest.fixture(scope="module")
def example_zip():
    return zip_dir(EXAMPLE, "fastapi_project-main")


def upload(client, data: bytes, filename="repo.zip"):
    return client.post(
        "/v1/analyses",
        files={"file": (filename, data, "application/zip")},
        data={"kind": "zip"},
    )


def auth(created: dict) -> dict:
    """Headers carrying the access token returned by POST /v1/analyses."""
    return {"X-ArchLens-Token": created["accessToken"]}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreateAndRead:
    def test_upload_runs_pipeline_and_returns_frontend_shape(self, client, example_zip, analyses_dir):
        r = upload(client, example_zip)
        assert r.status_code == 201, r.text
        body = r.json()
        assert FRONTEND_RESULT_KEYS <= body.keys()
        assert body["status"] == "completed"
        assert body["empty"] is False
        # Shared top-level folder is stripped and used as the repository name.
        assert body["repository"] == "fastapi_project-main"

        summary = body["summary"]
        assert summary["modules"] == 18
        assert summary["apiRoutes"] == 16
        assert summary["circularDependencies"] == 0

        graph = body["graph"]
        ids = {n["id"] for n in graph["nodes"]}
        assert len(graph["nodes"]) == 18
        assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
        for node in graph["nodes"]:
            assert 0 <= node["position"]["x"] <= 1 and 0 <= node["position"]["y"] <= 1
            assert node["type"] in {"client", "gateway", "service", "module", "model", "datastore", "cache", "external"}

        # Snippets are real source read from the upload.
        model = next(n for n in graph["nodes"] if n["id"] == "module:app.models.prediction")
        assert "class PredictionType" in model["metadata"]["snippet"]

        health = body["health"]
        assert 0 <= health["score"] <= 100
        assert len(health["metrics"]) == 5
        assert body["explanation"]["nodeId"] in ids

        # All five Phase 1–5 artifacts are persisted next to the view.
        stored = analyses_dir / body["analysisId"]
        for name in ("analysis", "graph", "architecture", "health", "evolution", "view", "metadata"):
            assert (stored / f"{name}.json").is_file()

    def test_results_are_retrievable_and_survive_a_new_app(self, client, example_zip):
        created = upload(client, example_zip).json()
        aid = created["analysisId"]

        analyses_router.get_analysis_service.cache_clear()
        fresh = TestClient(create_app())
        got = fresh.get(f"/v1/analyses/{aid}", headers=auth(created))
        assert got.status_code == 200
        assert got.json()["graph"] == created["graph"]
        assert "accessToken" not in got.json()
        assert fresh.get(f"/v1/analyses/{aid}/graph", headers=auth(created)).json() == created["graph"]
        assert fresh.get(f"/v1/analyses/{aid}/health", headers=auth(created)).json() == created["health"]

    def test_archive_without_python_is_empty_not_error(self, client):
        r = upload(client, zip_entries({"README.md": "# docs only\n"}), "docs.zip")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["empty"] is True
        assert body["graph"] == {"nodes": [], "edges": []}
        assert body["explanation"] is None
        assert body["summary"]["languages"] == []

    def test_temporary_extraction_directory_is_removed(self, client, example_zip, tmp_path, monkeypatch):
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(scratch))
        assert upload(client, example_zip).status_code == 201
        assert list(scratch.iterdir()) == []

    def test_large_repositories_are_grouped_by_package(self, client):
        entries = {}
        for pkg in range(6):
            entries[f"app/pkg{pkg}/__init__.py"] = ""
            for mod in range(6):
                entries[f"app/pkg{pkg}/mod{mod}.py"] = f"from app.pkg{(pkg + 1) % 6} import mod0\n"
        body = upload(client, zip_entries(entries), "big.zip").json()
        nodes = body["graph"]["nodes"]
        assert len(nodes) <= 24
        assert all(n["id"].startswith("group:") for n in nodes)
        assert sum(n["metadata"]["fileCount"] for n in nodes) == 42


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


class TestDiff:
    def test_diff_between_two_uploads(self, client, example_zip, tmp_path):
        base_created = upload(client, example_zip).json()
        base = base_created["analysisId"]

        changed = tmp_path / "changed"
        import shutil

        shutil.copytree(EXAMPLE, changed, ignore=shutil.ignore_patterns("__pycache__", "._*"))
        (changed / "app" / "services" / "cache_service.py").write_text(
            "from app.services.database import get_session\n\ndef cached():\n    return get_session\n"
        )
        current_created = upload(client, zip_dir(changed, "fastapi_project-main")).json()
        current = current_created["analysisId"]

        headers = {**auth(current_created), "X-ArchLens-Baseline-Token": base_created["accessToken"]}
        r = client.get(f"/v1/analyses/{current}/diff", params={"baseline": base}, headers=headers)
        assert r.status_code == 200, r.text
        diff = r.json()
        assert diff["versionA"]["graph"]["nodes"] and diff["versionB"]["graph"]["nodes"]
        added = [c for c in diff["changes"] if c["kind"] == "added"]
        assert any(c["label"] == "app.services.cache_service" for c in added)

    def test_diff_requires_baseline(self, client, example_zip):
        created = upload(client, example_zip).json()
        r = client.get(f"/v1/analyses/{created['analysisId']}/diff", headers=auth(created))
        assert r.status_code == 400
        assert r.json()["code"] == "missing_baseline"

    def test_diff_against_itself_is_rejected(self, client, example_zip):
        created = upload(client, example_zip).json()
        aid = created["analysisId"]
        r = client.get(f"/v1/analyses/{aid}/diff", params={"baseline": aid}, headers=auth(created))
        assert r.status_code == 400
        assert r.json()["code"] == "same_analysis"

    def test_diff_with_unknown_baseline_is_404(self, client, example_zip):
        created = upload(client, example_zip).json()
        r = client.get(
            f"/v1/analyses/{created['analysisId']}/diff", params={"baseline": "0" * 32}, headers=auth(created)
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Validation and safety
# ---------------------------------------------------------------------------


class TestErrors:
    def test_git_urls_are_not_supported(self, client):
        r = client.post("/v1/analyses", json={"kind": "git", "source": "https://github.com/a/b"})
        assert r.status_code == 501
        assert r.json() == {"detail": r.json()["detail"], "code": "git_not_supported"}

    @pytest.mark.parametrize("aid", ["0" * 32, "not-an-id", "..%2F..%2Fetc"])
    def test_unknown_or_malformed_ids_are_404(self, client, aid):
        r = client.get(f"/v1/analyses/{aid}")
        assert r.status_code == 404
        assert r.json()["code"] in {"analysis_not_found", "not_found"}

    def test_non_zip_filename_rejected(self, client):
        r = upload(client, b"hello", "repo.tar.gz")
        assert r.status_code == 400
        assert r.json()["code"] == "invalid_archive"

    def test_corrupt_zip_rejected(self, client):
        r = upload(client, b"PK\x03\x04 definitely not a zip")
        assert r.status_code == 400
        assert r.json()["code"] == "invalid_archive"

    def test_missing_file_field(self, client):
        r = client.post("/v1/analyses", data={"kind": "zip"}, files={"other": ("x", b"y")})
        assert r.status_code == 422
        assert r.json()["code"] == "validation_error"

    def test_unsupported_media_type(self, client):
        r = client.post("/v1/analyses", content=b"x", headers={"content-type": "text/plain"})
        assert r.status_code == 415

    @pytest.mark.parametrize(
        "name", ["../evil.py", "repo/../../evil.py", "/etc/evil.py", "C:/evil.py", "repo\\..\\evil.py"]
    )
    def test_unsafe_member_paths_rejected(self, client, name, tmp_path):
        r = upload(client, zip_entries({"repo/ok.py": "x = 1\n", name: "boom = 1\n"}))
        assert r.status_code == 400, r.text
        assert r.json()["code"] == "invalid_archive"
        assert not (tmp_path / "evil.py").exists()

    def test_symlink_member_rejected(self, client):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("repo/ok.py", "x = 1\n")
            link = zipfile.ZipInfo("repo/link.py")
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(link, "/etc/passwd")
        r = upload(client, buf.getvalue())
        assert r.status_code == 400
        assert "Symlink" in r.json()["detail"]

    def test_upload_size_limit(self, client, monkeypatch):
        monkeypatch.setenv("ARCHLENS_MAX_UPLOAD_MB", "1")
        analyses_router.get_analysis_service.cache_clear()
        r = upload(client, b"0" * (2 * 1024 * 1024))
        assert r.status_code == 413
        assert r.json()["code"] == "upload_too_large"

    def test_uncompressed_size_limit(self, client, monkeypatch):
        monkeypatch.setenv("ARCHLENS_MAX_UNCOMPRESSED_MB", "1")
        analyses_router.get_analysis_service.cache_clear()
        bomb = zip_entries({"repo/a.py": "#" * (3 * 1024 * 1024)})  # compresses to a few KB
        r = upload(client, bomb)
        assert r.status_code == 400
        assert "uncompressed" in r.json()["detail"]

    def test_member_count_limit(self, client, monkeypatch):
        monkeypatch.setenv("ARCHLENS_MAX_ARCHIVE_FILES", "3")
        analyses_router.get_analysis_service.cache_clear()
        r = upload(client, zip_entries({f"repo/m{i}.py": "" for i in range(5)}))
        assert r.status_code == 400
        assert "more than 3" in r.json()["detail"]

    def test_validation_errors_use_v1_shape(self, client, example_zip):
        created = upload(client, example_zip).json()
        r = client.post(
            f"/v1/analyses/{created['analysisId']}/copilot", json={"question": ""}, headers=auth(created)
        )
        assert r.status_code == 422
        body = r.json()
        assert body["code"] == "validation_error" and isinstance(body["detail"], str)

    def test_pipeline_failure_is_recorded(self, client, example_zip, monkeypatch):
        def boom(*_a, **_k):
            raise ValueError("synthetic failure")

        monkeypatch.setattr(analyses_service, "run_pipeline", boom)
        r = upload(client, example_zip)
        assert r.status_code == 422
        body = r.json()
        assert body["code"] == "analysis_failed" and "synthetic failure" in body["detail"]

        aid = body["analysisId"]
        meta = client.get(f"/v1/analyses/{aid}", headers=auth(body)).json()
        assert meta["status"] == "failed" and meta["graph"] is None
        assert meta["error"]["code"] == "analysis_failed"
        r = client.get(f"/v1/analyses/{aid}/graph", headers=auth(body))
        assert r.status_code == 409
        assert r.json()["code"] == "analysis_not_completed"

    def test_concurrency_limit_returns_429(self, client, example_zip):
        service = analyses_router.get_analysis_service()
        held = [service._slots.acquire(blocking=False) for _ in range(2)]
        try:
            r = upload(client, example_zip)
        finally:
            for ok in held:
                if ok:
                    service._slots.release()
        assert r.status_code == 429
        assert r.headers["retry-after"] == "10"


class TestHealth:
    def test_health_reports_storage(self, client, analyses_dir):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["storage_writable"] is True

    def test_health_fails_when_storage_unwritable(self, tmp_path, monkeypatch):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("file in the way")
        monkeypatch.setenv("ARCHLENS_ANALYSES_DIR", str(blocker / "analyses"))
        r = TestClient(create_app()).get("/health")
        assert r.status_code == 503
        assert r.json()["status"] == "unavailable"
