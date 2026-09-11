"""OpenAI LLM Provider implementation."""

import time
from typing import Optional, Dict, Any
import httpx
from app.llm.provider import LLMProvider, LLMRequest, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for ArchLens LLM integration."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenAI provider.

        Args:
            config: Configuration dict with api_key, model, base_url, timeout
        """
        super().__init__(config)
        self.provider_name = "openai"
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gpt-4o")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.timeout = config.get("timeout", 30)
        self._validate()

    def _validate(self) -> None:
        """Validate configuration."""
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        if not self.model:
            raise ValueError("OpenAI model is required")

    def validate_config(self) -> bool:
        """Check if provider is properly configured."""
        try:
            self._validate()
            return True
        except ValueError:
            return False

    def get_config_error(self) -> Optional[str]:
        """Get configuration error message."""
        if not self.api_key:
            return "OpenAI API key (ARCHLENS_LLM_API_KEY) is not set"
        if not self.model:
            return "OpenAI model (ARCHLENS_LLM_MODEL) is not set"
        return None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using OpenAI API.

        Args:
            request: LLMRequest with system and user prompts

        Returns:
            LLMResponse with generated content and metadata
        """
        start_time = time.time()

        try:
            response_data = await self._call_openai_api(request)
            latency_ms = (time.time() - start_time) * 1000

            return LLMResponse(
                content=response_data.get("content", ""),
                provider=self.provider_name,
                model=self.model,
                usage=response_data.get("usage", {}),
                latency_ms=latency_ms,
                success=True,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=self.model,
                usage={},
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
            )

    async def _call_openai_api(self, request: LLMRequest) -> Dict[str, Any]:
        """
        Call OpenAI API.

        Args:
            request: LLMRequest

        Returns:
            Dict with response content and usage
        """
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

            data = response.json()

            return {
                "content": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "usage": data.get("usage", {}),
            }
