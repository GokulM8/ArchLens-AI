"""Tests for Phase 6.2 — LLM Schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError
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


class TestLLMEnums:
    """Test LLM schema enums."""

    def test_operation_type_enum(self):
        """LLMOperationType should have required values."""
        assert LLMOperationType.EXPLAIN.value == "explain"
        assert LLMOperationType.ASK.value == "ask"
        assert LLMOperationType.RECOMMEND.value == "recommend"
        assert LLMOperationType.ANALYZE.value == "analyze"
        assert LLMOperationType.VALIDATE.value == "validate"
        assert LLMOperationType.SUGGEST.value == "suggest"

    def test_context_source_enum(self):
        """LLMContextSource should have required values."""
        assert LLMContextSource.ANALYSIS.value == "analysis"
        assert LLMContextSource.GRAPH.value == "graph"
        assert LLMContextSource.ARCHITECTURE.value == "architecture"
        assert LLMContextSource.USER_INPUT.value == "user_input"
        assert LLMContextSource.HISTORY.value == "history"

    def test_operation_category_enum(self):
        """LLMOperationCategory should have required values."""
        assert LLMOperationCategory.ARCHITECTURE_UNDERSTANDING.value == "architecture_understanding"
        assert LLMOperationCategory.COMPONENT_ANALYSIS.value == "component_analysis"


class TestGroundingSource:
    """Test GroundingSource model."""

    def test_grounding_source_creation(self):
        """GroundingSource should be created with required fields."""
        source = GroundingSource(
            source_type=LLMContextSource.ANALYSIS,
            artifact_id="comp_123",
            description="Component analysis result",
            confidence=0.95
        )
        assert source.source_type == LLMContextSource.ANALYSIS
        assert source.artifact_id == "comp_123"
        assert source.confidence == 0.95

    def test_grounding_source_with_evidence(self):
        """GroundingSource should support evidence list."""
        source = GroundingSource(
            source_type=LLMContextSource.GRAPH,
            artifact_id="graph_001",
            description="Graph dependency",
            confidence=0.85,
            evidence=["imports_count=5", "in_degree=3"]
        )
        assert len(source.evidence) == 2
        assert "imports_count=5" in source.evidence

    def test_grounding_source_confidence_bounds(self):
        """GroundingSource confidence should be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            GroundingSource(
                source_type=LLMContextSource.ANALYSIS,
                artifact_id="test",
                description="test",
                confidence=1.5  # Invalid: > 1.0
            )


class TestLLMUsage:
    """Test LLMUsage model."""

    def test_llm_usage_creation(self):
        """LLMUsage should track token usage."""
        usage = LLMUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_llm_usage_total_consistency(self):
        """LLMUsage total should match prompt + completion."""
        usage = LLMUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens


class TestLLMOperation:
    """Test LLMOperation model."""

    def test_llm_operation_creation(self):
        """LLMOperation should be created with required fields."""
        operation = LLMOperation(
            operation_type=LLMOperationType.EXPLAIN,
            category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            system_prompt="You are an architecture expert",
            user_prompt="Explain this component",
            context={"component_id": "svc_123"}
        )
        assert operation.operation_type == LLMOperationType.EXPLAIN
        assert operation.temperature == 0.7  # Default

    def test_llm_operation_with_custom_params(self):
        """LLMOperation should accept temperature and max_tokens."""
        operation = LLMOperation(
            operation_type=LLMOperationType.RECOMMEND,
            category=LLMOperationCategory.IMPROVEMENT_SUGGESTION,
            system_prompt="System",
            user_prompt="User",
            context={},
            temperature=0.5,
            max_tokens=1000
        )
        assert operation.temperature == 0.5
        assert operation.max_tokens == 1000

    def test_llm_operation_temperature_bounds(self):
        """LLMOperation temperature should be between 0.0 and 2.0."""
        with pytest.raises(ValidationError):
            LLMOperation(
                operation_type=LLMOperationType.EXPLAIN,
                category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                system_prompt="test",
                user_prompt="test",
                context={},
                temperature=2.5  # Invalid: > 2.0
            )


