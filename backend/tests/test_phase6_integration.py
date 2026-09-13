"""Integration tests for Phase 6.15 (API) and 6.16 (CLI).

These exercise the full stack — FastAPI endpoints and Click commands — against
the deterministic MockLLMProvider writing/reading real artifact files. No real
LLM request is ever made.
"""

import os

import pytest

from click.testing import CliRunner

from app.cli import cli
from tests.conftest import write_artifacts


API_AVAILABLE = True
try:
    from fastapi.testclient import TestClient
    from app.api import create_app
except ImportError:  # pragma: no cover
    API_AVAILABLE = False


MOCK_LLM_ENV = {
    "ARCHLENS_LLM_PROVIDER": "mock",
    "ARCHLENS_LLM_API_KEY": "test-key",
}


def _env_without_llm(env):
    env = dict(env)
    env["ARCHLENS_LLM_PROVIDER"] = ""
    env["ARCHLENS_LLM_API_KEY"] = ""
    return env


@pytest.fixture
def artifacts_dir(tmp_path, monkeypatch):
    write_artifacts(tmp_path)
    monkeypatch.setenv("ARCHLENS_ARTIFACTS_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(artifacts_dir, mock_env):
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# API integration (§30)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not API_AVAILABLE, reason="fastapi not installed")
class TestAPI:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["llm_configured"] is True

    def test_health_works_without_llm_config(self, artifacts_dir, no_llm_env):
        client = TestClient(create_app())
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["llm_configured"] is False

    def test_status_reports_config_without_secrets(self, client):
        response = client.get("/llm/status")
        assert response.status_code == 200
        body = response.json()
        assert body["configured"] is True
        assert "api_key" not in body
        assert "test-key" not in str(body)

    def test_ask_success(self, client):
        response = client.post("/llm/ask", json={"question": "What is the architecture?"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["content"]

    def test_unconfigured_returns_structured_error(self, artifacts_dir, no_llm_env):
        client = TestClient(create_app())
        response = client.post("/llm/ask", json={"question": "hi"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"]["error_type"] == "configuration_error"

    def test_invalid_target_returns_structured_error(self, client):
        response = client.post("/llm/risk", json={"target": "no_such_risk"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"]["error_type"] == "invalid_target"

    def test_missing_artifacts_404(self, monkeypatch):
        monkeypatch.setenv("ARCHLENS_ARTIFACTS_DIR", "/nonexistent/archlens/output")
        client = TestClient(create_app())
        response = client.post("/llm/ask", json={"question": "hi"})
        assert response.status_code == 404

    def test_incomplete_artifacts_dir_404(self, tmp_path, monkeypatch):
        # The directory exists but no artifact JSONs were written yet.
        monkeypatch.setenv("ARCHLENS_ARTIFACTS_DIR", str(tmp_path))
        client = TestClient(create_app())
        response = client.post("/llm/ask", json={"question": "hi"})
        assert response.status_code == 404
        assert "Missing ArchLens artifact" in response.json()["detail"]

    @pytest.mark.parametrize(
        "endpoint, payload",
        [
            ("/llm/explain", {}),
            ("/llm/summary", {}),
            ("/llm/component", {"target": "module:app.main"}),
            ("/llm/dependency", {"source": "module:app.main", "target": "module:app"}),
            ("/llm/risk", {"target": "high_coupling:module:app.main"}),
            ("/llm/recommendation", {"target": "reduce_coupling:module:app.main"}),
            ("/llm/impact", {"target": "module:app.main"}),
            ("/llm/refactor-plan", {"target": "reduce_coupling:module:app.main"}),
        ],
    )
    def test_all_llm_endpoints_succeed(self, client, endpoint, payload):
        response = client.post(endpoint, json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True, f"{endpoint}: {body}"

    def test_conversation_flow_across_requests(self, client):
        # Create a conversation…
        created = client.post("/llm/conversations", json={"repository": "sample_repo"})
        assert created.status_code == 200
        conversation_id = created.json()["id"]

        # …ask inside it…
        asked = client.post(
            "/llm/ask",
            json={"question": "What is the architecture?", "conversation_id": conversation_id},
        )
        assert asked.status_code == 200
        assert asked.json()["success"] is True

        # …and read the recorded turn back on a fresh request.
        fetched = client.get(f"/llm/conversations/{conversation_id}")
        assert fetched.status_code == 200
        messages = fetched.json()["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant"]

    def test_missing_conversation_404(self, client):
        response = client.get("/llm/conversations/does-not-exist")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# CLI integration (§31) + deterministic-pipeline backward compatibility
# ---------------------------------------------------------------------------


class TestCLI:
    @pytest.fixture
    def artifacts_dir(self, tmp_path):
        write_artifacts(tmp_path)
        return tmp_path

    def test_analyze_produces_all_five_artifacts(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "../examples/fastapi_project", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output
        for fname in ("analysis.json", "graph.json", "architecture.json",
                      "health.json", "evolution.json"):
            assert (tmp_path / fname).exists()

    def test_ask_requires_llm_config(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["ask", "What is the architecture?", "-o", str(artifacts_dir)],
            env=_env_without_llm(dict(os.environ)),
        )
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_ask_reports_invalid_llm_config(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["ask", "What is the architecture?", "-o", str(artifacts_dir)],
            env={
                "ARCHLENS_LLM_PROVIDER": "openai",
                "ARCHLENS_LLM_API_KEY": "test-key",
                "ARCHLENS_LLM_MODEL": "",
            },
        )
        assert result.exit_code == 1
        assert "OpenAI model is required" in result.stderr

    def test_ask_success(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["ask", "What is the architecture?", "-o", str(artifacts_dir)],
            env=MOCK_LLM_ENV,
        )
        assert result.exit_code == 0, result.output
        assert "Mock response" in result.output

    def test_explain_architecture_success(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["explain", "architecture", "-o", str(artifacts_dir)],
            env=MOCK_LLM_ENV,
        )
        assert result.exit_code == 0, result.output
        assert "Mock response" in result.output

    def test_explain_component_success(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["explain", "component", "module:app.main", "-o", str(artifacts_dir)],
            env=MOCK_LLM_ENV,
        )
        assert result.exit_code == 0, result.output

    def test_explain_dependency_success(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["explain", "dependency", "module:app.main", "module:app", "-o", str(artifacts_dir)],
            env=MOCK_LLM_ENV,
        )
        assert result.exit_code == 0, result.output

    def test_explain_risk_success(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["explain", "risk", "high_coupling:module:app.main", "-o", str(artifacts_dir)],
            env=MOCK_LLM_ENV,
        )
        assert result.exit_code == 0, result.output

    def test_invalid_target_exits_nonzero(self, artifacts_dir):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["explain", "risk", "no_such_risk", "-o", str(artifacts_dir)],
            env=MOCK_LLM_ENV,
        )
        assert result.exit_code == 1

    def test_analyze_needs_no_llm_at_all(self, tmp_path):
        """Deterministic pipeline must work with no LLM configuration."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["analyze", "../examples/fastapi_project", "-o", str(tmp_path)],
            env=_env_without_llm(dict(os.environ)),
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "health.json").exists()
        assert (tmp_path / "evolution.json").exists()