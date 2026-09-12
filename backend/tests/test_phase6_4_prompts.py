"""Tests for Phase 6.4 — Prompt Manager."""

import pytest

from app.llm.prompts import PromptManager
from app.llm.schemas import LLMOperationType


ALL_OPERATIONS = [
    "architecture_explanation",
    "architecture_qa",
    "component_explanation",
    "dependency_explanation",
    "risk_explanation",
    "recommendation_explanation",
    "impact_reasoning",
    "refactoring_plan",
    "repository_summary",
]


class TestSystemPrompts:
    @pytest.mark.parametrize("operation", ALL_OPERATIONS)
    def test_every_operation_has_nonempty_system_prompt(self, operation):
        prompt = PromptManager.get_system_prompt(operation)
        assert prompt
        assert "ArchLens" in prompt

    @pytest.mark.parametrize("operation", ALL_OPERATIONS)
    def test_every_prompt_grounds_in_artifacts(self, operation):
        prompt = PromptManager.get_system_prompt(operation)
        lower = prompt.lower()
        assert ("only" in lower or "ground" in lower or "do not" in lower)

    def test_unknown_operation_falls_back_to_default(self):
        prompt = PromptManager.get_system_prompt("not_a_real_operation")
        assert prompt
        assert prompt == PromptManager._get_default_prompt()

    def test_empty_operation_falls_back_to_default(self):
        assert PromptManager.get_system_prompt("") == PromptManager._get_default_prompt()
        assert PromptManager.get_system_prompt(None) == PromptManager._get_default_prompt()

    def test_enum_values_all_resolve(self):
        for value in LLMOperationType:
            assert PromptManager.get_system_prompt(value.value)


class TestBuildOperationPrompt:
    def test_build_architecture_prompt_includes_context(self):
        prompt = PromptManager.build_operation_prompt(
            "architecture_explanation",
            {"repository": "sample_repo", "component_count": 5},
            {"query": "What is the layout?"},
        )
        assert "sample_repo" in prompt
        assert "What is the layout?" in prompt
        assert "=== CONTEXT ===" in prompt
        assert "=== REQUEST ===" in prompt

    def test_build_prompt_with_target(self):
        prompt = PromptManager.build_operation_prompt(
            "component_explanation",
            {"component": {"id": "module:app.main", "role": "entry_point"}},
            {},
            target="module:app.main",
        )
        assert "=== TARGET ===" in prompt
        assert "module:app.main" in prompt
        assert "entry_point" in prompt

    def test_no_context(self):
        prompt = PromptManager.build_operation_prompt("architecture_qa", {}, {"query": "Q"})
        assert "No context provided." in prompt

    def test_context_with_architecture_data(self):
        prompt = PromptManager.build_operation_prompt(
            "architecture_explanation",
            {"architecture_data": {"components": [{"id": "m1"}]}},
            {},
        )
        assert "Architecture Components: 1" in prompt

    def test_dependency_context_shows_deps(self):
        prompt = PromptManager.build_operation_prompt(
            "dependency_explanation",
            {"dependencies": ["module:a", "module:b"]},
            {},
        )
        assert "module:a, module:b" in prompt

    def test_health_findings_limited_to_top_three(self):
        findings = [
            {"type": f"t{i}", "message": "msg" * 60}
            for i in range(10)
        ]
        prompt = PromptManager.build_operation_prompt(
            "risk_explanation",
            {"health_findings": findings},
            {},
        )
        # The "Health Findings: 10 found" line indicates the raw count was
        # available, while only 3 rendered entries appear.
        assert "Health Findings: 10 found" in prompt
        assert prompt.count("- t0:") == 1 and prompt.count("- t1:") == 1 and prompt.count("- t2:") == 1
        assert "- t3:" not in prompt

    def test_completion_instruction_present(self):
        prompt = PromptManager.build_operation_prompt("architecture_explanation", {}, {})
        assert "comprehensive explanation" in prompt


class TestOperationTypes:
    @pytest.mark.parametrize(
        "operation, keyword",
        [
            ("architecture_explanation", "comprehensive"),
            ("architecture_qa", "question"),
            ("component_explanation", "component"),
            ("dependency_explanation", "depend"),
            ("risk_explanation", "risk"),
            ("recommendation_explanation", "recommend"),
            ("impact_reasoning", "impact"),
            ("refactoring_plan", "refactor"),
            ("repository_summary", "summar"),
        ],
    )
    def test_distinct_completion_instructions(self, operation, keyword):
        instruction = PromptManager._get_completion_instruction(operation)
        assert keyword.lower() in instruction.lower()