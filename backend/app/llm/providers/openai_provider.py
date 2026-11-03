"""OpenAI LLM Provider implementation (also the base for OpenAI-compatible APIs)."""

import asyncio
import time
from typing import Optional, Dict, Any
import httpx
from app.llm.provider import LLMProvider, LLMRequest, LLMResponse
from app.llm.redaction import redact

# Upstream error bodies are truncated before they reach responses or logs.
_MAX_ERROR_BODY = 300


class ProviderCallError(Exception):
    """A failed provider call, classified so callers can react consistently."""

    def __init__(self, message: str, error_type: str, retryable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for ArchLens LLM integration."""

    # Human-readable name used in configuration and error messages.
    label = "OpenAI"
    default_base_url = "https://api.openai.com/v1"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenAI provider.

        Args:
            config: Configuration dict with api_key, model, base_url, timeout,
                and optionally max_tokens, max_retries, retry_delay_ms
        """
        super().__init__(config)
        self.provider_name = "openai"
        self.api_key = config.get("api_key")
        # Model is never hard-coded — it must come from the environment
        # (ARCHLENS_LLM_MODEL). _validate() rejects an empty model with a
        # clear configuration error.
        self.model = config.get("model", "")
        self.base_url = (config.get("base_url") or self.default_base_url).rstrip("/")
        self.timeout = config.get("timeout", 30)
        # Output cap applied when the request does not set one.
        self.max_tokens: Optional[int] = config.get("max_tokens")
        self._validate()

    def _validate(self) -> None:
        """Validate configuration."""
        error = self.get_config_error()
        if error:
            raise ValueError(error)

    def validate_config(self) -> bool:
        """Check if provider is properly configured."""
        return self.get_config_error() is None

    def get_config_error(self) -> Optional[str]:
        """Get configuration error message."""
        if not self.api_key:
            return f"{self.label} API key is required (ARCHLENS_LLM_API_KEY is not set)"
        if not self.model:
            return f"{self.label} model is required (ARCHLENS_LLM_MODEL is not set)"
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
            error_msg = redact(str(e), [self.api_key])

            return LLMResponse(
                content="",
                provider=self.provider_name,
                model=self.model,
                usage={},
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
                error_type=getattr(e, "error_type", "provider_error"),
                retryable=bool(getattr(e, "retryable", False)),
            )

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        """Return True for HTTP status codes indicating transient failures."""
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _status_error_type(status_code: int) -> str:
        if status_code in (401, 403):
            return "provider_auth_error"
        if status_code == 404:
            return "provider_model_not_found"
        if status_code == 429:
            return "provider_rate_limited"
        if status_code >= 500:
            return "provider_unavailable"
        return "provider_bad_request"

    def _build_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """The chat-completions body. Subclasses add provider-specific fields."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
        }
        max_tokens = request.max_tokens or self.max_tokens
        if max_tokens:
            payload["max_tokens"] = max_tokens
        return payload

    def _parse_completion(self, response: httpx.Response) -> Dict[str, Any]:
        """Extract the answer from a 200 response; malformed or empty is an error."""
        try:
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ProviderCallError(
                f"{self.label} API returned a malformed response", "provider_malformed_response", True
            )
        content = self._clean_content(content if isinstance(content, str) else "")
        if not content.strip():
            raise ProviderCallError(
                f"{self.label} API returned an empty answer", "provider_empty_response", True
            )
        usage = data.get("usage") if isinstance(data, dict) else None
        return {"content": content, "usage": usage if isinstance(usage, dict) else {}}

    def _clean_content(self, content: str) -> str:
        """Hook for providers that wrap the answer (e.g. reasoning traces)."""
        return content

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
        payload = self._build_payload(request)

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
                except httpx.TransportError as e:
                    # Network / timeout / connection errors are transient — retry.
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay_ms * (attempt + 1) / 1000)
                        continue
                    if isinstance(e, httpx.TimeoutException):
                        raise ProviderCallError(
                            f"{self.label} API timed out after {self.timeout}s", "provider_timeout", True
                        )
                    raise ProviderCallError(
                        f"Could not reach the {self.label} API ({type(e).__name__})",
                        "provider_unreachable",
                        True,
                    )

                if response.status_code == 200:
                    return self._parse_completion(response)

                if self._is_retryable_status(response.status_code) and attempt < max_retries:
                    await asyncio.sleep(retry_delay_ms * (attempt + 1) / 1000)
                    continue

                body = (response.text or "")[:_MAX_ERROR_BODY]
                raise ProviderCallError(
                    f"{self.label} API error: {response.status_code} - {body}",
                    self._status_error_type(response.status_code),
                    self._is_retryable_status(response.status_code),
                )

            # Unreachable: the for-loop always returns, continues, or raises.
            raise RuntimeError("_call_openai_api: unexpected loop exit")  # pragma: no cover
