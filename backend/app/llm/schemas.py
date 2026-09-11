"""LLM Schemas — typed Pydantic models for LLM operations and responses."""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class LLMOperationType(str, Enum):
    """Types of LLM operations for architecture intelligence."""
    EXPLAIN = "explain"
    ASK = "ask"
    RECOMMEND = "recommend"
    ANALYZE = "analyze"
    VALIDATE = "validate"
    SUGGEST = "suggest"


class LLMContextSource(str, Enum):
    """Source of context information provided to the LLM."""
    ANALYSIS = "analysis"           # From Phase 1 static analysis
    GRAPH = "graph"                 # From Phase 2 dependency graph
    ARCHITECTURE = "architecture"   # From Phase 3 architecture inference
    USER_INPUT = "user_input"      # From user query
    HISTORY = "history"            # From conversation history


class LLMOperationCategory(str, Enum):
    """High-level categories for LLM operations."""
    ARCHITECTURE_UNDERSTANDING = "architecture_understanding"
    COMPONENT_ANALYSIS = "component_analysis"
    RELATIONSHIP_ANALYSIS = "relationship_analysis"
    PATTERN_DETECTION = "pattern_detection"
    IMPROVEMENT_SUGGESTION = "improvement_suggestion"
    VALIDATION = "validation"


class GroundingSource(BaseModel):
    """Evidence source for LLM grounding."""
    source_type: LLMContextSource
    artifact_id: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Optional[List[str]] = None


class LLMUsage(BaseModel):
    """Token usage information from LLM provider."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMOperation(BaseModel):
    """Represents a single LLM operation request."""
    operation_type: LLMOperationType
    category: LLMOperationCategory
    system_prompt: str
    user_prompt: str
    context: Dict[str, Any]
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)


class LLMError(BaseModel):
    """Structured error information from LLM operations."""
    error_type: str
    message: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    retriable: bool = False


class LLMResponseMetadata(BaseModel):
    """Metadata for LLM responses."""
    provider: str
    model: str
    usage: LLMUsage
    latency_ms: float
    request_id: Optional[str] = None
    grounding_sources: List[GroundingSource] = Field(default_factory=list)
    raw_response: Optional[Dict[str, Any]] = None  # Provider-specific raw data


class LLMOperationResponse(BaseModel):
    """Response from an LLM operation."""
    operation_type: LLMOperationType
    category: LLMOperationCategory
    success: bool
    content: str = ""
    grounding_evidence: List[GroundingSource] = Field(default_factory=list)
    metadata: LLMResponseMetadata
    error: Optional[LLMError] = None
    explanation: Optional[str] = None  # User-facing explanation
    suggestions: List[str] = Field(default_factory=list)


class LLMMessage(BaseModel):
    """Single message in an LLM conversation."""
    role: str  # "system", "user", "assistant"
    content: str
    timestamp: Optional[float] = None
    operation_id: Optional[str] = None


class LLMConversationContext(BaseModel):
    """Context for multi-turn LLM conversations."""
    repository: str
    architecture_version: str
    analysis_version: str
    graph_version: str
    custom_context: Dict[str, Any] = Field(default_factory=dict)
    grounding_enabled: bool = True
    max_history_turns: int = 10


class LLMConversation(BaseModel):
    """Multi-turn conversation with an LLM."""
    id: str
    repository: str
    context: LLMConversationContext
    messages: List[LLMMessage] = Field(default_factory=list)
    created_at: float
    last_modified_at: float


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    provider_name: str
    model: str
    api_key: Optional[str] = None  # Never exposed in responses
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    retry_delay_ms: int = 100
    temperature: float = 0.7
    max_tokens_default: int = 2000


class LLMProviderCapabilities(BaseModel):
    """Capabilities of an LLM provider."""
    provider: str
    model: str
    supports_streaming: bool = False
    supports_functions: bool = False
    supports_vision: bool = False
    max_input_tokens: int
    max_output_tokens: int
    cost_per_1k_input_tokens: Optional[float] = None
    cost_per_1k_output_tokens: Optional[float] = None


class LLMContext(BaseModel):
    """Context information passed to LLM operations."""
    repository_name: str
    analysis_data: Optional[Dict[str, Any]] = None
    graph_data: Optional[Dict[str, Any]] = None
    architecture_data: Optional[Dict[str, Any]] = None
    user_focus: Optional[str] = None  # Component or aspect to focus on
    custom_context: Dict[str, Any] = Field(default_factory=dict)


class OperationRequest(BaseModel):
    """External request for an LLM operation."""
    operation_type: LLMOperationType
    query: str
    context: LLMContext
    options: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


class OperationResult(BaseModel):
    """Result of an LLM operation."""
    request_id: str
    success: bool
    operation_type: LLMOperationType
    result: str
    grounding: List[GroundingSource] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[LLMError] = None


class LLMSchemaVersion(BaseModel):
    """Version information for LLM schemas."""
    major: int
    minor: int
    patch: int
    schema_name: str
    description: str
    deprecated: bool = False
    deprecation_message: Optional[str] = None


# Schema version tracking
CURRENT_SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS = ["1.0.0"]


def get_schema_version() -> LLMSchemaVersion:
    """Get current schema version information."""
    return LLMSchemaVersion(
        major=1,
        minor=0,
        patch=0,
        schema_name="LLM Operations Schema",
        description="Typed Pydantic models for LLM operations and responses"
    )
