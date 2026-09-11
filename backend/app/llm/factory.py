"""LLM Provider Factory — creates and configures provider instances."""

import os
from typing import Optional, Dict, Any
from app.llm.provider import LLMProvider


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
            "model": os.getenv("ARCHLENS_LLM_MODEL", "gpt-4o"),
            "base_url": os.getenv("ARCHLENS_LLM_BASE_URL", "https://api.openai.com/v1"),
            "timeout": int(os.getenv("ARCHLENS_LLM_TIMEOUT", "30")),
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

        if provider_name not in ["openai"]:
            return f"Unknown LLM provider: {provider_name}. Supported: openai"

        return None
