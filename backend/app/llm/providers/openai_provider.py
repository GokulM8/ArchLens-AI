"""OpenAI LLM Provider implementation."""

import asyncio
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
        # Model is never hard-coded — it must come from the environment
        # (ARCHLENS_LLM_MODEL). _validate() rejects an empty model with a
        # clear configuration error.
        self.model = config.get("model", "")
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

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        """Return True for HTTP status codes indicating transient failures."""
        return status_code == 429 or 500 <= status_code < 600

    async def _call_openai_api(self, request: LLMRequest) -> Dict[str, Any]:
        """
        Call OpenAI API with retry handling for transient failures.

        Retries timeouts, connection errors, HTTP 429 (rate limit), and 5xx
        server errors up to ``max_retries`` times with linear back-off.
        Non-transient client errors (4xx except 429) fail immediately.

        Args:
            request: LLMRequest

        Returns:
            Dict with response content and usage
        """
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

        payload: Dict[str, Any] = {
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

        max_retries: int = max(0, int(self.config.get("max_retries", 3)))
        retry_delay_ms: int = max(0, int(self.config.get("retry_delay_ms", 100)))

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                except httpx.TransportError:
                    # Network / timeout / connection errors are transient — retry.
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay_ms * (attempt + 1) / 1000)
                        continue
                    raise

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "content": data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", ""),
                        "usage": data.get("usage", {}),
                    }

                if self._is_retryable_status(response.status_code) and attempt < max_retries:
                    await asyncio.sleep(retry_delay_ms * (attempt + 1) / 1000)
                    continue

                raise Exception(
                    f"OpenAI API error: {response.status_code} - {response.text}"
                )

            # Unreachable: the for-loop always returns, continues, or raises.
            raise RuntimeError("_call_openai_api: unexpected loop exit")  # pragma: no cover
