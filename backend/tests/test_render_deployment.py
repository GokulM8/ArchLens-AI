"""Behaviour the Render (two-service, no nginx, ephemeral disk) deployment relies on.

Covers $PORT handling, CORS for a separate frontend origin, the health check,
running without LLM credentials, visitor isolation, ephemeral/capped storage,
upload rate and size limits, the analysis time limit and safe errors.
"""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import serve
from app.analyses import router as analyses_router
from app.analyses import service as analyses_service
from app.analyses.ingest import IngestLimits
from app.analyses.safeguards import UploadGuard, client_key
from app.analyses.service import AnalysisService, safe_error_message
from app.analyses.storage import AnalysisStore
from app.api import create_app
from app.http_middleware import cors_origins

from tests.test_v1_analyses import auth, upload, zip_entries

REPO = {
    "shop/__init__.py": "",
    "shop/api.py": "from shop import store\n\ndef handler():\n    return store.load()\n",
    "shop/store.py": "def load():\n    return []\n",
}
FRONTEND = "https://archlens-frontend.onrender.com"
LLM_VARS = ("ARCHLENS_LLM_PROVIDER", "ARCHLENS_LLM_API_KEY", "ARCHLENS_LLM_MODEL", "ARCHLENS_LLM_BASE_URL")
RENDER_VARS = (
    "FRONTEND_ORIGIN",
    "ARCHLENS_CORS_ORIGINS",
    "ARCHLENS_MAX_STORED_ANALYSES",
    "ARCHLENS_RETENTION_HOURS",
    "ARCHLENS_UPLOAD_RATE_PER_HOUR",
    "ARCHLENS_UPLOAD_GLOBAL_PER_HOUR",
    "ARCHLENS_TRUSTED_PROXY_HOPS",
    "ARCHLENS_ANALYSIS_TIMEOUT_SECONDS",
    "ARCHLENS_ENABLE_LEGACY_LLM_API",
    "ARCHLENS_MAX_UPLOAD_MB",
)


@pytest.fixture
def analyses_dir(tmp_path, monkeypatch):
    for name in RENDER_VARS:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "analyses"
    monkeypatch.setenv("ARCHLENS_ANALYSES_DIR", str(path))
    analyses_router.get_analysis_service.cache_clear()
    yield path
    analyses_router.get_analysis_service.cache_clear()


def make_client():
    analyses_router.get_analysis_service.cache_clear()
    return TestClient(create_app())


@pytest.fixture
def client(analyses_dir):
    return make_client()


def create(client, entries=REPO, name="shop.zip"):
    r = upload(client, zip_entries(entries), name)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# $PORT
# ---------------------------------------------------------------------------


