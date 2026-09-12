"""Tests for Phase 6.6 — LLM Service (operations, conversations, errors).

All tests use the deterministic MockLLMProvider; no real LLM request is ever
made. Async operations are driven with ``asyncio.run`` so no pytest-asyncio
plugin is required.
"""

import asyncio
from enum import Enum

import pytest

from app.llm.factory import LLMProviderFactory
from app.llm.guardrails import ValidationResult
from app.llm.service import LLMService, LLMOperation


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def service(context_builder, guardrails):
    return LLMService(LLMProviderFactory, context_builder, guardrails)


class TestOperationSuccess:
    def test_explain_architecture_success(self, service, mock_env):
        response = run(service.explain_architecture({}))
        assert response.success
        assert response.content
        assert response.metadata.provider == "mock"
        assert response.explanation

    def test_summarize_repository_success(self, service, mock_env):
        response = run(service.summarize_repository({}))
        assert response.success
        assert response.content
        assert response.metadata.provider == "mock"

    @pytest.mark.parametrize(
        "question",
        ["What is the architecture?", "How is the repo structured?"],
    )
    def test_ask_success(self, service, mock_env, question):
        response = run(service.ask(question))
        assert response.success
        assert response.content
        assert response.metadata.provider == "mock"

    @pytest.mark.parametrize(
        "method, arg",
        [
            ("explain_component", "module:app.main"),
            ("explain_risk", "high_coupling:module:app.main"),
            ("explain_recommendation", "reduce_coupling:module:app.main"),
            ("explain_impact", "module:app.main"),
            ("generate_refactoring_plan", "reduce_coupling:module:app.main"),
        ],
    )
    def test_targeted_operations_success(self, service, mock_env, method, arg):
        response = run(getattr(service, method)(arg))
        assert response.success
        assert response.content
        assert response.metadata.provider == "mock"

    def test_dependency_operation_success(self, service, mock_env):
        response = run(service.explain_dependency("module:app.main", "module:app"))
        assert response.success
        assert response.content

    def test_component_operation_has_grounding_evidence(self, service, mock_env):
        response = run(service.explain_component("module:app.main"))
        ids = [gs.artifact_id for gs in response.grounding_evidence]
        assert any("module:app.main" in i for i in ids)


class TestOperationErrors:
    def test_unconfigured_returns_clear_error(self, service, no_llm_env):
        response = run(service.explain_architecture({}))
        assert not response.success
        assert response.error is not None
        assert response.error.error_type == "configuration_error"
        assert "not configured" in response.content.lower()
        # No hardcoded model names in suggestions — the spec forbids "gpt-4o".
        for suggestion in response.suggestions:
            assert "gpt-4o" not in suggestion

    def test_unconfigured_does_not_crash_any_operation(self, service, no_llm_env):
        calls = [
            lambda s: s.ask("hello"),
            lambda s: s.explain_component("module:app.main"),
            lambda s: s.explain_dependency("module:app.main", "module:app"),
            lambda s: s.explain_risk("high_coupling:module:app.main"),
            lambda s: s.explain_recommendation("reduce_coupling:module:app.main"),
            lambda s: s.explain_impact("module:app.main"),
            lambda s: s.generate_refactoring_plan("reduce_coupling:module:app.main"),
            lambda s: s.summarize_repository({}),
        ]
        for call in calls:
            response = run(call(service))
            assert not response.success
            assert response.error.error_type == "configuration_error"

    def test_unknown_operation(self, service, mock_env):
        class MadeUpOp(str, Enum):
            NOT_A_REAL_OP = "not_a_real_operation"

        response = run(service.execute_operation(MadeUpOp.NOT_A_REAL_OP, {}))
        assert not response.success
        assert response.error.error_type == "invalid_operation"

    def test_missing_question_returns_error(self, service, mock_env):
        response = run(service.ask(""))
        assert not response.success
        assert "question" in response.error.message.lower()

    def test_handler_exception_wrapped(self, service, mock_env):
        async def boom(*args, **kwargs):
            raise RuntimeError("boom")

        service._operation_handlers[LLMOperation.ARCHITECTURE_QA] = boom
        response = run(service.ask("What is this?"))
        assert not response.success
        assert response.error.error_type == "execution_error"
        assert "boom" in response.content

    def test_unknown_risk_id_returns_structured_error(self, service, mock_env):
        response = run(service.explain_risk("no_such_risk"))
        assert not response.success
        assert response.error.error_type == "invalid_target"
        assert "No risk found" in response.error.message

    def test_unknown_recommendation_id_returns_structured_error(self, service, mock_env):
        response = run(service.explain_recommendation("no_such_recommendation"))
        assert not response.success
        assert response.error.error_type == "invalid_target"

    def test_dependency_without_relationship_returns_structured_error(self, service, mock_env):
        response = run(service.explain_dependency("module:app", "module:nope"))
        assert not response.success
        assert response.error.error_type == "invalid_target"


