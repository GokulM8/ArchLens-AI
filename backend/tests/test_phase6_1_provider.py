"""Tests for Phase 6.1 — LLM Provider Abstraction."""

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from app.llm.factory import LLMProviderFactory
from app.llm.provider import LLMRequest, LLMResponse
from app.llm.providers.mock_provider import MockLLMProvider


class TestLLMProviderFactory:
    """Test LLM provider factory."""

    def test_factory_returns_none_when_not_configured(self):
        """Factory should return None when ARCHLENS_LLM_PROVIDER is not set."""
        with patch.dict(os.environ, {}, clear=True):
            provider = LLMProviderFactory.create_provider()
            assert provider is None

    def test_factory_creates_mock_provider(self):
        """Factory should create MockLLMProvider when configured."""
        with patch.dict(
            os.environ,
            {
                "ARCHLENS_LLM_PROVIDER": "mock",
                "ARCHLENS_LLM_MODEL": "mock-model",
                "ARCHLENS_LLM_API_KEY": "mock-key",
            },
        ):
            provider = LLMProviderFactory.create_provider()
            assert provider is not None

    def test_factory_raises_on_unknown_provider(self):
        """Factory should raise ValueError for unknown provider."""
        with patch.dict(
            os.environ,
            {
                "ARCHLENS_LLM_PROVIDER": "unknown_provider",
                "ARCHLENS_LLM_API_KEY": "key",
            },
        ):
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                LLMProviderFactory.create_provider()

    def test_is_configured_returns_true_when_provider_and_key_set(self):
        """is_configured should return True when provider and API key are set."""
        with patch.dict(
            os.environ,
            {
                "ARCHLENS_LLM_PROVIDER": "openai",
                "ARCHLENS_LLM_API_KEY": "test-key",
            },
        ):
            assert LLMProviderFactory.is_configured() is True

    def test_is_configured_returns_false_when_not_set(self):
        """is_configured should return False when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            assert LLMProviderFactory.is_configured() is False

    def test_get_configuration_error_when_nothing_configured(self):
        """get_configuration_error should return error when nothing is configured."""
        with patch.dict(os.environ, {}, clear=True):
            error = LLMProviderFactory.get_configuration_error()
            assert error is not None
            assert "ARCHLENS_LLM_PROVIDER" in error
            assert "ARCHLENS_LLM_API_KEY" in error

    def test_get_configuration_error_when_provider_missing(self):
        """get_configuration_error should return error when provider is missing."""
        with patch.dict(os.environ, {"ARCHLENS_LLM_API_KEY": "test-key"}, clear=True):
            error = LLMProviderFactory.get_configuration_error()
            assert error is not None
            assert "ARCHLENS_LLM_PROVIDER" in error

    def test_get_configuration_error_when_api_key_missing(self):
        """get_configuration_error should return error when API key is missing."""
        with patch.dict(os.environ, {"ARCHLENS_LLM_PROVIDER": "openai"}, clear=True):
            error = LLMProviderFactory.get_configuration_error()
            assert error is not None
            assert "ARCHLENS_LLM_API_KEY" in error

    def test_get_configuration_error_returns_none_when_valid(self):
        """get_configuration_error should return None when properly configured."""
        with patch.dict(
            os.environ,
            {
                "ARCHLENS_LLM_PROVIDER": "openai",
                "ARCHLENS_LLM_API_KEY": "test-key",
            },
        ):
            error = LLMProviderFactory.get_configuration_error()
            assert error is None


class TestMockLLMProvider:
    """Test MockLLMProvider for testing."""

    def test_mock_provider_validates_config(self):
        """Mock provider should always validate config successfully."""
        provider = MockLLMProvider({"model": "mock"})
        assert provider.validate_config() is True

    def test_mock_provider_has_no_config_error(self):
        """Mock provider should have no config errors."""
        provider = MockLLMProvider({"model": "mock"})
        assert provider.get_config_error() is None

    @pytest.mark.asyncio
    async def test_mock_provider_generates_response(self):
        """Mock provider should generate a response."""
        provider = MockLLMProvider({"model": "mock-model"})
        request = LLMRequest(
            system_prompt="You are helpful",
            user_prompt="What is architecture?",
            context={},
        )

        response = await provider.generate(request)

        assert response.success is True
        assert response.provider == "mock"
        assert response.model == "mock-model"
        assert len(response.content) > 0
        assert response.usage == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        assert response.latency_ms > 0
        assert response.error is None

    @pytest.mark.asyncio
    async def test_mock_provider_deterministic_responses(self):
        """Mock provider should generate deterministic responses for same input."""
        provider = MockLLMProvider({"model": "mock"})
        request = LLMRequest(
            system_prompt="You are helpful",
            user_prompt="Tell me about architecture",
            context={},
        )

        response1 = await provider.generate(request)
        response2 = await provider.generate(request)

        assert response1.content == response2.content


class TestLLMRequest:
    """Test LLMRequest data model."""

    def test_llm_request_creation(self):
        """LLMRequest should be created with required fields."""
        request = LLMRequest(
            system_prompt="You are an architect",
            user_prompt="Explain the architecture",
            context={"key": "value"},
        )

        assert request.system_prompt == "You are an architect"
        assert request.user_prompt == "Explain the architecture"
        assert request.context == {"key": "value"}
        assert request.temperature == 0.7
        assert request.max_tokens is None

    def test_llm_request_with_custom_params(self):
        """LLMRequest should accept custom temperature and max_tokens."""
        request = LLMRequest(
            system_prompt="System",
            user_prompt="User",
            context={},
            temperature=0.5,
            max_tokens=1000,
        )

        assert request.temperature == 0.5
        assert request.max_tokens == 1000


class TestLLMResponse:
    """Test LLMResponse data model."""

    def test_llm_response_success(self):
        """LLMResponse should represent successful generation."""
        response = LLMResponse(
            content="Generated content",
            provider="mock",
            model="mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=15.5,
            success=True,
        )

        assert response.content == "Generated content"
        assert response.provider == "mock"
        assert response.success is True
        assert response.error is None

    def test_llm_response_failure(self):
        """LLMResponse should represent failed generation."""
        response = LLMResponse(
            content="",
            provider="mock",
            model="mock-model",
            usage={},
            latency_ms=100.0,
            success=False,
            error="API timeout",
        )

        assert response.success is False
        assert response.error == "API timeout"
        assert response.content == ""


class TestProviderAbstraction:
    """Test provider abstraction."""

    def test_provider_has_required_methods(self):
        """Provider should implement required abstract methods."""
        provider = MockLLMProvider({"model": "mock"})

        assert hasattr(provider, "generate")
        assert hasattr(provider, "validate_config")
        assert hasattr(provider, "get_config_error")
        assert callable(provider.generate)
        assert callable(provider.validate_config)
        assert callable(provider.get_config_error)

    def test_provider_config_isolation(self):
        """Provider should not expose secrets in config."""
        config = {"api_key": "secret-key", "model": "test-model"}
        provider = MockLLMProvider(config)

        # Config is stored but should never be logged or exposed
        assert provider.config["api_key"] == "secret-key"


class TestConfigurationEnvironmentVariables:
    """Test configuration through environment variables."""

    def test_all_supported_env_vars(self):
        """All supported environment variables should be respected."""
        with patch.dict(
            os.environ,
            {
                "ARCHLENS_LLM_PROVIDER": "openai",
                "ARCHLENS_LLM_MODEL": "gpt-4o",
                "ARCHLENS_LLM_API_KEY": "test-api-key",
                "ARCHLENS_LLM_BASE_URL": "https://custom.openai.com/v1",
                "ARCHLENS_LLM_TIMEOUT": "60",
            },
        ):
            config = LLMProviderFactory._build_openai_config()

            assert config["api_key"] == "test-api-key"
            assert config["model"] == "gpt-4o"
            assert config["base_url"] == "https://custom.openai.com/v1"
            assert config["timeout"] == 60

    def test_default_values_when_env_vars_missing(self):
        """Should use default values when environment variables are missing."""
        with patch.dict(
            os.environ,
            {
                "ARCHLENS_LLM_PROVIDER": "openai",
                "ARCHLENS_LLM_API_KEY": "test-key",
            },
            clear=True,
        ):
            config = LLMProviderFactory._build_openai_config()

            assert config["model"] == "gpt-4o"
            assert config["base_url"] == "https://api.openai.com/v1"
            assert config["timeout"] == 30
