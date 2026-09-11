"""Mock LLM Provider for testing — deterministic responses without external API."""

from typing import Optional, Dict, Any
from app.llm.provider import LLMProvider, LLMRequest, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing and development."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize mock provider.

        Args:
            config: Configuration dict (unused for mock)
        """
        super().__init__(config)
        self.provider_name = "mock"
        self.model = config.get("model", "mock-model")

    def validate_config(self) -> bool:
        """Mock is always valid."""
        return True

    def get_config_error(self) -> Optional[str]:
        """Mock has no configuration errors."""
        return None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate a deterministic mock response.

        Args:
            request: LLMRequest

        Returns:
            Deterministic LLMResponse for testing
        """
        # Generate a deterministic response based on the user prompt
        user_prompt_hash = hash(request.user_prompt) % 1000

        if "architecture" in request.user_prompt.lower():
            content = "Mock response: This is a test response about architecture."
        elif "component" in request.user_prompt.lower():
            content = "Mock response: This component has the following characteristics..."
        else:
            content = f"Mock response (hash: {user_prompt_hash}): {request.user_prompt[:50]}"

        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=self.model,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=10.0,
            success=True,
        )
