"""LLM Service — orchestrates LLM operations with verified context."""

from typing import Dict, Any, Optional, List, Callable
import os
import time
from enum import Enum

from app.llm.schemas import (
    LLMOperationType,
    LLMOperationCategory,
    LLMContext,
    LLMContextSource,
    GroundingSource,
    LLMOperation,
    LLMOperationResponse,
    LLMResponseMetadata,
    LLMError,
    LLMUsage,
    LLMMessage,
    LLMConversation,
    LLMConversationContext,
)
from app.llm.context import VerifiedContextBuilder
from app.llm.guardrails import GroundingGuardrails
from app.llm.factory import LLMProviderFactory


class LLMOperation(Enum):
    """Available LLM operations."""

    ARCHITECTURE_EXPLANATION = "architecture_explanation"
    ARCHITECTURE_QA = "architecture_qa"
    COMPONENT_EXPLANATION = "component_explanation"
    DEPENDENCY_EXPLANATION = "dependency_explanation"
    RISK_EXPLANATION = "risk_explanation"
    RECOMMENDATION_EXPLANATION = "recommendation_explanation"
    IMPACT_REASONING = "impact_reasoning"
    REFACTORING_PLAN = "refactoring_plan"
    REPOSITORY_SUMMARY = "repository_summary"