class TestProviderConfig:
    def test_model_defaults_from_env_never_hardcoded(self, service, mock_env):
        # mock_env deletes ARCHLENS_LLM_MODEL, so the default must be empty —
        # never a hardcoded default model.
        config = service._get_provider_config_for_operation(
            LLMOperation.ARCHITECTURE_EXPLANATION, {}, None
        )
        assert "gpt-4o" not in config["model"]
        assert config["temperature"] == 0.7

    def test_request_model_override(self, service, mock_env):
        config = service._get_provider_config_for_operation(
            LLMOperation.ARCHITECTURE_QA, {"model": "custom-model", "max_tokens": 512}, None
        )
        assert config["model"] == "custom-model"
        assert config["max_tokens"] == 512

    def test_system_prompt_included(self, service, mock_env):
        config = service._get_provider_config_for_operation(
            LLMOperation.ARCHITECTURE_EXPLANATION, {}, None
        )
        assert "ArchLens" in config["system_prompt"]


class TestGuardrailInteractions:
    def test_grounding_violation_is_validated_response(self, service, mock_env, monkeypatch):
        def invalid(content):
            return ValidationResult(
                is_valid=False,
                message="LLM output references unverified repository facts",
                flags=["unknown_component"],
                suggested_fix="Do not invent files.",
            )

        monkeypatch.setattr(service.guardrails, "validate_repository_facts", invalid)
        response = run(service.ask("Describe the repo"))
        # The operation still completes, but carries a validation warning.
        assert response.success
        assert response.error is not None
        assert response.error.error_type == "validation_warning"


class TestConversations:
    def test_create_and_get_conversation(self, service):
        conv = service.create_conversation(repository="sample_repo")
        assert conv.id
        assert conv.repository == "sample_repo"
        assert conv.messages == []
        assert service.get_conversation(conv.id) is conv

    def test_create_with_explicit_id(self, service):
        conv = service.create_conversation(repository="sample_repo", conversation_id="c-1")
        assert conv.id == "c-1"

    def test_get_missing_conversation(self, service):
        assert service.get_conversation("nope") is None

    def test_list_conversations_and_filter(self, service):
        service.create_conversation(repository="repo-a")
        service.create_conversation(repository="repo-b")
        assert len(service.list_conversations()) == 2
        assert len(service.list_conversations(repository="repo-a")) == 1

    def test_delete_conversation(self, service):
        conv = service.create_conversation(repository="repo-a")
        assert service.delete_conversation(conv.id) is True
        assert service.get_conversation(conv.id) is None
        assert service.delete_conversation(conv.id) is False

    def test_append_message(self, service):
        conv = service.create_conversation(repository="repo-a")
        msg = service.append_message(conv.id, "user", "Hello", operation_id="ask")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert conv.messages[-1] is msg

    def test_append_message_missing_conversation(self, service):
        assert service.append_message("missing", "user", "hi") is None

    def test_multi_turn_records_user_and_assistant(self, service, mock_env):
        conv = service.create_conversation(repository="sample_repo")
        run(service.ask("What is the architecture?", conversation_id=conv.id))
        assert len(conv.messages) == 2
        assert [m.role for m in conv.messages] == ["user", "assistant"]
        assert "What is the architecture?" in conv.messages[0].content

    def test_repeated_turns_accumulate_history(self, service, mock_env):
        conv = service.create_conversation(repository="sample_repo")
        for _ in range(3):
            run(service.ask("Explain the layout", conversation_id=conv.id))
        assert len(conv.messages) == 6
        assert service._format_conversation_history(conv).count("assistant:") == 3

    def test_history_injection_into_provider_config(self, service, mock_env):
        conv = service.create_conversation(repository="sample_repo")
        run(service.ask("First question", conversation_id=conv.id))
        config = service._inject_conversation_history({}, conv.id)
        assert "CONVERSATION HISTORY" in config["_conversation_history"]
        assert "assistant:" in config["_conversation_history"]

    def test_no_conversation_no_history(self, service):
        config = service._inject_conversation_history({}, None)
        assert config["_conversation_history"] == ""

    def test_max_history_turns_trims(self, service):
        conv = service.create_conversation(repository="repo-a", max_history_turns=1)
        service.append_message(conv.id, "user", "q1")
        service.append_message(conv.id, "assistant", "a1")
        service.append_message(conv.id, "user", "q2")
        service.append_message(conv.id, "assistant", "a2")
        service.append_message(conv.id, "user", "q3")
        service.append_message(conv.id, "assistant", "a3")
        # max_history_turns=1 → only the last 2 messages survive.
        assert len(conv.messages) == 2
        assert conv.messages[0].content == "q3"