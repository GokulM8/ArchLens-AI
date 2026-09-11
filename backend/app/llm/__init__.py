"""ArchLens AI Phase 6 — LLM Architecture Intelligence & Copilot Package."""

from app.llm.provider import LLMProvider
from app.llm.factory import LLMProviderFactory
from app.llm.schemas import (
    LLMOperationType,
    LLMContextSource,
    LLMOperationCategory,
    GroundingSource,
    LLMUsage,
    LLMOperation,
    LLMError,
    LLMResponseMetadata,
    LLMOperationResponse,
    LLMMessage,
    LLMConversationContext,
    LLMConversation,
    LLMProviderConfig,
    LLMProviderCapabilities,
    LLMContext,
    OperationRequest,
    OperationResult,
    LLMSchemaVersion,
    get_schema_version,
    CURRENT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)

__all__ = [
    # Provider abstraction (Phase 6.1)
    "LLMProvider",
    "LLMProviderFactory",
    # Schemas (Phase 6.2)
    "LLMOperationType",
    "LLMContextSource",
    "LLMOperationCategory",
    "GroundingSource",
    "LLMUsage",
    "LLMOperation",
    "LLMError",
    "LLMResponseMetadata",
    "LLMOperationResponse",
    "LLMMessage",
    "LLMConversationContext",
    "LLMConversation",
    "LLMProviderConfig",
    "LLMProviderCapabilities",
    "LLMContext",
    "OperationRequest",
    "OperationResult",
    "LLMSchemaVersion",
    "get_schema_version",
    "CURRENT_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
]