class LLMService:
    """Orchestrates LLM operations with verified context and guardrails."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        context_builder: VerifiedContextBuilder,
        guardrails: GroundingGuardrails,
    ):
        """
        Initialize the LLM service.

        Args:
            provider_factory: Factory for creating LLM providers
            context_builder: Builder for verified contexts
            guardrails: Grounding and validation guardrails
        """
        self.provider_factory = provider_factory
        self.context_builder = context_builder
        self.guardrails = guardrails

        # Operation handlers registry
        self._operation_handlers: Dict[LLMOperation, Callable] = {
            LLMOperation.ARCHITECTURE_EXPLANATION: self._handle_architecture_explanation,
            LLMOperation.ARCHITECTURE_QA: self._handle_architecture_qa,
            LLMOperation.COMPONENT_EXPLANATION: self._handle_component_explanation,
            LLMOperation.DEPENDENCY_EXPLANATION: self._handle_dependency_explanation,
            LLMOperation.RISK_EXPLANATION: self._handle_risk_explanation,
            LLMOperation.RECOMMENDATION_EXPLANATION: self._handle_recommendation_explanation,
            LLMOperation.IMPACT_REASONING: self._handle_impact_reasoning,
            LLMOperation.REFACTORING_PLAN: self._handle_refactoring_plan,
            LLMOperation.REPOSITORY_SUMMARY: self._handle_repository_summary,
        }

        # In-memory conversation store (multi-turn support, spec §29).
        self._conversations: Dict[str, LLMConversation] = {}

    async def execute_operation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        target: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """
        Execute an LLM operation with verified context and guardrails.

        Args:
            operation: Type of operation to execute
            request: Operation-specific request parameters
            target: Optional target component, risk, recommendation, etc.
            user_context: Optional user-specific context
            conversation_id: Optional conversation ID for multi-turn context
            user_id: Optional user ID for personalization

        Returns:
            LLMOperationResponse with results and metadata
        """
        # Validate that we have a configured provider
        if not self.provider_factory.is_configured():
            return LLMOperationResponse(
                operation_type=LLMOperationType.ASK,
                category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                success=False,
                content="LLM provider is not configured. Please set ARCHLENS_LLM_PROVIDER and ARCHLENS_LLM_API_KEY.",
                grounding_evidence=[],
                metadata=LLMResponseMetadata(
                    provider="none",
                    model="none",
                    usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    latency_ms=0.0,
                    request_id=request.get("request_id"),
                    grounding_sources=[],
                    raw_response={},
                ),
                error=LLMError(
                    error_type="configuration_error",
                    message="LLM provider is not configured",
                    details={"provider": "none", "api_key": "not_set"},
                    retriable=False,
                ),
                explanation="LLM provider is not configured. Deterministic ArchLens analysis is still available but LLM explanations are not.",
                suggestions=[
                    "Set ARCHLENS_LLM_PROVIDER=openai",
                    "Set ARCHLENS_LLM_API_KEY=your_api_key",
                    "Set ARCHLENS_LLM_MODEL=<model name> (optional)",
                ],
            )

        # Get the provider
        provider = self.provider_factory.create_provider()
        if not provider:
            return LLMOperationResponse(
                operation_type=LLMOperationType.ASK,
                category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                success=False,
                content="Failed to create LLM provider. Please check configuration.",
                grounding_evidence=[],
                metadata=LLMResponseMetadata(
                    provider="none",
                    model="none",
                    usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    latency_ms=0.0,
                    request_id=request.get("request_id"),
                    grounding_sources=[],
                    raw_response={},
                ),
                error=LLMError(
                    error_type="provider_creation_error",
                    message="Failed to create LLM provider",
                    retriable=True,
                ),
                explanation="The LLM provider could not be created from the current configuration.",
                suggestions=[
                    "Check ARCHLENS_LLM_PROVIDER configuration",
                    "Verify ARCHLENS_LLM_API_KEY is set correctly",
                    "Check provider configuration",
                ],
            )

        # Get the operation handler
        handler = self._operation_handlers.get(operation)
        if not handler:
            return LLMOperationResponse(
                operation_type=LLMOperationType.ASK,
                category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                success=False,
                content=f"Unknown operation: {operation.value}",
                grounding_evidence=[],
                metadata=LLMResponseMetadata(
                    provider=provider.provider_name,
                    model=provider.model,
                    usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    latency_ms=0.0,
                    request_id=request.get("request_id"),
                    grounding_sources=[],
                    raw_response={},
                ),
                error=LLMError(
                    error_type="invalid_operation",
                    message=f"Unknown operation: {operation.value}",
                    retriable=False,
                ),
                explanation=f"The operation '{operation.value}' is not supported.",
                suggestions=[
                    "Use one of the supported operations: " + ", ".join([op.value for op in LLMOperation]),
                ],
            )

        # Build appropriate context based on operation and target
        try:
            context = self._build_context_for_operation(operation, target, request, user_context)
        except ValueError as ve:
            # Unresolvable target (unknown risk/recommendation, malformed
            # dependency) → a clean structured error, never a raw exception.
            provider = self.provider_factory.create_provider()
            return LLMOperationResponse(
                operation_type=LLMOperationType.ASK,
                category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                success=False,
                content=f"Invalid operation target: {ve}",
                grounding_evidence=[],
                metadata=LLMResponseMetadata(
                    provider=provider.provider_name if provider else "none",
                    model=provider.model if provider else "none",
                    usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    latency_ms=0.0,
                    request_id=request.get("request_id"),
                    grounding_sources=[],
                    raw_response={},
                ),
                error=LLMError(
                    error_type="invalid_target",
                    message=str(ve),
                    retriable=False,
                ),
                explanation="The requested target could not be resolved from the deterministic ArchLens artifacts.",
                suggestions=[
                    "Provide a valid component id (e.g. module:app.main)",
                    "Provide a valid risk id from health.json",
                    "Provide a valid recommendation id from evolution.json",
                    "For dependencies, provide source||target (e.g. module:a||module:b)",
                ],
            )

        # Get provider-specific configuration for the operation
        provider_config = self._get_provider_config_for_operation(operation, request, user_context)

        # Inject prior conversation turns (multi-turn support, spec §29).
        provider_config = self._inject_conversation_history(provider_config, conversation_id)

        # Execute the handler
        try:
            response = await handler(operation, request, context, provider_config, conversation_id, user_id)
            # Persist the Q&A into the conversation for the next turn.
            self._record_conversation_turn(conversation_id, request, operation, response)
            return response
        except Exception as e:
            # Handle unexpected errors
            return LLMOperationResponse(
                operation_type=LLMOperationType.ASK,
                category=LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                success=False,
                content=f"Error during {operation.value}: {str(e)}",
                grounding_evidence=[],
                metadata=LLMResponseMetadata(
                    provider=provider.provider_name,
                    model=provider.model,
                    usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    latency_ms=0.0,
                    request_id=request.get("request_id"),
                    grounding_sources=[],
                    raw_response={},
                ),
                error=LLMError(
                    error_type="execution_error",
                    message=f"Error during {operation.value}: {str(e)}",
                    details={"operation": operation.value, "error": str(e)},
                    retriable=True,
                ),
                explanation=f"An unexpected error occurred while executing {operation.value}.",
                suggestions=[
                    "Try again with a simpler query",
                    "Check the operation parameters",
                    "Ensure all required artifacts are available",
                ],
            )

    # ------------------------------------------------------------------
    # Conversation support (spec §29)
    # ------------------------------------------------------------------

    def create_conversation(
        self,
        repository: str,
        conversation_id: Optional[str] = None,
        custom_context: Optional[Dict[str, Any]] = None,
        grounding_enabled: bool = True,
        max_history_turns: int = 10,
    ) -> LLMConversation:
        """
        Start a new multi-turn conversation.

        Args:
            repository: Repository name the conversation is about
            conversation_id: Optional explicit ID; a UUID is generated if omitted
            custom_context: Optional user-provided context dict
            grounding_enabled: Whether grounding guardrails apply
            max_history_turns: Max conversation turns included in prompts

        Returns:
            The newly created LLMConversation.
        """
        import uuid

        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        now = time.time()

        context = LLMConversationContext(
            repository=repository,
            architecture_version="",
            analysis_version="",
            graph_version="",
            custom_context=custom_context or {},
            grounding_enabled=grounding_enabled,
            max_history_turns=max_history_turns,
        )
        conversation = LLMConversation(
            id=conversation_id,
            repository=repository,
            context=context,
            messages=[],
            created_at=now,
            last_modified_at=now,
        )
        self._conversations[conversation_id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[LLMConversation]:
        """Retrieve a conversation by ID, or None if it does not exist."""
        return self._conversations.get(conversation_id)

    def list_conversations(self, repository: Optional[str] = None) -> List[LLMConversation]:
        """
        List stored conversations.

        Args:
            repository: Optional filter — only conversations for this repo.

        Returns:
            List of LLMConversation objects (newest-last).
        """
        conversations = list(self._conversations.values())
        if repository:
            conversations = [c for c in conversations if c.repository == repository]
        return conversations

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation. Returns True if a conversation was removed."""
        return self._conversations.pop(conversation_id, None) is not None

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        operation_id: Optional[str] = None,
    ) -> Optional[LLMMessage]:
        """
        Append a message to a conversation, trimming old turns to the max.

        Args:
            conversation_id: Target conversation
            role: "user", "assistant", or "system"
            content: Message text
            operation_id: Optional operation that produced this message

        Returns:
            The appended LLMMessage, or None if the conversation does not exist.
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        message = LLMMessage(
            role=role,
            content=content,
            timestamp=time.time(),
            operation_id=operation_id,
        )
        conversation.messages.append(message)
        conversation.last_modified_at = message.timestamp or time.time()

        # Trim to max_history_turns (each "turn" is a user+assistant pair).
        max_turns = max(1, conversation.context.max_history_turns)
        max_messages = max_turns * 2
        if len(conversation.messages) > max_messages:
            conversation.messages = conversation.messages[-max_messages:]
        return message

    def _format_conversation_history(
        self,
        conversation: LLMConversation,
    ) -> str:
        """
        Build a compact conversation-history section to include in a prompt.

        Args:
            conversation: The active conversation

        Returns:
            A formatted history block, or "" when empty.
        """
        if not conversation.messages:
            return ""
        lines = ["\n=== CONVERSATION HISTORY (previous turns) ==="]
        window = conversation.context.max_history_turns
        for message in conversation.messages[-window * 2:]:
            lines.append(f"{message.role}: {message.content}")
        return "\n".join(lines)

    def _inject_conversation_history(
        self,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Attach formatted prior-turn history to the provider config so that
        ``_request_to_llm_request`` can include it in the user prompt.

        Args:
            provider_config: Provider config for the current operation
            conversation_id: Active conversation id, if any

        Returns:
            The same provider_config (mutated in place).
        """
        history_section = ""
        if conversation_id:
            conversation = self._conversations.get(conversation_id)
            if conversation:
                history_section = self._format_conversation_history(conversation)
        provider_config["_conversation_history"] = history_section
        return provider_config

    def _record_conversation_turn(
        self,
        conversation_id: Optional[str],
        request: Dict[str, Any],
        operation: LLMOperation,
        response: LLMOperationResponse,
    ) -> None:
        """
        Persist the user query and assistant response into the conversation,
        if a conversation id was provided.

        Args:
            conversation_id: Active conversation id, if any
            request: The operation request
            operation: The operation that ran
            response: The operation response
        """
        if not conversation_id or not self._conversations.get(conversation_id):
            return
        if response.error is not None and response.metadata.provider == "none":
            return  # Discard configuration/provider errors — nothing to learn.

        user_text = request.get("query") or request.get("target") or operation.value
        self.append_message(
            conversation_id, "user", str(user_text), operation_id=operation.value
        )
        self.append_message(
            conversation_id, "assistant", response.content or "", operation_id=operation.value
        )

    # ------------------------------------------------------------------
    # Public operation methods (spec §§20–28)
    # ------------------------------------------------------------------

    async def explain_architecture(
        self,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§20 Explain the overall repository architecture."""
        return await self.execute_operation(
            LLMOperation.ARCHITECTURE_EXPLANATION,
            request or {},
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def ask(
        self,
        question: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **overrides: Any,
    ) -> LLMOperationResponse:
        """§21 Ask an architecture question about the repository."""
        request = dict(overrides)
        request["query"] = question
        return await self.execute_operation(
            LLMOperation.ARCHITECTURE_QA,
            request,
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def explain_component(
        self,
        component_id: str,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§22 Explain a specific component."""
        req = dict(request or {})
        req.setdefault("target", component_id)
        req.setdefault("query", f"Explain the component: {component_id}")
        return await self.execute_operation(
            LLMOperation.COMPONENT_EXPLANATION,
            req,
            target=component_id,
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def explain_dependency(
        self,
        source: str,
        target: str,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§23 Explain the dependency between two components."""
        req = dict(request or {})
        req.setdefault("target", f"{source}||{target}")
        req.setdefault("query", f"Explain the dependency from {source} to {target}")
        return await self.execute_operation(
            LLMOperation.DEPENDENCY_EXPLANATION,
            req,
            target=f"{source}||{target}",
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def explain_risk(
        self,
        risk_id: str,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§24 Explain a specific architectural risk."""
        req = dict(request or {})
        req.setdefault("target", risk_id)
        req.setdefault("query", f"Explain the risk: {risk_id}")
        return await self.execute_operation(
            LLMOperation.RISK_EXPLANATION,
            req,
            target=risk_id,
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def explain_recommendation(
        self,
        recommendation_id: str,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§25 Explain a specific evolution recommendation."""
        req = dict(request or {})
        req.setdefault("target", recommendation_id)
        req.setdefault("query", f"Explain the recommendation: {recommendation_id}")
        return await self.execute_operation(
            LLMOperation.RECOMMENDATION_EXPLANATION,
            req,
            target=recommendation_id,
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def explain_impact(
        self,
        component_id: str,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§26 Analyze the impact of changing a component."""
        req = dict(request or {})
        req.setdefault("target", component_id)
        req.setdefault("query", f"What is the impact of changing {component_id}?")
        return await self.execute_operation(
            LLMOperation.IMPACT_REASONING,
            req,
            target=component_id,
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def generate_refactoring_plan(
        self,
        recommendation_id: str,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§27 Generate a refactoring plan for a recommendation."""
        req = dict(request or {})
        req.setdefault("target", recommendation_id)
        req.setdefault("query", f"Generate a refactoring plan for: {recommendation_id}")
        return await self.execute_operation(
            LLMOperation.REFACTORING_PLAN,
            req,
            target=recommendation_id,
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def summarize_repository(
        self,
        request: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LLMOperationResponse:
        """§28 Summarize the repository architecture."""
        return await self.execute_operation(
            LLMOperation.REPOSITORY_SUMMARY,
            request or {},
            user_context=user_context,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def _build_context_for_operation(
        self,
        operation: LLMOperation,
        target: Optional[str],
        request: Dict[str, Any],
        user_context: Optional[Dict[str, Any]],
    ) -> LLMContext:
        """
        Build the appropriate context for the operation.

        Args:
            operation: Type of operation
            target: Optional target
            request: Operation request
            user_context: Optional user context

        Returns:
            LLMContext for the operation
        """
        # Map operation types to context selection
        operation_type_mapping = {
            LLMOperation.ARCHITECTURE_EXPLANATION: "architecture_explanation",
            LLMOperation.ARCHITECTURE_QA: "architecture_qa",
            LLMOperation.COMPONENT_EXPLANATION: "component_explanation",
            LLMOperation.DEPENDENCY_EXPLANATION: "dependency_explanation",
            LLMOperation.RISK_EXPLANATION: "risk_explanation",
            LLMOperation.RECOMMENDATION_EXPLANATION: "recommendation_explanation",
            LLMOperation.IMPACT_REASONING: "impact_reasoning",
            LLMOperation.REFACTORING_PLAN: "refactoring_plan",
            LLMOperation.REPOSITORY_SUMMARY: "repository_summary",
        }

        operation_str = operation_type_mapping.get(operation)
        if not operation_str:
            operation_str = operation.value

        # A user focus is an optional string; user_context is a dict of options.
        focus = (user_context or {}).get("focus") if isinstance(user_context, dict) else None

        # Use the context builder to select appropriate context
        return self.context_builder.select_context_for_operation(
            operation_str, target, focus
        )

    def _get_provider_config_for_operation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        user_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Get provider configuration for the operation.

        Args:
            operation: Type of operation
            request: Operation request
            user_context: Optional user context

        Returns:
            Provider configuration
        """
        # Default provider configuration — model defaults come from env (never hard-coded).
        default_model = os.getenv("ARCHLENS_LLM_MODEL", "")
        config = {
            "model": default_model,
            "temperature": 0.7,
            "max_tokens": None,
            "system_prompt": self._get_system_prompt_for_operation(operation),
        }

        # Override with request-specific configuration
        if "model" in request:
            config["model"] = request["model"]

        if "temperature" in request:
            config["temperature"] = request["temperature"]

        if "max_tokens" in request:
            config["max_tokens"] = request["max_tokens"]

        if "system_prompt" in request:
            config["system_prompt"] = request["system_prompt"]

        # Override with user context if provided
        if user_context:
            if "model" in user_context:
                config["model"] = user_context["model"]

            if "temperature" in user_context:
                config["temperature"] = user_context["temperature"]

            if "max_tokens" in user_context:
                config["max_tokens"] = user_context["max_tokens"]

            if "system_prompt" in user_context:
                config["system_prompt"] = user_context["system_prompt"]

        return config

    def _get_system_prompt_for_operation(self, operation: LLMOperation) -> str:
        """
        Get the system prompt for an operation.

        Args:
            operation: Type of operation

        Returns:
            System prompt string
        """
        # These prompts should be loaded from the prompts module
        # For now, provide basic versions

        prompts = {
            LLMOperation.ARCHITECTURE_EXPLANATION: """
You are ArchLens Architecture Copilot.

ArchLens has already analyzed this repository using deterministic
static analysis, graph analysis, architecture inference, health analysis,
and evolution analysis.

The supplied ArchLens artifacts are authoritative for repository facts.

DO NOT invent files, modules, classes, functions, routes, dependencies,
relationships, layers, roles, metrics, risks, or recommendations.

If the supplied evidence is insufficient, explicitly state so.

Distinguish verified facts from reasoning and suggestions.

DO NOT override deterministic ArchLens findings.

Use the supplied evidence when explaining architectural conclusions.
""",
            LLMOperation.ARCHITECTURE_QA: """
You are ArchLens Architecture Copilot.

ArchLens has analyzed this repository and provides verified facts about
its architecture, components, dependencies, and evolution.

Answer questions based ONLY on the supplied ArchLens artifacts.

Distinguish between:
1. Verified facts from deterministic analysis
2. Interpretations and reasoning from deterministic artifacts
3. LLM-generated explanations and suggestions

If you don't have enough information from the artifacts, explicitly state so.
""",
            LLMOperation.COMPONENT_EXPLANATION: """
You are ArchLens Architecture Copilot specializing in component analysis.

Provide detailed explanations of repository components based on ArchLens
analysis. Include:
- Component role and layer
- Responsibilities and dependencies
- Health findings and risks
- Evolution recommendations
- Impact analysis

Use only the information provided in the context.
""",
            LLMOperation.DEPENDENCY_EXPLANATION: """
You are ArchLens Architecture Copilot specializing in dependency analysis.

Explain dependencies between components based on the dependency graph.
Include:
- Direct and indirect dependencies
- Dependency types and relationships
- Alternative paths and complexity
- Impact on system architecture
- Health and risk implications

Use only the dependency information from the context.
""",
            LLMOperation.RISK_EXPLANATION: """
You are ArchLens Architecture Copilot specializing in risk analysis.

Explain architectural risks based on ArchLens health analysis.
Include:
- Risk type and severity
- Affected components and evidence
- Architectural implications
- Recommendations for mitigation
- Context from deterministic analysis

Use only the risk information from the context.
""",
            LLMOperation.RECOMMENDATION_EXPLANATION: """
You are ArchLens Architecture Copilot specializing in recommendations.

Explain evolution recommendations based on ArchLens analysis.
Include:
- Recommendation type and priority
- Evidence and reasoning
- Affected components
- Implementation guidance
- Impact analysis

Use only the recommendation information from the context.
""",
            LLMOperation.IMPACT_REASONING: """
You are ArchLens Architecture Copilot specializing in impact analysis.

Analyze the impact of changes on the repository architecture.
Include:
- Direct and indirect effects
- Dependency chains
- Architectural implications
- Risk considerations
- Recommendations for safe changes

Use only the impact information from the context.
""",
            LLMOperation.REFACTORING_PLAN: """
You are ArchLens Architecture Copilot specializing in refactoring planning.

Create structured refactoring plans based on evolution recommendations.
Include:
- Step-by-step implementation sequence
- Validation checkpoints
- Risk mitigation strategies
- Dependencies and ordering
- Expected outcomes and metrics

Ground the plan in the supplied ArchLens artifacts.
""",
            LLMOperation.REPOSITORY_SUMMARY: """
You are ArchLens Architecture Copilot providing repository summaries.

Create developer-friendly summaries of repository architecture and patterns.
Include:
- Project purpose and structure
- Major components and their roles
- Architecture patterns and styles
- Key dependencies and data flow
- Health status and improvement areas
- Areas worth investigating

Based on deterministic ArchLens analysis artifacts.
""",
        }

        return prompts.get(operation, """
You are ArchLens Architecture Copilot.

Provide architectural explanations based on deterministic analysis artifacts.
Use only verified facts from the supplied context.
Distinguish between facts, deterministic interpretations, and LLM reasoning.
""")

    # Operation handler methods

    async def _handle_architecture_explanation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle architecture explanation operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                "No provider available",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_architecture_explanation_prompt(context, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.EXPLAIN,
            LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_architecture_qa(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle architecture Q&A operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.ASK,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                "No provider available",
                request.get("request_id"),
            )

        # Extract question from request
        question = request.get("query", "")
        if not question:
            return self._create_error_response(
                LLMOperationType.ASK,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                "No question provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_architecture_qa_prompt(context, question, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.ASK,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.ASK,
            LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_component_explanation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle component explanation operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.COMPONENT_ANALYSIS,
                "No provider available",
                request.get("request_id"),
            )

        # Extract component from request
        target = request.get("target", "")
        if not target:
            return self._create_error_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.COMPONENT_ANALYSIS,
                "No component target provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_component_explanation_prompt(context, target, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.COMPONENT_ANALYSIS,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.EXPLAIN,
            LLMOperationCategory.COMPONENT_ANALYSIS,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_dependency_explanation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle dependency explanation operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.ANALYZE,
                LLMOperationCategory.RELATIONSHIP_ANALYSIS,
                "No provider available",
                request.get("request_id"),
            )

        # Extract dependency from request
        target = request.get("target", "")
        if not target:
            return self._create_error_response(
                LLMOperationType.ANALYZE,
                LLMOperationCategory.RELATIONSHIP_ANALYSIS,
                "No dependency target provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_dependency_explanation_prompt(context, target, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.ANALYZE,
                LLMOperationCategory.RELATIONSHIP_ANALYSIS,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.ANALYZE,
            LLMOperationCategory.RELATIONSHIP_ANALYSIS,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_risk_explanation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle risk explanation operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.VALIDATE,
                LLMOperationCategory.VALIDATION,
                "No provider available",
                request.get("request_id"),
            )

        # Extract risk from request
        target = request.get("target", "")
        if not target:
            return self._create_error_response(
                LLMOperationType.VALIDATE,
                LLMOperationCategory.VALIDATION,
                "No risk target provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_risk_explanation_prompt(context, target, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.VALIDATE,
                LLMOperationCategory.VALIDATION,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.VALIDATE,
            LLMOperationCategory.VALIDATION,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_recommendation_explanation(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle recommendation explanation operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.RECOMMEND,
                LLMOperationCategory.IMPROVEMENT_SUGGESTION,
                "No provider available",
                request.get("request_id"),
            )

        # Extract recommendation from request
        target = request.get("target", "")
        if not target:
            return self._create_error_response(
                LLMOperationType.RECOMMEND,
                LLMOperationCategory.IMPROVEMENT_SUGGESTION,
                "No recommendation target provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_recommendation_explanation_prompt(context, target, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.RECOMMEND,
                LLMOperationCategory.IMPROVEMENT_SUGGESTION,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.RECOMMEND,
            LLMOperationCategory.IMPROVEMENT_SUGGESTION,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_impact_reasoning(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle impact reasoning operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.ASK,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                "No provider available",
                request.get("request_id"),
            )

        # Extract component from request
        target = request.get("target", "")
        if not target:
            return self._create_error_response(
                LLMOperationType.ASK,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                "No component target provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_impact_reasoning_prompt(context, target, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.ASK,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.ASK,
            LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_refactoring_plan(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle refactoring plan operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.SUGGEST,
                LLMOperationCategory.IMPROVEMENT_SUGGESTION,
                "No provider available",
                request.get("request_id"),
            )

        # Extract recommendation from request
        target = request.get("target", "")
        if not target:
            return self._create_error_response(
                LLMOperationType.SUGGEST,
                LLMOperationCategory.IMPROVEMENT_SUGGESTION,
                "No recommendation target provided",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_refactoring_plan_prompt(context, target, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.SUGGEST,
                LLMOperationCategory.IMPROVEMENT_SUGGESTION,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.SUGGEST,
            LLMOperationCategory.IMPROVEMENT_SUGGESTION,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    async def _handle_repository_summary(
        self,
        operation: LLMOperation,
        request: Dict[str, Any],
        context: LLMContext,
        provider_config: Dict[str, Any],
        conversation_id: Optional[str],
        user_id: Optional[str],
    ) -> LLMOperationResponse:
        """Handle repository summary operation."""
        provider = self.provider_factory.create_provider()
        if not provider:
            return self._create_error_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                "No provider available",
                request.get("request_id"),
            )

        # Build prompt
        prompt = self._build_repository_summary_prompt(context, request)

        # Generate response
        response = await provider.generate(self._request_to_llm_request(prompt, provider_config))

        # Apply guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)
        if not validation_result.is_valid:
            return self._create_validated_response(
                LLMOperationType.EXPLAIN,
                LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
                prompt,
                response,
                context,
                request.get("request_id"),
                validation_result,
            )

        return self._create_success_response(
            LLMOperationType.EXPLAIN,
            LLMOperationCategory.ARCHITECTURE_UNDERSTANDING,
            prompt,
            response,
            context,
            request.get("request_id"),
        )

    # Prompt building methods

    def _build_architecture_explanation_prompt(
        self, context: LLMContext, request: Dict[str, Any]
    ) -> str:
        """Build prompt for architecture explanation."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append("Explain the overall architecture of this repository based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. High-level structure and organization")
        prompt_parts.append("2. Major architectural layers and their purposes")
        prompt_parts.append("3. Key components and their roles")
        prompt_parts.append("4. Entry points and interfaces")
        prompt_parts.append("5. Architectural patterns and styles")
        prompt_parts.append("6. Health concerns and improvement areas")
        prompt_parts.append("7. Evolution opportunities")
        prompt_parts.append("")
        prompt_parts.append("Use only the information provided in the context. Ground all claims in the deterministic artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Keep the explanation clear and actionable for developers.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        if context.architecture_data and "components" in context.architecture_data:
            for comp in context.architecture_data["components"]:
                prompt_parts.append(f"- {comp.get('id', '')}: {comp.get('role', '')} in layer '{comp.get('layer', '')}'")

        if context.health_data and "risks" in context.health_data:
            prompt_parts.append("\nKey Health Findings:")
            for finding in context.health_data["risks"]:
                prompt_parts.append(
                    f"- {finding.get('type', '')}: {finding.get('title', finding.get('description', ''))} "
                    f"(Severity: {finding.get('severity', '')})"
                )

        return "\n".join(prompt_parts) + "\n\nPlease provide a comprehensive architecture explanation."

    def _build_architecture_qa_prompt(
        self, context: LLMContext, question: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for architecture Q&A."""
        prompt = "You are ArchLens Architecture Copilot.\n\n"
        prompt += "Answer this question about the repository architecture:\n\n"
        prompt += f"Question: {question}\n\n"
        prompt += "Based on the supplied ArchLens analysis artifacts.\n\n"
        prompt += "When answering:\n"
        prompt += "1. Ground all facts in the deterministic artifacts\n"
        prompt += "2. Distinguish between verified facts and reasoning\n"
        prompt += "3. Be explicit about information gaps\n"
        prompt += "4. Use context from the relevant artifacts\n"
        prompt += "5. Keep answers clear and actionable\n\n"
        prompt += f"Repository: {context.repository_name}\n\n"

        return prompt + "Please provide a comprehensive answer."

    def _build_component_explanation_prompt(
        self, context: LLMContext, target: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for component explanation."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append(f"Explain component '{target}' in detail based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. Component role, layer, and purpose")
        prompt_parts.append("2. Responsibilities and functionality")
        prompt_parts.append("3. Dependencies and dependents")
        prompt_parts.append("4. Health status and risks")
        prompt_parts.append("5. Evolution recommendations")
        prompt_parts.append("6. Impact analysis")
        prompt_parts.append("7. Architectural significance")
        prompt_parts.append("")
        prompt_parts.append("Use only the information provided in the context. Ground all claims in the deterministic artifacts.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add component-specific information from context
        cc = context.custom_context or {}
        if cc.get("name") or cc.get("role") or cc.get("layer"):
            prompt_parts.append("\nComponent Information:")
            prompt_parts.append(f"- Name: {cc.get('name', 'N/A')}")
            if cc.get("path"):
                prompt_parts.append(f"- Path: {cc.get('path')}")
            if cc.get("role"):
                prompt_parts.append(f"- Role: {cc.get('role')}")
            if cc.get("layer"):
                prompt_parts.append(f"- Layer: {cc.get('layer')}")
            if cc.get("confidence"):
                prompt_parts.append(f"- Classification confidence: {cc.get('confidence')}")

        if cc.get("dependencies"):
            prompt_parts.append(f"\nDependencies: {', '.join(cc['dependencies']) if cc['dependencies'] else 'None'}")

        if cc.get("dependents"):
            prompt_parts.append(f"Dependents: {', '.join(cc['dependents']) if cc['dependents'] else 'None'}")

        if cc.get("routes"):
            prompt_parts.append(f"Routes: {', '.join(cc['routes'])}")

        risks = cc.get("risks") or []
        if risks:
            prompt_parts.append(f"\nHealth Risks ({len(risks)}):")
            for risk in risks[:5]:
                prompt_parts.append(
                    f"- [{risk.get('severity')}] {risk.get('type')}: {risk.get('title')} — {risk.get('description')}"
                )

        refactorings = cc.get("refactorings") or []
        if refactorings:
            prompt_parts.append(f"\nRefactoring Opportunities ({len(refactorings)}):")
            for opp in refactorings[:5]:
                prompt_parts.append(
                    f"- [{opp.get('priority')}] {opp.get('type')}: {opp.get('title')} — {opp.get('rationale')}"
                )

        return "\n".join(prompt_parts) + "\n\nPlease provide a detailed component explanation."

    def _build_dependency_explanation_prompt(
        self, context: LLMContext, target: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for dependency explanation."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append(f"Explain the dependency '{target}' in this repository based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. Dependency type and relationship")
        prompt_parts.append("2. Source and target components")
        prompt_parts.append("3. Dependency paths and complexity")
        prompt_parts.append("4. Architectural implications")
        prompt_parts.append("5. Health and risk considerations")
        prompt_parts.append("6. Evolution recommendations")
        prompt_parts.append("")
        prompt_parts.append("Use only the dependency information from the context. Ground all claims in the deterministic artifacts.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add dependency-specific information from context
        cc = context.custom_context or {}
        if cc.get("source_component") and cc.get("target_component"):
            prompt_parts.append(
                f"\nDependency: {cc['source_component']} {cc.get('directed', '->')} {cc['target_component']}"
            )
        if cc.get("relationship_types"):
            prompt_parts.append(f"Relationship Types: {', '.join(cc['relationship_types'])}")
        if cc.get("source_role") or cc.get("target_role"):
            prompt_parts.append(
                f"Roles: {cc.get('source_role', '?')} -> {cc.get('target_role', '?')}"
            )
        if cc.get("source_layer") or cc.get("target_layer"):
            prompt_parts.append(
                f"Layers: {cc.get('source_layer', '?')} -> {cc.get('target_layer', '?')}"
            )
        edges = cc.get("edges") or []
        if edges:
            prompt_parts.append(f"\nDependency Edges ({len(edges)}):")
            for edge in edges:
                prompt_parts.append(
                    f"- {edge.get('source')} -> {edge.get('target')} ({edge.get('type', 'IMPORTS')})"
                )

        return "\n".join(prompt_parts) + "\n\nPlease provide a detailed dependency explanation."

    def _build_risk_explanation_prompt(
        self, context: LLMContext, target: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for risk explanation."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append(f"Explain risk '{target}' in this repository based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. Risk type and severity")
        prompt_parts.append("2. Affected components")
        prompt_parts.append("3. Evidence and supporting data")
        prompt_parts.append("4. Architectural implications")
        prompt_parts.append("5. Recommendations for mitigation")
        prompt_parts.append("6. Impact analysis")
        prompt_parts.append("")
        prompt_parts.append("Use only the risk information from the context. Ground all claims in the deterministic artifacts.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add risk-specific information from context
        cc = context.custom_context or {}
        if cc.get("risk_type"):
            prompt_parts.append(f"\nRisk Type: {cc.get('risk_type')}")
        if cc.get("severity"):
            prompt_parts.append(f"Severity: {cc.get('severity')}")
        if cc.get("affected_components"):
            prompt_parts.append(f"Affected Components: {', '.join(str(c) for c in (cc.get('affected_components') or []))}")
        if cc.get("title"):
            prompt_parts.append(f"Title: {cc.get('title')}")
        if cc.get("description"):
            prompt_parts.append(f"Description: {cc.get('description')}")
        if cc.get("metric"):
            prompt_parts.append(f"Metric: {cc.get('metric')}")
        evidence = cc.get("evidence") or []
        if evidence:
            prompt_parts.append("\nEvidence:")
            for item in evidence:
                prompt_parts.append(f"- {item}")
        if cc.get("recommendation"):
            prompt_parts.append(f"\nRelated Recommendation: {cc.get('recommendation')}")

        return "\n".join(prompt_parts) + "\n\nPlease provide a detailed risk explanation."

    def _build_recommendation_explanation_prompt(
        self, context: LLMContext, target: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for recommendation explanation."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append(f"Explain recommendation '{target}' in this repository based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. Recommendation type and priority")
        prompt_parts.append("2. Affected component(s)")
        prompt_parts.append("3. Evidence and reasoning")
        prompt_parts.append("4. Implementation guidance")
        prompt_parts.append("5. Expected impact")
        prompt_parts.append("6. Architectural implications")
        prompt_parts.append("")
        prompt_parts.append("Use only the recommendation information from the context. Ground all claims in the deterministic artifacts.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add recommendation-specific information from context
        cc = context.custom_context or {}
        if cc.get("recommendation_type"):
            prompt_parts.append(f"\nRecommendation Type: {cc.get('recommendation_type')}")
        if cc.get("priority"):
            prompt_parts.append(f"Priority: {cc.get('priority')}")
        if cc.get("title"):
            prompt_parts.append(f"Title: {cc.get('title')}")
        if cc.get("affected_components"):
            prompt_parts.append(f"Affected Components: {', '.join(str(c) for c in (cc.get('affected_components') or []))}")
        if cc.get("rationale"):
            prompt_parts.append(f"Rationale: {cc.get('rationale')}")
        if cc.get("suggested_action"):
            prompt_parts.append(f"Suggested Action: {cc.get('suggested_action')}")
        if cc.get("expected_benefit"):
            prompt_parts.append(f"Expected Benefit: {cc.get('expected_benefit')}")
        evidence = cc.get("evidence") or []
        if evidence:
            prompt_parts.append("\nEvidence:")
            for item in evidence:
                prompt_parts.append(f"- {item}")
        related_risks = cc.get("related_risks") or []
        if related_risks:
            prompt_parts.append(f"\nRelated Risks ({len(related_risks)}):")
            for risk in related_risks[:5]:
                prompt_parts.append(
                    f"- [{risk.get('severity')}] {risk.get('type')}: {risk.get('title')}"
                )
        impact_analysis = cc.get("impact_analysis") or {}
        if impact_analysis:
            prompt_parts.append(
                f"\nImpact: {impact_analysis.get('total_impact_count', 0)} affected (level {impact_analysis.get('impact_level')})"
            )

        return "\n".join(prompt_parts) + "\n\nPlease provide a detailed recommendation explanation."

    def _build_impact_reasoning_prompt(
        self, context: LLMContext, target: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for impact reasoning."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append(f"Analyze the impact of changes to component '{target}' in this repository based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. Direct and indirect effects")
        prompt_parts.append("2. Dependency chains and propagation")
        prompt_parts.append("3. Architectural implications")
        prompt_parts.append("4. Health and risk considerations")
        prompt_parts.append("5. Recommendations for safe changes")
        prompt_parts.append("6. Validation checkpoints")
        prompt_parts.append("")
        prompt_parts.append("Use only the impact information from the context. Ground all claims in the deterministic artifacts.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add impact-specific information from context
        cc = context.custom_context or {}
        if cc.get("directly_affected_components"):
            prompt_parts.append(
                f"\nDirectly Affected Components ({len(cc['directly_affected_components'])}): "
                f"{', '.join(str(c) for c in cc['directly_affected_components'])}"
            )
        if cc.get("indirectly_affected_components"):
            prompt_parts.append(
                f"Indirectly Affected Components ({len(cc['indirectly_affected_components'])}): "
                f"{', '.join(str(c) for c in cc['indirectly_affected_components'][:20])}"
            )
        if cc.get("depends_on"):
            prompt_parts.append(
                f"Component Depends On: {', '.join(str(c) for c in cc['depends_on'])}"
            )
        if cc.get("impact_level") is not None:
            prompt_parts.append(f"Impact Level: {cc.get('impact_level')}")
        if cc.get("affected_routes") is not None:
            prompt_parts.append(f"Affected Routes: {cc.get('affected_routes')}")
        if cc.get("affected_dependencies") is not None:
            prompt_parts.append(f"Affected Dependencies: {cc.get('affected_dependencies')}")

        return "\n".join(prompt_parts) + "\n\nPlease provide a comprehensive impact analysis."

    def _build_refactoring_plan_prompt(
        self, context: LLMContext, target: str, request: Dict[str, Any]
    ) -> str:
        """Build prompt for refactoring plan."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append(f"Create a structured refactoring plan for recommendation '{target}' in this repository based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Include:")
        prompt_parts.append("1. Step-by-step implementation sequence")
        prompt_parts.append("2. Validation checkpoints")
        prompt_parts.append("3. Risk mitigation strategies")
        prompt_parts.append("4. Dependencies and ordering")
        prompt_parts.append("5. Expected outcomes and metrics")
        prompt_parts.append("6. Architectural considerations")
        prompt_parts.append("")
        prompt_parts.append("Ground the plan in the supplied ArchLens artifacts. Use only the information provided in the context.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add recommendation-specific information from context
        cc = context.custom_context or {}
        if cc.get("recommendation_type"):
            prompt_parts.append(f"\nRecommendation: {cc.get('recommendation_type')}")
        if cc.get("priority"):
            prompt_parts.append(f"Priority: {cc.get('priority')}")
        if cc.get("affected_components"):
            prompt_parts.append(f"Affected Components: {', '.join(str(c) for c in (cc.get('affected_components') or []))}")
        if cc.get("rationale"):
            prompt_parts.append(f"Rationale: {cc.get('rationale')}")
        if cc.get("suggested_action"):
            prompt_parts.append(f"Suggested Action: {cc.get('suggested_action')}")
        if cc.get("expected_benefit"):
            prompt_parts.append(f"Expected Benefit: {cc.get('expected_benefit')}")

        return "\n".join(prompt_parts) + "\n\nPlease provide a comprehensive refactoring plan."

    def _build_repository_summary_prompt(
        self, context: LLMContext, request: Dict[str, Any]
    ) -> str:
        """Build prompt for repository summary."""
        prompt_parts = []
        prompt_parts.append("You are ArchLens Architecture Copilot.")
        prompt_parts.append("")
        prompt_parts.append("Create a comprehensive developer-friendly summary of the repository architecture and patterns based on the supplied ArchLens analysis artifacts.")
        prompt_parts.append("")
        prompt_parts.append("Focus on:")
        prompt_parts.append("1. Project purpose and structure")
        prompt_parts.append("2. Overall architecture organization")
        prompt_parts.append("3. Major components and their roles")
        prompt_parts.append("4. Business logic and data access patterns")
        prompt_parts.append("5. Key dependencies and data flow")
        prompt_parts.append("6. Architectural styles and patterns")
        prompt_parts.append("7. Health status and improvement areas")
        prompt_parts.append("8. Areas worth investigating")
        prompt_parts.append("")
        prompt_parts.append("Use only the information from the deterministic artifacts. Ground all claims in the verified facts.")
        prompt_parts.append("")
        prompt_parts.append(f"Repository: {context.repository_name}")

        # Add summary information from context
        if context.custom_context:
            prompt_parts.append("\nRepository Overview:")
            for key, value in context.custom_context.items():
                if isinstance(value, (int, str, list)):
                    prompt_parts.append(f"- {key}: {value}")

        return "\n".join(prompt_parts) + "\n\nPlease provide a comprehensive repository summary for developers."

    # Helper methods

    def _request_to_llm_request(self, prompt: str, provider_config: Dict[str, Any]) -> Any:
        """Convert internal request format to LLMProvider request format."""
        from app.llm.provider import LLMRequest

        # Attach prior conversation turns (spec §29) as trailing context.
        history = provider_config.get("_conversation_history") or ""
        user_prompt = f"{prompt}\n{history}" if history else prompt

        return LLMRequest(
            system_prompt=provider_config.get("system_prompt", ""),
            user_prompt=user_prompt,
            context={},
            temperature=provider_config.get("temperature", 0.7),
            max_tokens=provider_config.get("max_tokens"),
        )

    def _create_success_response(
        self,
        operation_type: LLMOperationType,
        category: LLMOperationCategory,
        prompt: str,
        response: Any,
        context: LLMContext,
        request_id: Optional[str],
    ) -> LLMOperationResponse:
        """Create a successful LLM operation response."""
        from app.llm.guardrails import GroundingGuardrails

        # Validate content with guardrails
        validation_result = self.guardrails.validate_repository_facts(response.content)

        # Build grounding evidence from context
        grounding_sources = []
        if context.architecture_data and "components" in context.architecture_data:
            for comp in context.architecture_data["components"]:
                if comp.get("id"):
                    grounding_sources.append(
                        GroundingSource(
                            source_type=LLMContextSource.ARCHITECTURE,
                            artifact_id=f"component:{comp['id']}",
                            description=f"Component: {comp.get('id', '')} ({comp.get('role', '')})",
                            confidence=1.0,
                            evidence=[f"Layer: {comp.get('layer', '')}", f"Role: {comp.get('role', '')}"],
                        )
                    )

        # Create metadata
        metadata = LLMResponseMetadata(
            provider=response.provider,
            model=response.model,
            usage=response.usage or LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=response.latency_ms or 0.0,
            request_id=request_id,
            grounding_sources=grounding_sources,
            raw_response={},
        )

        return LLMOperationResponse(
            operation_type=operation_type,
            category=category,
            success=True,
            content=response.content,
            grounding_evidence=grounding_sources,
            metadata=metadata,
            error=None,
            explanation=f"Successfully generated {operation_type.value} using {response.provider} provider.",
            suggestions=[],  # Will be populated based on operation
        )

    def _create_error_response(
        self,
        operation_type: LLMOperationType,
        category: LLMOperationCategory,
        error_message: str,
        request_id: Optional[str],
    ) -> LLMOperationResponse:
        """Create an error LLM operation response."""
        return LLMOperationResponse(
            operation_type=operation_type,
            category=category,
            success=False,
            content="",
            grounding_evidence=[],
            metadata=LLMResponseMetadata(
                provider="none",
                model="none",
                usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                latency_ms=0.0,
                request_id=request_id,
                grounding_sources=[],
                raw_response={},
            ),
            error=LLMError(
                error_type="execution_error",
                message=error_message,
                retriable=True,
            ),
            explanation=f"Error during operation: {error_message}",
            suggestions=[
                "Check provider configuration",
                "Verify operation parameters",
                "Ensure deterministic artifacts are available",
            ],
        )

    def _create_validated_response(
        self,
        operation_type: LLMOperationType,
        category: LLMOperationCategory,
        prompt: str,
        response: Any,
        context: LLMContext,
        request_id: Optional[str],
        validation_result: Any,
    ) -> LLMOperationResponse:
        """Create a response with validation warnings."""
        # Create response with content but mark as validated with warnings
        from app.llm.guardrails import GroundingGuardrails

        grounding_sources = []
        if context.architecture_data and "components" in context.architecture_data:
            for comp in context.architecture_data["components"]:
                if comp.get("id"):
                    grounding_sources.append(
                        GroundingSource(
                            source_type=LLMContextSource.ARCHITECTURE,
                            artifact_id=f"component:{comp['id']}",
                            description=f"Component: {comp.get('id', '')}",
                            confidence=1.0,
                            evidence=[f"Layer: {comp.get('layer', '')}"],
                        )
                    )

        metadata = LLMResponseMetadata(
            provider=response.provider,
            model=response.model,
            usage=response.usage or LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=response.latency_ms or 0.0,
            request_id=request_id,
            grounding_sources=grounding_sources,
            raw_response={},
        )

        suggestions = validation_result.suggested_fix.split(". ") if validation_result.suggested_fix else []
        suggestions = [s for s in suggestions if s]

        return LLMOperationResponse(
            operation_type=operation_type,
            category=category,
            success=True,  # Still successful, but with validation warnings
            content=response.content,
            grounding_evidence=grounding_sources,
            metadata=metadata,
            error=LLMError(
                error_type="validation_warning",
                message=validation_result.message,
                details=validation_result.evidence,
                retriable=False,
            ),
            explanation=f"Response generated with validation warnings: {validation_result.message}",
            suggestions=suggestions,
        )