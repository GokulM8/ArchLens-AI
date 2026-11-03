"""LLM Provider Factory — creates and configures provider instances."""

import os
from typing import Optional, Dict, Any
from app.llm.provider import LLMProvider


SUPPORTED_PROVIDERS = ("openai", "nvidia", "mock")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}")


def _env_tristate(name: str) -> Optional[bool]:
    """true/false from the environment; None when unset."""
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return None
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def create_provider() -> Optional[LLMProvider]:
        """
        Create an LLM provider based on environment configuration.

        Returns:
            Configured LLMProvider instance or None if not configured
        """
        provider_name = os.getenv("ARCHLENS_LLM_PROVIDER", "").lower()

        if not provider_name:
            return None

        if provider_name == "openai":
            from app.llm.providers.openai_provider import OpenAIProvider
            config = LLMProviderFactory._build_openai_config()
            return OpenAIProvider(config)

        if provider_name == "nvidia":
            from app.llm.providers.nvidia_provider import NVIDIAProvider
            return NVIDIAProvider(LLMProviderFactory._build_nvidia_config())

        if provider_name == "mock":
            from app.llm.providers.mock_provider import MockLLMProvider
            config = {"model": os.getenv("ARCHLENS_LLM_MODEL", "mock-model")}
            return MockLLMProvider(config)

        raise ValueError(f"Unknown LLM provider: {provider_name}")

    @staticmethod
    def _build_openai_config() -> Dict[str, Any]:
        """Build OpenAI provider configuration from environment variables."""
        return {
            "api_key": os.getenv("ARCHLENS_LLM_API_KEY"),
            # Model is never hard-coded — it is taken solely from the env var
            # (ARCHLENS_LLM_MODEL). The OpenAIProvider validates that a model is
            # present for a configured provider.
            "model": os.getenv("ARCHLENS_LLM_MODEL", ""),
            "base_url": os.getenv("ARCHLENS_LLM_BASE_URL") or "https://api.openai.com/v1",
            "timeout": _env_float("ARCHLENS_LLM_TIMEOUT", 30.0),
            "max_tokens": _env_int("ARCHLENS_LLM_MAX_TOKENS", 0) or None,
        }

    @staticmethod
    def _build_nvidia_config() -> Dict[str, Any]:
        """
        Build NVIDIA provider configuration from environment variables.

        Raises ValueError (surfaced as a configuration error, never a request)
        when a value cannot be parsed.
        """
        from app.llm.providers.nvidia_provider import DEFAULT_BASE_URL

        return {
            "api_key": os.getenv("ARCHLENS_LLM_API_KEY", ""),
            "model": os.getenv("ARCHLENS_LLM_MODEL", ""),
            "base_url": os.getenv("ARCHLENS_LLM_BASE_URL") or DEFAULT_BASE_URL,
            "timeout": _env_float("ARCHLENS_LLM_TIMEOUT", 60.0),
            "max_tokens": _env_int("ARCHLENS_LLM_MAX_TOKENS", 2048),
            "max_retries": _env_int("ARCHLENS_LLM_MAX_RETRIES", 2),
            # Validated by NVIDIAProvider: only false/unset is supported for now.
            "thinking": _env_tristate("ARCHLENS_LLM_THINKING"),
            "streaming": bool(_env_tristate("ARCHLENS_LLM_STREAMING")),
        }

    @staticmethod
    def is_configured() -> bool:
        """
        Check if an LLM provider is configured.

        Returns:
            True if provider name and API key are configured
        """
        provider_name = os.getenv("ARCHLENS_LLM_PROVIDER", "").lower()
        api_key = os.getenv("ARCHLENS_LLM_API_KEY", "")
        return bool(provider_name and api_key)

    @staticmethod
    def get_configuration_error() -> Optional[str]:
        """
        Get a user-friendly error message if configuration is incomplete.

        Returns:
            Error message or None if properly configured
        """
        provider_name = os.getenv("ARCHLENS_LLM_PROVIDER", "").lower()
        api_key = os.getenv("ARCHLENS_LLM_API_KEY", "")

        if not provider_name and not api_key:
            return (
                "LLM provider is not configured. "
                "Set ARCHLENS_LLM_PROVIDER and ARCHLENS_LLM_API_KEY to enable Architecture Copilot."
            )

        if not provider_name:
            return "ARCHLENS_LLM_PROVIDER is not set."

        if not api_key:
            return "ARCHLENS_LLM_API_KEY is not set."

        if provider_name not in SUPPORTED_PROVIDERS:
            return f"Unknown LLM provider: {provider_name}. Supported: {', '.join(SUPPORTED_PROVIDERS)}"

        if provider_name == "nvidia" and not os.getenv("ARCHLENS_LLM_MODEL", ""):
            return "ARCHLENS_LLM_MODEL is not set."

        return None
