"""NVIDIA provider, OpenAI-compatible error handling, redaction and structured answers.

Fully offline: httpx.AsyncClient is replaced with a fake that records requests,
so no API key or network access is needed.
"""

import json
from unittest.mock import patch

import httpx
import pytest

from app.llm.factory import LLMProviderFactory
from app.llm.provider import LLMRequest
from app.llm.providers.nvidia_provider import DEFAULT_BASE_URL, NVIDIAProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.redaction import REDACTED, redact
from app.llm import structured

SECRET = "nvapi-TESTSECRET0123456789abcdef"
MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
HTTPX_CLIENT = "app.llm.providers.openai_provider.httpx.AsyncClient"


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text or (json.dumps(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakeClient:
    """Stands in for httpx.AsyncClient; replays outcomes and records requests."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []
        self.timeout = None

    def __call__(self, timeout=None, **_):
        self.timeout = timeout
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        self.requests.append({"url": url, "json": json, "headers": headers})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def completion(content="Answer.", usage=None):
    return FakeResponse(
        200,
        {
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
        },
    )


def nvidia(**overrides):
    config = {"api_key": SECRET, "model": MODEL, "max_retries": 0, "retry_delay_ms": 0}
    config.update(overrides)
    return NVIDIAProvider(config)


def request():
    return LLMRequest(system_prompt="sys", user_prompt="What is the architecture?", context={})


@pytest.fixture
def nvidia_env(monkeypatch):
    for name in (
        "ARCHLENS_LLM_BASE_URL",
        "ARCHLENS_LLM_TIMEOUT",
        "ARCHLENS_LLM_MAX_TOKENS",
        "ARCHLENS_LLM_MAX_RETRIES",
        "ARCHLENS_LLM_THINKING",
        "ARCHLENS_LLM_STREAMING",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("ARCHLENS_LLM_API_KEY", SECRET)
    monkeypatch.setenv("ARCHLENS_LLM_MODEL", MODEL)


# ---------------------------------------------------------------------------
# Imports and construction
# ---------------------------------------------------------------------------


class TestImportsAndConstruction:
    def test_providers_package_imports_both_providers(self):
        import app.llm.providers as providers

        assert providers.OpenAIProvider is OpenAIProvider
        assert providers.NVIDIAProvider is NVIDIAProvider

    def test_openai_provider_still_constructs(self):
        provider = OpenAIProvider({"api_key": "k", "model": "m"})
        assert provider.provider_name == "openai"
        assert provider.base_url == "https://api.openai.com/v1"

    def test_construction_makes_no_network_request(self):
        def no_network(*_a, **_k):
            raise AssertionError("constructing a provider must not open a connection")

        with patch(HTTPX_CLIENT, side_effect=no_network):
            provider = nvidia()
        assert provider.provider_name == "nvidia"
        assert provider.base_url == DEFAULT_BASE_URL
        assert provider.max_tokens == 2048

    def test_missing_key_is_a_clear_error_without_secrets(self):
        with pytest.raises(ValueError, match="ARCHLENS_LLM_API_KEY"):
            NVIDIAProvider({"model": MODEL})

    def test_missing_model_is_a_clear_error(self):
        with pytest.raises(ValueError, match="ARCHLENS_LLM_MODEL"):
            NVIDIAProvider({"api_key": SECRET})

    @pytest.mark.parametrize(
        "option, message",
        [({"streaming": True}, "STREAMING"), ({"thinking": True}, "THINKING"), ({"max_tokens": 0}, "MAX_TOKENS")],
    )
    def test_unsupported_options_are_rejected(self, option, message):
        with pytest.raises(ValueError, match=message):
            nvidia(**option)

    def test_thinking_false_is_accepted(self):
        assert nvidia(thinking=False).validate_config() is True


# ---------------------------------------------------------------------------
# Factory selection
# ---------------------------------------------------------------------------


class TestFactory:
    def test_selects_nvidia_with_defaults(self, nvidia_env):
        provider = LLMProviderFactory.create_provider()
        assert isinstance(provider, NVIDIAProvider)
        assert provider.base_url == DEFAULT_BASE_URL
        assert provider.model == MODEL
        assert provider.max_tokens == 2048
        assert provider.timeout == 60.0
        assert LLMProviderFactory.get_configuration_error() is None

    def test_nvidia_reads_overrides(self, nvidia_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_BASE_URL", "https://nim.internal/v1/")
        monkeypatch.setenv("ARCHLENS_LLM_MAX_TOKENS", "512")
        monkeypatch.setenv("ARCHLENS_LLM_TIMEOUT", "12.5")
        monkeypatch.setenv("ARCHLENS_LLM_THINKING", "false")
        monkeypatch.setenv("ARCHLENS_LLM_STREAMING", "false")
        provider = LLMProviderFactory.create_provider()
        assert provider.base_url == "https://nim.internal/v1"
        assert provider.max_tokens == 512
        assert provider.timeout == 12.5

    def test_invalid_number_is_a_configuration_error(self, nvidia_env, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_MAX_TOKENS", "lots")
        with pytest.raises(ValueError, match="ARCHLENS_LLM_MAX_TOKENS"):
            LLMProviderFactory.create_provider()

    def test_nvidia_without_model_reports_configuration_error(self, nvidia_env, monkeypatch):
        monkeypatch.delenv("ARCHLENS_LLM_MODEL")
        assert LLMProviderFactory.get_configuration_error() == "ARCHLENS_LLM_MODEL is not set."

    def test_nvidia_without_key_is_not_configured(self, nvidia_env, monkeypatch):
        monkeypatch.delenv("ARCHLENS_LLM_API_KEY")
        assert LLMProviderFactory.is_configured() is False
        assert "ARCHLENS_LLM_API_KEY" in LLMProviderFactory.get_configuration_error()

    def test_openai_and_mock_selection_unchanged(self, monkeypatch):
        monkeypatch.setenv("ARCHLENS_LLM_API_KEY", "k")
        monkeypatch.setenv("ARCHLENS_LLM_MODEL", "gpt-x")
        monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "openai")
        assert type(LLMProviderFactory.create_provider()) is OpenAIProvider
        monkeypatch.setenv("ARCHLENS_LLM_PROVIDER", "mock")
        assert LLMProviderFactory.create_provider().provider_name == "mock"

    def test_disabled_when_provider_unset(self, monkeypatch):
        monkeypatch.delenv("ARCHLENS_LLM_PROVIDER", raising=False)
        assert LLMProviderFactory.create_provider() is None


# ---------------------------------------------------------------------------
# Requests and responses
# ---------------------------------------------------------------------------


class TestGenerate:
    @pytest.mark.asyncio
    async def test_basic_non_streaming_request(self):
        client = FakeClient([completion("Layered FastAPI app.")])
        provider = nvidia(timeout=7.0)
        with patch(HTTPX_CLIENT, client):
            response = await provider.generate(request())

        assert response.success is True
        assert response.content == "Layered FastAPI app."
        assert response.provider == "nvidia" and response.model == MODEL
        assert response.usage["total_tokens"] == 13

        sent = client.requests[0]
        assert sent["url"] == f"{DEFAULT_BASE_URL}/chat/completions"
        assert sent["headers"]["Authorization"] == f"Bearer {SECRET}"
        body = sent["json"]
        assert body["model"] == MODEL
        assert body["max_tokens"] == 2048
        assert [m["role"] for m in body["messages"]] == ["system", "user"]
        # Unverified features are never sent.
        assert not {"stream", "chat_template_kwargs", "reasoning_effort", "response_format"} & body.keys()
        assert client.timeout == 7.0

    @pytest.mark.asyncio
    async def test_request_max_tokens_overrides_default(self):
        client = FakeClient([completion()])
        req = request()
        req.max_tokens = 100
        with patch(HTTPX_CLIENT, client):
            await nvidia().generate(req)
        assert client.requests[0]["json"]["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_inline_reasoning_trace_is_removed(self):
        client = FakeClient([completion("<think>internal notes</think>\nThe answer.")])
        with patch(HTTPX_CLIENT, client):
            response = await nvidia().generate(request())
        assert response.content == "The answer."

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status, error_type, retryable",
        [
            (401, "provider_auth_error", False),
            (403, "provider_auth_error", False),
            (404, "provider_model_not_found", False),
            (400, "provider_bad_request", False),
            (429, "provider_rate_limited", True),
            (503, "provider_unavailable", True),
        ],
    )
    async def test_http_errors_are_classified(self, status, error_type, retryable):
        client = FakeClient([FakeResponse(status, text=f"error {status}")])
        with patch(HTTPX_CLIENT, client):
            response = await nvidia().generate(request())
        assert response.success is False
        assert response.error_type == error_type
        assert response.retryable is retryable
        assert str(status) in response.error

    @pytest.mark.asyncio
    async def test_timeout_is_classified_and_retried(self):
        client = FakeClient([httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow")])
        with patch(HTTPX_CLIENT, client):
            response = await nvidia(max_retries=1).generate(request())
        assert len(client.requests) == 2
        assert response.success is False
        assert response.error_type == "provider_timeout"

    @pytest.mark.asyncio
    async def test_connection_error_is_classified(self):
        client = FakeClient([httpx.ConnectError("refused")])
        with patch(HTTPX_CLIENT, client):
            response = await nvidia().generate(request())
        assert response.error_type == "provider_unreachable"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "reply",
        [
            FakeResponse(200, text="<html>gateway</html>"),
            FakeResponse(200, {"choices": []}),
            FakeResponse(200, {"choices": [{"text": "legacy"}]}),
            FakeResponse(200, {"error": "nope"}),
        ],
    )
    async def test_malformed_responses_fail(self, reply):
        with patch(HTTPX_CLIENT, FakeClient([reply])):
            response = await nvidia().generate(request())
        assert response.success is False
        assert response.error_type == "provider_malformed_response"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", ["", "   ", None, "<think>only thoughts</think>"])
    async def test_empty_answers_fail(self, content):
        with patch(HTTPX_CLIENT, FakeClient([completion(content)])):
            response = await nvidia().generate(request())
        assert response.success is False
        assert response.error_type == "provider_empty_response"

    @pytest.mark.asyncio
    async def test_key_echoed_by_provider_is_redacted(self):
        client = FakeClient([FakeResponse(401, text=f"Invalid key {SECRET} for {MODEL}")])
        with patch(HTTPX_CLIENT, client):
            response = await nvidia().generate(request())
        assert SECRET not in response.error
        assert REDACTED in response.error

    @pytest.mark.asyncio
    async def test_long_error_bodies_are_truncated(self):
        client = FakeClient([FakeResponse(400, text="x" * 5000)])
        with patch(HTTPX_CLIENT, client):
            response = await nvidia().generate(request())
        assert len(response.error) < 500


# ---------------------------------------------------------------------------
# Redaction and structured answers
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_configured_secret_and_key_shapes_are_masked(self):
        text = f"key={SECRET} other=sk-abcdefghijklmnop Authorization: Bearer abc.def.ghi123"
        out = redact(text, [SECRET])
        assert SECRET not in out
        assert "sk-abcdefghijklmnop" not in out
        assert "abc.def.ghi123" not in out
        assert out.count(REDACTED) == 3

    def test_empty_and_short_secrets_are_ignored(self):
        assert redact("plain text", [None, "", "ab"]) == "plain text"
        assert redact(None) == ""


class TestStructuredAnswers:
    def test_parses_fenced_json_and_checks_evidence(self):
        raw = (
            "```json\n"
            + json.dumps(
                {
                    "summary": "s",
                    "verified_facts": [
                        {"statement": "a", "evidence": ["F1"]},
                        {"statement": "b", "evidence": ["F1", "F9"]},
                    ],
                    "interpretation": ["i"],
                }
            )
            + "\n```"
        )
        checked = structured.check_evidence(structured.parse_answer(raw), {"F1"})
        assert [f["verified"] for f in checked["verified_facts"]] == [True, False]
        assert checked["unverified_evidence"] == ["F9"]
        rendered = structured.render_answer(checked)
        assert "(unverified)" in rendered and "Interpretation:" in rendered

    @pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", json.dumps({"verified_facts": []})])
    def test_invalid_answers_raise(self, raw):
        with pytest.raises(structured.StructuredOutputError):
            structured.parse_answer(raw)

    def test_schema_describes_copilot_answer(self):
        schema = structured.answer_json_schema()
        assert "summary" in schema["properties"]


# ---------------------------------------------------------------------------
# Smoke-test script (python -m app.llm.smoke)
# ---------------------------------------------------------------------------


class TestSmokeScript:
    def test_success_never_prints_the_key(self, nvidia_env, capsys):
        from app.llm import smoke

        with patch(HTTPX_CLIENT, FakeClient([completion("pong")])):
            assert smoke.main([]) == 0
        out = capsys.readouterr().out
        assert "OK" in out and "'pong'" in out
        assert SECRET not in out
        assert "nvapi-… (" in out

    def test_failure_is_reported_and_redacted(self, nvidia_env, capsys):
        from app.llm import smoke

        with patch(HTTPX_CLIENT, FakeClient([FakeResponse(401, text=f"bad key {SECRET}")])):
            assert smoke.main([]) == 1
        out = capsys.readouterr().out
        assert "provider_auth_error" in out
        assert SECRET not in out

    def test_configuration_error_makes_no_request(self, nvidia_env, monkeypatch, capsys):
        from app.llm import smoke

        monkeypatch.delenv("ARCHLENS_LLM_MODEL")
        with patch(HTTPX_CLIENT, FakeClient([])):
            assert smoke.main([]) == 2
        assert "ARCHLENS_LLM_MODEL" in capsys.readouterr().out