class TestLLMError:
    """Test LLMError model."""

    def test_llm_error_creation(self):
        """LLMError should represent error information."""
        error = LLMError(
            error_type="timeout",
            message="Request timed out after 30s",
            code="TIMEOUT_30",
            retriable=True
        )
        assert error.error_type == "timeout"
        assert error.message == "Request timed out after 30s"
        assert error.retriable is True

    def test_llm_error_with_details(self):
        """LLMError should support additional details."""
        error = LLMError(
            error_type="validation",
            message="Invalid input",
            details={"field": "temperature", "reason": "out of bounds"}
        )
        assert error.details["field"] == "temperature"


class TestLLMResponseMetadata:
    """Test LLMResponseMetadata model."""

    def test_response_metadata_creation(self):
        """LLMResponseMetadata should track response information."""
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        metadata = LLMResponseMetadata(
            provider="openai",
            model="gpt-4o",
            usage=usage,
            latency_ms=250.5,
            request_id="req_123"
        )
        assert metadata.provider == "openai"
        assert metadata.model == "gpt-4o"
        assert metadata.latency_ms == 250.5

    def test_response_metadata_with_grounding(self):
        """LLMResponseMetadata should include grounding sources."""
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        source = GroundingSource(
            source_type=LLMContextSource.ANALYSIS,
            artifact_id="comp_1",
            description="Component data",
            confidence=0.9
        )
        metadata = LLMResponseMetadata(
            provider="openai",
            model="gpt-4o",
            usage=usage,
            latency_ms=100.0,
            grounding_sources=[source]
        )
        assert len(metadata.grounding_sources) == 1
        assert metadata.grounding_sources[0].artifact_id == "comp_1"


class TestLLMOperationResponse:
    """Test LLMOperationResponse model."""

    def test_operation_response_success(self):
        """LLMOperationResponse should represent successful operation."""
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        metadata = LLMResponseMetadata(
            provider="openai",
            model="gpt-4o",
            usage=usage,
            latency_ms=200.0
        )
        response = LLMOperationResponse(
            operation_type=LLMOperationType.EXPLAIN,
            category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            success=True,
            content="This is the explanation...",
            metadata=metadata
        )
        assert response.success is True
        assert response.error is None
        assert len(response.content) > 0

    def test_operation_response_failure(self):
        """LLMOperationResponse should represent failed operation."""
        usage = LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        metadata = LLMResponseMetadata(
            provider="openai",
            model="gpt-4o",
            usage=usage,
            latency_ms=100.0
        )
        error = LLMError(
            error_type="api_error",
            message="API limit exceeded",
            retriable=True
        )
        response = LLMOperationResponse(
            operation_type=LLMOperationType.ANALYZE,
            category=LLMOperationCategory.COMPONENT_ANALYSIS,
            success=False,
            content="",
            metadata=metadata,
            error=error
        )
        assert response.success is False
        assert response.error is not None

    def test_operation_response_with_suggestions(self):
        """LLMOperationResponse should support suggestions."""
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        metadata = LLMResponseMetadata(
            provider="openai",
            model="gpt-4o",
            usage=usage,
            latency_ms=150.0
        )
        response = LLMOperationResponse(
            operation_type=LLMOperationType.RECOMMEND,
            category=LLMOperationCategory.IMPROVEMENT_SUGGESTION,
            success=True,
            content="Recommendations",
            metadata=metadata,
            suggestions=["Split into microservices", "Add caching layer"]
        )
        assert len(response.suggestions) == 2


class TestLLMMessage:
    """Test LLMMessage model."""

    def test_message_creation(self):
        """LLMMessage should represent conversation message."""
        message = LLMMessage(
            role="user",
            content="Explain the architecture"
        )
        assert message.role == "user"
        assert message.content == "Explain the architecture"

    def test_message_with_metadata(self):
        """LLMMessage should support timestamp and operation_id."""
        message = LLMMessage(
            role="assistant",
            content="Here's the explanation",
            timestamp=1234567890.0,
            operation_id="op_123"
        )
        assert message.timestamp == 1234567890.0
        assert message.operation_id == "op_123"


