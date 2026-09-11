"""LLM Provider abstraction — base class for provider implementations."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMRequest:
    """Represents an LLM request."""
    system_prompt: str
    user_prompt: str
    context: Dict[str, Any]
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@dataclass
class LLMResponse:
    """Represents an LLM response."""
    content: str
    provider: str
    model: str
    usage: Dict[str, int]
    latency_ms: float
    success: bool
    error: Optional[str] = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement this interface to be used by ArchLens.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration.

        Args:
            config: Provider configuration dictionary
        """
        self.config = config
        self.provider_name = "unknown"
        self.model = config.get("model", "")

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate an LLM response asynchronously.

        Args:
            request: LLMRequest with prompts and context

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the provider is properly configured.

        Returns:
            True if configured correctly, False otherwise
        """
        pass

    @abstractmethod
    def get_config_error(self) -> Optional[str]:
        """
        Get a user-friendly error message if configuration is invalid.

        Returns:
            Error message or None if valid
        """
        pass
