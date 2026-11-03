"""Access control, retention and the Copilot route for /v1/analyses.

Uploads run the real deterministic pipeline. The LLM is the offline mock
provider, or the NVIDIA provider with a fake HTTP client — never the network.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.analyses import router as analyses_router
from app.api import create_app
from app.llm.providers.mock_provider import MockLLMProvider

from tests.test_llm_nvidia_provider import HTTPX_CLIENT, MODEL, SECRET, FakeClient, FakeResponse, completion
from tests.test_v1_analyses import EXAMPLE, auth, upload, zip_dir, zip_entries

SMALL_REPO = {
    "zebra_shop/__init__.py": "",
    "zebra_shop/zebra_api.py": "from zebra_shop import zebra_store\n\ndef handler():\n    return zebra_store.load()\n",
    "zebra_shop/zebra_store.py": "def load():\n    return []\n",
}


@pytest.fixture
def analyses_dir(tmp_path, monkeypatch):
    path = tmp_path / "analyses"
    monkeypatch.setenv("ARCHLENS_ANALYSES_DIR", str(path))
    monkeypatch.delenv("ARCHLENS_RETENTION_HOURS", raising=False)
    analyses_router.get_analysis_service.cache_clear()
    yield path
    analyses_router.get_analysis_service.cache_clear()


@pytest.fixture
def client(analyses_dir):
    return TestClient(create_app())


@pytest.fixture
def small(client):
    r = upload(client, zip_entries(SMALL_REPO), "zebra.zip")
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def example_zip():
    return zip_dir(EXAMPLE, "fastapi_project-main")


def ask(client, created, question="What is the architecture?", headers=None):
    return client.post(
        f"/v1/analyses/{created['analysisId']}/copilot",
        json={"question": question},
        headers=auth(created) if headers is None else headers,
    )


@pytest.fixture
def nvidia_env(monkeypatch):
    monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("ARCHLENS_LLM_API_KEY", SECRET)
    monkeypatch.setenv("ARCHLENS_LLM_MODEL", MODEL)
    monkeypatch.setenv("ARCHLENS_LLM_MAX_RETRIES", "0")
    for name in ("ARCHLENS_LLM_BASE_URL", "ARCHLENS_LLM_THINKING", "ARCHLENS_LLM_STREAMING", "ARCHLENS_LLM_MAX_TOKENS"):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


class TestAccessControl:
    def test_create_returns_a_token_and_never_its_hash(self, client, small, analyses_dir):
        assert len(small["accessToken"]) >= 40
        assert "accessTokenHash" not in small
        stored = (analyses_dir / small["analysisId"] / "metadata.json").read_text()
        assert small["accessToken"] not in stored
        got = client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).json()
        assert "accessTokenHash" not in got and "accessToken" not in got

    @pytest.mark.parametrize("path", ["", "/graph", "/health"])
    @pytest.mark.parametrize("token", [None, "", "wrong-token"])
    def test_reads_without_the_right_token_look_like_unknown_ids(self, client, small, path, token):
        headers = {} if token is None else {"X-ArchLens-Token": token}
        r = client.get(f"/v1/analyses/{small['analysisId']}{path}", headers=headers)
        assert r.status_code == 404
        assert r.json() == {"detail": "Analysis not found.", "code": "analysis_not_found"}

    def test_one_analysis_token_does_not_open_another(self, client, small, example_zip):
        other = upload(client, example_zip).json()
        r = client.get(f"/v1/analyses/{other['analysisId']}", headers=auth(small))
        assert r.status_code == 404
        r = ask(client, other, headers=auth(small))
        assert r.status_code == 404

    def test_diff_needs_the_baseline_token_too(self, client, small, example_zip):
        other = upload(client, example_zip).json()
        url = f"/v1/analyses/{small['analysisId']}/diff"
        params = {"baseline": other["analysisId"]}
        assert client.get(url, params=params, headers=auth(small)).status_code == 404
        wrong = {**auth(small), "X-ArchLens-Baseline-Token": small["accessToken"]}
        assert client.get(url, params=params, headers=wrong).status_code == 404
        right = {**auth(small), "X-ArchLens-Baseline-Token": other["accessToken"]}
        assert client.get(url, params=params, headers=right).status_code == 200

    def test_analyses_cannot_be_listed(self, client, small):
        r = client.get("/v1/analyses")
        assert r.status_code == 405
        assert small["analysisId"] not in r.text

    def test_delete_requires_the_token_and_removes_everything(self, client, small, analyses_dir):
        path = analyses_dir / small["analysisId"]
        assert client.delete(f"/v1/analyses/{small['analysisId']}").status_code == 404
        assert path.is_dir()
        assert client.delete(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).status_code == 204
        assert not path.exists()
        assert client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).status_code == 404

    def test_analyses_stored_without_a_token_are_inaccessible(self, client, small, analyses_dir):
        meta_path = analyses_dir / small["analysisId"] / "metadata.json"
        meta = json.loads(meta_path.read_text())
        del meta["accessTokenHash"]
        meta_path.write_text(json.dumps(meta))
        assert client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).status_code == 404


class TestRetention:
    @staticmethod
    def _age(analyses_dir, created, hours):
        meta_path = analyses_dir / created["analysisId"] / "metadata.json"
        meta = json.loads(meta_path.read_text())
        old = datetime.now(timezone.utc) - timedelta(hours=hours)
        meta["createdAt"] = old.isoformat(timespec="seconds").replace("+00:00", "Z")
        meta_path.write_text(json.dumps(meta))

    def test_expired_analysis_is_deleted_on_access(self, client, small, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_RETENTION_HOURS", "1")
        analyses_router.get_analysis_service.cache_clear()
        self._age(analyses_dir, small, hours=2)
        r = client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small))
        assert r.status_code == 404
        assert not (analyses_dir / small["analysisId"]).exists()

    def test_upload_sweeps_expired_analyses(self, client, small, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_RETENTION_HOURS", "1")
        analyses_router.get_analysis_service.cache_clear()
        self._age(analyses_dir, small, hours=2)
        fresh = upload(client, zip_entries(SMALL_REPO)).json()
        assert not (analyses_dir / small["analysisId"]).exists()
        assert (analyses_dir / fresh["analysisId"]).is_dir()

    def test_zero_keeps_analyses(self, client, small, analyses_dir, monkeypatch):
        monkeypatch.setenv("ARCHLENS_RETENTION_HOURS", "0")
        analyses_router.get_analysis_service.cache_clear()
        self._age(analyses_dir, small, hours=10_000)
        assert client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).status_code == 200


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------


class TestCopilotWithMockProvider:
    def test_answers_from_the_requested_analysis_only(self, client, small, example_zip, mock_env):
        other = upload(client, example_zip).json()
        prompts = []
        original = MockLLMProvider.generate

        async def recording(self, request):
            prompts.append(request.system_prompt + "\n" + request.user_prompt)
            return await original(self, request)

        with patch.object(MockLLMProvider, "generate", recording):
            r = ask(client, small)

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["analysisId"] == small["analysisId"]
        assert body["answer"]
        assert body["provider"] == "mock"
        assert isinstance(body["grounded"], bool)
        assert "external language model" in body["disclosure"]
        assert set(body["usage"]) == {"promptTokens", "completionTokens", "totalTokens"}

        assert len(prompts) == 1
        # The deterministic fact sheet for this analysis is in the prompt...
        assert "ArchLens fact sheet" in prompts[0]
        assert "[component:module:zebra_api]" in prompts[0]
        # ...but not its source code.
        assert "return zebra_store.load()" not in prompts[0]
        # Nothing from the other stored analysis reaches the model.
        assert other["repository"] not in prompts[0]
        assert "prediction" not in prompts[0]

    def test_deterministic_results_are_unchanged_by_copilot(self, client, small, mock_env):
        before = client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).json()
        assert ask(client, small).status_code == 200
        after = client.get(f"/v1/analyses/{small['analysisId']}", headers=auth(small)).json()
        assert before == after

    def test_not_configured_is_503(self, client, small, no_llm_env):
        r = ask(client, small)
        assert r.status_code == 503
        assert r.json()["code"] == "llm_not_configured"

    def test_question_length_limit(self, client, small, mock_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_COPILOT_MAX_QUESTION_CHARS", "10")
        r = ask(client, small, question="x" * 11)
        assert r.status_code == 422
        assert r.json()["code"] == "question_too_long"

    def test_blank_question_rejected(self, client, small, mock_env):
        r = ask(client, small, question="   ")
        assert r.status_code == 422
        assert r.json()["code"] == "validation_error"

    def test_empty_analysis_has_nothing_to_discuss(self, client, mock_env):
        created = upload(client, zip_entries({"README.md": "# docs\n"})).json()
        r = ask(client, created)
        assert r.status_code == 409
        assert r.json()["code"] == "analysis_empty"

    def test_failed_analysis_is_409(self, client, small, analyses_dir, mock_env):
        meta_path = analyses_dir / small["analysisId"] / "metadata.json"
        meta = json.loads(meta_path.read_text())
        meta["status"] = "failed"
        meta_path.write_text(json.dumps(meta))
        r = ask(client, small)
        assert r.status_code == 409
        assert r.json()["code"] == "analysis_not_completed"

    def test_rate_limit_counts_only_admitted_requests(self, client, small, mock_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_RATE_PER_MINUTE", "1")
        # Rejected before reaching the provider: missing token, blank question.
        assert ask(client, small, headers={}).status_code == 404
        assert ask(client, small, question=" ").status_code == 422
        assert ask(client, small).status_code == 200
        r = ask(client, small)
        assert r.status_code == 429
        assert r.json()["code"] == "llm_rate_limited"
        assert int(r.headers["retry-after"]) >= 1

    def test_daily_quota(self, client, small, mock_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_DAILY_QUOTA", "1")
        assert ask(client, small).status_code == 200
        r = ask(client, small)
        assert r.status_code == 429
        assert r.json()["code"] == "llm_quota_exceeded"

    def test_status_endpoint(self, client, mock_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_API_KEY", SECRET)
        body = client.get("/v1/copilot/status").json()
        assert body["enabled"] is True and body["provider"] == "mock"
        assert SECRET not in json.dumps(body)

    def test_status_when_disabled(self, client, no_llm_env):
        body = client.get("/v1/copilot/status").json()
        assert body["enabled"] is False
        assert body["configurationError"]


class TestCopilotWithNvidiaProvider:
    def test_success(self, client, small, nvidia_env):
        fake = FakeClient([completion("The zebra_shop package has an API module and a store module.")])
        with patch(HTTPX_CLIENT, fake):
            r = ask(client, small)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provider"] == "nvidia" and body["model"] == MODEL
        assert "zebra_shop" in body["answer"]
        assert fake.requests[0]["json"]["max_tokens"] == 2048

    @pytest.mark.parametrize(
        "outcome, status, code, provider_error",
        [
            (FakeResponse(401, text=f"bad key {SECRET}"), 502, "llm_provider_error", "provider_auth_error"),
            (FakeResponse(404, text="model not found"), 502, "llm_provider_error", "provider_model_not_found"),
            (FakeResponse(429, text="slow down"), 503, "llm_provider_busy", "provider_rate_limited"),
            (FakeResponse(500, text="boom"), 503, "llm_provider_unavailable", "provider_unavailable"),
            (FakeResponse(200, text="<html>"), 502, "llm_provider_error", "provider_malformed_response"),
            (completion(""), 502, "llm_provider_error", "provider_empty_response"),
        ],
    )
    def test_provider_failures_are_errors_never_answers(self, client, small, nvidia_env, outcome, status, code, provider_error):
        with patch(HTTPX_CLIENT, FakeClient([outcome])):
            r = ask(client, small)
        assert r.status_code == status, r.text
        body = r.json()
        assert body["code"] == code
        assert body["providerError"] == provider_error
        assert "answer" not in body
        assert SECRET not in r.text

    def test_timeout_is_504(self, client, small, nvidia_env):
        import httpx

        with patch(HTTPX_CLIENT, FakeClient([httpx.ReadTimeout("slow")])):
            r = ask(client, small)
        assert r.status_code == 504
        assert r.json()["code"] == "llm_timeout"

    def test_missing_model_is_not_configured(self, client, small, nvidia_env, monkeypatch):
        monkeypatch.delenv("ARCHLENS_LLM_MODEL")
        r = ask(client, small)
        assert r.status_code == 503
        assert r.json()["code"] == "llm_not_configured"

    def test_unsupported_streaming_is_reported_not_ignored(self, client, small, nvidia_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_STREAMING", "true")
        with patch(HTTPX_CLIENT, FakeClient([])):
            r = ask(client, small)
        assert r.status_code == 503
        assert "STREAMING" in r.json()["detail"]