class TestLLMConversationContext:
    """Test LLMConversationContext model."""

    def test_conversation_context_creation(self):
        """LLMConversationContext should define conversation scope."""
        context = LLMConversationContext(
            repository="my-app",
            architecture_version="1.0.0",
            analysis_version="1.0.0",
            graph_version="1.0.0"
        )
        assert context.repository == "my-app"
        assert context.grounding_enabled is True  # Default

    def test_conversation_context_with_custom(self):
        """LLMConversationContext should support custom context."""
        context = LLMConversationContext(
            repository="my-app",
            architecture_version="1.0.0",
            analysis_version="1.0.0",
            graph_version="1.0.0",
            custom_context={"focus": "microservices"}
        )
        assert context.custom_context["focus"] == "microservices"


class TestLLMConversation:
    """Test LLMConversation model."""

    def test_conversation_creation(self):
        """LLMConversation should represent multi-turn conversation."""
        ctx = LLMConversationContext(
            repository="my-app",
            architecture_version="1.0.0",
            analysis_version="1.0.0",
            graph_version="1.0.0"
        )
        conv = LLMConversation(
            id="conv_123",
            repository="my-app",
            context=ctx,
            created_at=1234567890.0,
            last_modified_at=1234567890.0
        )
        assert conv.id == "conv_123"
        assert len(conv.messages) == 0  # Initially empty

    def test_conversation_with_messages(self):
        """LLMConversation should accumulate messages."""
        ctx = LLMConversationContext(
            repository="my-app",
            architecture_version="1.0.0",
            analysis_version="1.0.0",
            graph_version="1.0.0"
        )
        msg1 = LLMMessage(role="user", content="Hello")
        msg2 = LLMMessage(role="assistant", content="Hi there")
        conv = LLMConversation(
            id="conv_456",
            repository="my-app",
            context=ctx,
            messages=[msg1, msg2],
            created_at=1234567890.0,
            last_modified_at=1234567900.0
        )
        assert len(conv.messages) == 2


class TestLLMProviderConfig:
    """Test LLMProviderConfig model."""

    def test_provider_config_creation(self):
        """LLMProviderConfig should define provider configuration."""
        config = LLMProviderConfig(
            provider_name="openai",
            model="gpt-4o",
            api_key="sk-proj-xxx"
        )
        assert config.provider_name == "openai"
        assert config.model == "gpt-4o"
        assert config.timeout == 30  # Default

    def test_provider_config_with_custom_values(self):
        """LLMProviderConfig should accept custom parameters."""
        config = LLMProviderConfig(
            provider_name="openai",
            model="gpt-4o",
            api_key="sk-proj-xxx",
            timeout=60,
            max_retries=5,
            temperature=0.5
        )
        assert config.timeout == 60
        assert config.max_retries == 5


class TestLLMProviderCapabilities:
    """Test LLMProviderCapabilities model."""

    def test_capabilities_creation(self):
        """LLMProviderCapabilities should describe provider capabilities."""
        caps = LLMProviderCapabilities(
            provider="openai",
            model="gpt-4o",
            max_input_tokens=128000,
            max_output_tokens=4096
        )
        assert caps.provider == "openai"
        assert caps.max_input_tokens == 128000
        assert caps.supports_streaming is False  # Default

    def test_capabilities_with_features(self):
        """LLMProviderCapabilities should list supported features."""
        caps = LLMProviderCapabilities(
            provider="openai",
            model="gpt-4o",
            supports_streaming=True,
            supports_functions=True,
            max_input_tokens=128000,
            max_output_tokens=4096,
            cost_per_1k_input_tokens=0.015,
            cost_per_1k_output_tokens=0.06
        )
        assert caps.supports_streaming is True
        assert caps.cost_per_1k_input_tokens == 0.015


class TestLLMContext:
    """Test LLMContext model."""

    def test_context_creation(self):
        """LLMContext should represent operation context."""
        context = LLMContext(
            repository_name="my-app",
            user_focus="auth_module"
        )
        assert context.repository_name == "my-app"
        assert context.user_focus == "auth_module"

    def test_context_with_data(self):
        """LLMContext should include analysis and architecture data."""
        analysis_data = {"total_files": 42, "languages": ["python"]}
        context = LLMContext(
            repository_name="my-app",
            analysis_data=analysis_data,
            custom_context={"focus": "patterns"}
        )
        assert context.analysis_data["total_files"] == 42