class TestPort:
    def test_uses_render_port(self):
        assert serve.resolve_port({"PORT": "10000"}) == 10000

    @pytest.mark.parametrize("value", [None, "", "abc", "0", "70000", "-1"])
    def test_falls_back_to_8000(self, value):
        env = {} if value is None else {"PORT": value}
        assert serve.resolve_port(env) == 8000

    def test_binds_all_interfaces_with_one_worker(self):
        opts = serve.uvicorn_options({"PORT": "10000"})
        assert opts["host"] == "0.0.0.0"
        assert opts["port"] == 10000
        assert opts["workers"] == 1
        assert opts["proxy_headers"] is True

    def test_dockerfile_starts_through_app_serve(self):
        dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
        assert 'CMD ["python", "-m", "app.serve"]' in dockerfile
        assert "os.environ.get('PORT')" in dockerfile  # healthcheck follows $PORT


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCors:
    def test_origin_parsing(self):
        env = {"FRONTEND_ORIGIN": f"{FRONTEND}/", "ARCHLENS_CORS_ORIGINS": "http://localhost:3000, *, ftp://x, https://a.b/path"}
        assert cors_origins(env) == [FRONTEND, "http://localhost:3000"]

    def test_no_origins_means_no_cors(self, analyses_dir):
        r = make_client().get("/health", headers={"Origin": FRONTEND})
        assert "access-control-allow-origin" not in r.headers

    def test_frontend_origin_is_allowed_without_credentials(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("FRONTEND_ORIGIN", FRONTEND)
        c = make_client()
        r = c.options(
            "/v1/analyses/abc",
            headers={
                "Origin": FRONTEND,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-archlens-token",
            },
        )
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == FRONTEND
        assert "access-control-allow-credentials" not in r.headers
        assert "x-archlens-token" in r.headers["access-control-allow-headers"].lower()

        r = c.get("/v1/copilot/status", headers={"Origin": FRONTEND})
        assert r.headers["access-control-allow-origin"] == FRONTEND
        assert "retry-after" in r.headers["access-control-expose-headers"].lower()

    def test_other_origins_are_refused(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("FRONTEND_ORIGIN", FRONTEND)
        c = make_client()
        r = c.options(
            "/v1/analyses",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
        assert r.status_code == 400
        assert "access-control-allow-origin" not in r.headers
        r = c.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers

    def test_wildcard_is_never_honoured(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_CORS_ORIGINS", "*")
        r = make_client().get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers

    def test_errors_carry_cors_headers(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("FRONTEND_ORIGIN", FRONTEND)
        r = make_client().get("/v1/analyses/" + "0" * 32, headers={"Origin": FRONTEND})
        assert r.status_code == 404
        assert r.headers["access-control-allow-origin"] == FRONTEND


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_ok_and_reveals_no_paths(self, client, analyses_dir):
        for method in ("get", "head"):
            r = getattr(client, method)("/health")
            assert r.status_code == 200
        body = client.get("/health").json()
        assert body["status"] == "ok" and body["storage_writable"] is True
        assert str(analyses_dir) not in json.dumps(body)
        assert set(body) == {"status", "storage_writable", "llm_configured"}

    def test_503_when_storage_unwritable(self, tmp_path, monkeypatch, analyses_dir):
        blocker = tmp_path / "file"
        blocker.write_text("x")
        monkeypatch.setenv("ARCHLENS_ANALYSES_DIR", str(blocker / "analyses"))
        r = make_client().get("/health")
        assert r.status_code == 503 and r.json()["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Missing LLM credentials
# ---------------------------------------------------------------------------


class TestWithoutLLM:
    @pytest.fixture(autouse=True)
    def _no_llm(self, monkeypatch):
        for name in LLM_VARS:
            monkeypatch.delenv(name, raising=False)

    def test_starts_and_analyses_deterministically(self, client):
        assert client.get("/health").json()["llm_configured"] is False
        created = create(client)
        assert created["status"] == "completed" and created["graph"]["nodes"]

    def test_provider_without_key_still_starts(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "nvidia")
        c = make_client()
        assert c.get("/health").status_code == 200
        status = c.get("/v1/copilot/status").json()
        assert status["enabled"] is False and status["configurationError"]
        created = create(c)
        r = c.post(f"/v1/analyses/{created['analysisId']}/copilot", json={"question": "Why?"}, headers=auth(created))
        assert r.status_code == 503 and r.json()["code"] == "llm_not_configured"

    def test_key_never_appears_in_responses(self, analyses_dir, monkeypatch):
        secret = "nvapi-SECRET-should-never-leak"
        monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "nvidia")
        monkeypatch.setenv("ARCHLENS_LLM_API_KEY", secret)
        c = make_client()
        for path in ("/health", "/v1/copilot/status", "/llm/status", "/openapi.json"):
            assert secret not in c.get(path).text


# ---------------------------------------------------------------------------
# Visitor isolation
# ---------------------------------------------------------------------------


class TestVisitorIsolation:
    def test_one_visitors_token_opens_nothing_else(self, client):
        alice, bob = create(client), create(client)
        a, b = alice["analysisId"], bob["analysisId"]
        for path in ("", "/graph", "/health"):
            assert client.get(f"/v1/analyses/{a}{path}", headers=auth(alice)).status_code == 200
            r = client.get(f"/v1/analyses/{b}{path}", headers=auth(alice))
            assert r.status_code == 404 and r.json()["code"] == "analysis_not_found"
            assert client.get(f"/v1/analyses/{b}{path}").status_code == 404
        assert client.delete(f"/v1/analyses/{b}", headers=auth(alice)).status_code == 404
        r = client.post(f"/v1/analyses/{b}/copilot", json={"question": "x"}, headers=auth(alice))
        assert r.status_code == 404
        # Diff needs the baseline's own token too.
        r = client.get(f"/v1/analyses/{a}/diff?baseline={b}", headers={**auth(alice), "X-ArchLens-Baseline-Token": alice["accessToken"]})
        assert r.status_code == 404

    def test_no_listing_or_global_history(self, client):
        create(client)
        assert client.get("/v1/analyses").status_code in (404, 405)

    def test_legacy_global_llm_routes_can_be_disabled(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_ENABLE_LEGACY_LLM_API", "false")
        c = make_client()
        for path in ("/llm/status", "/llm/conversations/abc"):
            assert c.get(path).status_code == 404
        assert c.post("/llm/ask", json={"question": "x"}).status_code == 404
        assert c.get("/health").status_code == 200

    def test_legacy_routes_stay_on_by_default(self, client):
        assert client.get("/llm/status").status_code == 200


# ---------------------------------------------------------------------------
# Ephemeral storage
# ---------------------------------------------------------------------------


class TestEphemeralStorage:
    def test_wiped_disk_means_404_not_500(self, client, analyses_dir):
        created = create(client)
        import shutil

        shutil.rmtree(analyses_dir)  # what a restart / spin-down does on Render
        fresh = make_client()
        r = fresh.get(f"/v1/analyses/{created['analysisId']}", headers=auth(created))
        assert r.status_code == 404 and r.json()["code"] == "analysis_not_found"
        assert fresh.get("/health").status_code == 200  # recreates the directory
        assert create(fresh)["status"] == "completed"

    def test_upload_leaves_no_archive_or_temp_files(self, client, analyses_dir, tmp_path, monkeypatch):
        import tempfile

        scratch = tmp_path / "tmp"
        scratch.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(scratch))
        created = create(client)
        assert list(scratch.iterdir()) == []
        stored = {p.name for p in (analyses_dir / created["analysisId"]).iterdir()}
        assert not any(name.endswith(".zip") for name in stored)

    def test_capacity_evicts_oldest(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_MAX_STORED_ANALYSES", "2")
        c = make_client()
        first = create(c)
        time.sleep(1.1)  # createdAt has one-second resolution
        second = create(c)
        time.sleep(1.1)
        third = create(c)
        ids = {p.name for p in analyses_dir.iterdir() if p.is_dir()}
        assert ids == {second["analysisId"], third["analysisId"]}
        assert c.get(f"/v1/analyses/{first['analysisId']}", headers=auth(first)).status_code == 404

    def test_make_room_unlimited_by_default(self, tmp_path):
        assert AnalysisStore(tmp_path).make_room() == 0


# ---------------------------------------------------------------------------
# Upload limits, rate limits, timeouts, errors
# ---------------------------------------------------------------------------


class _Req:
    def __init__(self, xff=None, peer="10.0.0.1"):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = type("C", (), {"host": peer})()


class TestAbuseLimits:
    def test_client_key_ignores_spoofed_forwarded_for(self, monkeypatch):
        monkeypatch.delenv("ARCHLENS_TRUSTED_PROXY_HOPS", raising=False)
        assert client_key(_Req("1.1.1.1, 2.2.2.2")) == "10.0.0.1"
        monkeypatch.setenv("ARCHLENS_TRUSTED_PROXY_HOPS", "1")
        assert client_key(_Req("6.6.6.6, 203.0.113.9")) == "203.0.113.9"
        assert client_key(_Req()) == "10.0.0.1"

    def test_upload_guard_per_client_and_global(self):
        now = [1000.0]
        guard = UploadGuard(per_client=2, global_limit=3, clock=lambda: now[0])
        guard.admit("a")
        guard.admit("a")
        with pytest.raises(Exception) as e:
            guard.admit("a")
        assert e.value.code == "upload_rate_limited" and int(e.value.headers["Retry-After"]) > 0
        guard.admit("b")
        with pytest.raises(Exception) as e:
            guard.admit("c")
        assert e.value.code == "server_upload_limit"
        now[0] += 3601
        guard.admit("a")

    def test_upload_rate_limit_over_http(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_UPLOAD_RATE_PER_HOUR", "1")
        monkeypatch.setenv("FRONTEND_ORIGIN", FRONTEND)
        c = make_client()
        create(c)
        r = c.post(
            "/v1/analyses",
            files={"file": ("shop.zip", zip_entries(REPO), "application/zip")},
            data={"kind": "zip"},
            headers={"Origin": FRONTEND},
        )
        assert r.status_code == 429 and r.json()["code"] == "upload_rate_limited"
        assert int(r.headers["Retry-After"]) > 0
        assert r.headers["access-control-allow-origin"] == FRONTEND

    def test_chunked_body_over_limit_is_rejected(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_MAX_UPLOAD_MB", "1")
        c = make_client()

        def chunks():
            for _ in range(3):
                yield b"x" * (1024 * 1024)

        r = c.post("/v1/analyses", content=chunks(), headers={"content-type": "multipart/form-data; boundary=zz"})
        assert r.status_code == 413 and r.json()["code"] == "upload_too_large"
        assert list(analyses_dir.glob("*")) == []

    def test_declared_length_over_limit_is_rejected(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_MAX_UPLOAD_MB", "1")
        r = make_client().post(
            "/v1/analyses",
            content=b"x" * (3 * 1024 * 1024),
            headers={"content-type": "multipart/form-data; boundary=zz"},
        )
        assert r.status_code == 413

    def test_failure_messages_hide_server_paths(self, client, monkeypatch):
        def boom(repo_root, *_a, **_k):
            raise ValueError(f"cannot parse {repo_root}/shop/api.py")

        monkeypatch.setattr(analyses_service, "run_pipeline", boom)
        r = upload(client, zip_entries(REPO), "shop.zip")
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "archlens-" not in detail and "/tmp" not in detail and "shop/api.py" in detail

    def test_safe_error_message_is_bounded(self, tmp_path):
        msg = safe_error_message("ValueError", f"{tmp_path}/src/x.py " + "y" * 1000, tmp_path)
        assert str(tmp_path) not in msg and len(msg) <= 300

    def test_unhandled_errors_are_generic_json(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("FRONTEND_ORIGIN", FRONTEND)

        def explode(self, analysis_id):
            raise RuntimeError("secret internal detail /etc/passwd")

        monkeypatch.setattr(AnalysisService, "get", explode)
        c = make_client()
        created = create(c)
        c = TestClient(create_app(), raise_server_exceptions=False)
        r = c.get(f"/v1/analyses/{created['analysisId']}", headers={**auth(created), "Origin": FRONTEND})
        assert r.status_code == 500
        assert r.json() == {"detail": "Internal server error.", "code": "internal_error"}
        assert r.headers["access-control-allow-origin"] == FRONTEND


class TestAnalysisTimeout:
    def test_subprocess_mode_completes(self, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_ANALYSIS_TIMEOUT_SECONDS", "120")
        c = make_client()
        assert analyses_router.get_analysis_service().timeout_seconds == 120
        created = create(c)
        assert created["status"] == "completed" and created["graph"]["nodes"]

    def test_timeout_kills_the_analysis(self, analyses_dir, monkeypatch):
        service = AnalysisService(AnalysisStore(analyses_dir), IngestLimits.from_env(), 1, timeout_seconds=0.01)
        app = create_app()
        app.dependency_overrides[analyses_router.get_analysis_service] = lambda: service
        r = upload(TestClient(app), zip_entries(REPO), "shop.zip")
        assert r.status_code == 422 and r.json()["code"] == "analysis_timeout"
        meta = json.loads((analyses_dir / r.json()["analysisId"] / "metadata.json").read_text())
        assert meta["status"] == "failed" and meta["error"]["code"] == "analysis_timeout"
