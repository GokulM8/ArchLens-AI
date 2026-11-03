"""NVIDIA (build.nvidia.com / NIM) provider via its OpenAI-compatible API.

Only a plain, non-streaming chat-completions request is sent. Thinking mode
and streaming are not sent to the API: model support for them varies and has
not been verified for the configured model, so asking for them is a
configuration error rather than a silently ignored flag.
"""

import re
from typing import Any, Dict, Optional

from app.llm.providers.openai_provider import OpenAIProvider

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MAX_TOKENS = 2048

# Some reasoning models inline their trace in the answer text.
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


class NVIDIAProvider(OpenAIProvider):
    """NVIDIA Nemotron (and other NIM-hosted models) through /chat/completions."""

    label = "NVIDIA"
    default_base_url = DEFAULT_BASE_URL

    def __init__(self, config: Dict[str, Any]):
        config = {**config}
        config.setdefault("max_tokens", DEFAULT_MAX_TOKENS)
        self.thinking: Optional[bool] = config.get("thinking")
        self.streaming: bool = bool(config.get("streaming"))
        super().__init__(config)
        self.provider_name = "nvidia"

    def get_config_error(self) -> Optional[str]:
        error = super().get_config_error()
        if error:
            return error
        if self.streaming:
            return "ARCHLENS_LLM_STREAMING=true is not supported yet; set it to false"
        if self.thinking:
            return "ARCHLENS_LLM_THINKING=true is not supported yet; set it to false or leave it unset"
        max_tokens = self.max_tokens
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            return "ARCHLENS_LLM_MAX_TOKENS must be a positive integer"
        return None

    def _clean_content(self, content: str) -> str:
        return _THINK_BLOCK.sub("", content).strip()