class TestOperationRequest:
    """Test OperationRequest model."""

    def test_operation_request_creation(self):
        """OperationRequest should represent external API request."""
        ctx = LLMContext(repository_name="my-app")
        req = OperationRequest(
            operation_type=LLMOperationType.EXPLAIN,
            query="What is this architecture?",
            context=ctx,
            request_id="req_789"
        )
        assert req.operation_type == LLMOperationType.EXPLAIN
        assert req.query == "What is this architecture?"
        assert req.request_id == "req_789"

    def test_operation_request_with_options(self):
        """OperationRequest should accept custom options."""
        ctx = LLMContext(repository_name="my-app")
        req = OperationRequest(
            operation_type=LLMOperationType.ANALYZE,
            query="Analyze",
            context=ctx,
            options={"depth": "detailed", "include_metrics": True}
        )
        assert req.options["depth"] == "detailed"


class TestOperationResult:
    """Test OperationResult model."""

    def test_operation_result_success(self):
        """OperationResult should represent operation result."""
        grounding = GroundingSource(
            source_type=LLMContextSource.ANALYSIS,
            artifact_id="comp_1",
            description="Result grounding",
            confidence=0.95
        )
        result = OperationResult(
            request_id="req_789",
            success=True,
            operation_type=LLMOperationType.EXPLAIN,
            result="Explanation content",
            grounding=[grounding]
        )
        assert result.success is True
        assert result.result == "Explanation content"

    def test_operation_result_failure(self):
        """OperationResult should handle failures."""
        error = LLMError(
            error_type="api_error",
            message="Service unavailable",
            retriable=True
        )
        result = OperationResult(
            request_id="req_999",
            success=False,
            operation_type=LLMOperationType.ANALYZE,
            result="",
            error=error
        )
        assert result.success is False
        assert result.error is not None


class TestLLMSchemaVersion:
    """Test LLMSchemaVersion model."""

    def test_schema_version_creation(self):
        """LLMSchemaVersion should represent schema version."""
        version = LLMSchemaVersion(
            major=1,
            minor=0,
            patch=0,
            schema_name="Test Schema",
            description="Test description"
        )
        assert version.major == 1
        assert version.deprecated is False  # Default

    def test_get_schema_version(self):
        """get_schema_version should return current schema."""
        version = get_schema_version()
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0

    def test_schema_version_constants(self):
        """Schema version constants should be defined."""
        assert CURRENT_SCHEMA_VERSION == "1.0.0"
        assert "1.0.0" in SUPPORTED_SCHEMA_VERSIONS


class TestSchemaIntegration:
    """Test schema integration and serialization."""

    def test_full_operation_flow(self):
        """Test creating a full operation request/response flow."""
        # Create request
        ctx = LLMContext(
            repository_name="my-app",
            user_focus="service_layer"
        )
        req = OperationRequest(
            operation_type=LLMOperationType.EXPLAIN,
            query="Explain the service layer",
            context=ctx
        )

        # Create response
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        grounding = GroundingSource(
            source_type=LLMContextSource.ARCHITECTURE,
            artifact_id="svc_layer_1",
            description="Service layer component",
            confidence=0.9
        )
        metadata = LLMResponseMetadata(
            provider="openai",
            model="gpt-4o",
            usage=usage,
            latency_ms=250.0,
            grounding_sources=[grounding]
        )
        response = LLMOperationResponse(
            operation_type=LLMOperationType.EXPLAIN,
            category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            success=True,
            content="The service layer handles business logic...",
            grounding_evidence=[grounding],
            metadata=metadata
        )

        # Verify flow
        assert req.operation_type == response.operation_type
        assert response.success is True
        assert len(response.grounding_evidence) > 0

    def test_schema_json_serialization(self):
        """Test that schemas serialize to JSON correctly."""
        source = GroundingSource(
            source_type=LLMContextSource.ANALYSIS,
            artifact_id="comp_1",
            description="Test",
            confidence=0.85
        )
        json_str = source.model_dump_json()
        assert "comp_1" in json_str
        assert "0.85" in json_str
