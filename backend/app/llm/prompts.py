"""Centralized prompts for LLM operations in ArchLens Phase 6."""

from typing import Dict, Any, Optional
class PromptManager:
    """Manages prompts for LLM operations with proper grounding and validation."""

    @staticmethod
    def get_system_prompt(operation_type: str) -> str:
        """
        Get the system prompt for a specific operation type.

        Args:
            operation_type: Type of operation

        Returns:
            System prompt string
        """
        if not operation_type:
            return PromptManager._get_default_prompt()

        system_prompts = {
            "architecture_explanation": PromptManager._get_architecture_explanation_prompt(),
            "architecture_qa": PromptManager._get_architecture_qa_prompt(),
            "component_explanation": PromptManager._get_component_explanation_prompt(),
            "dependency_explanation": PromptManager._get_dependency_explanation_prompt(),
            "risk_explanation": PromptManager._get_risk_explanation_prompt(),
            "recommendation_explanation": PromptManager._get_recommendation_explanation_prompt(),
            "impact_reasoning": PromptManager._get_impact_reasoning_prompt(),
            "refactoring_plan": PromptManager._get_refactoring_plan_prompt(),
            "repository_summary": PromptManager._get_repository_summary_prompt(),
        }

        return system_prompts.get(operation_type, PromptManager._get_default_prompt())

    @staticmethod
    def build_operation_prompt(
        operation_type: str,
        context: Dict[str, Any],
        request: Dict[str, Any],
        target: Optional[str] = None,
    ) -> str:
        """
        Build the complete operation prompt based on operation type and context.

        Args:
            operation_type: Type of operation
            context: Context data for the operation
            request: Original request data
            target: Optional target component/risk/etc.

        Returns:
            Complete prompt string
        """
        base_prompt = PromptManager.get_system_prompt(operation_type)

        # Add context-specific information
        context_section = PromptManager._build_context_section(operation_type, context)
        request_section = PromptManager._build_request_section(operation_type, request)
        target_section = PromptManager._build_target_section(operation_type, target)

        return f"{base_prompt}\n\n{context_section}\n\n{request_section}{target_section}\n\n{PromptManager._get_completion_instruction(operation_type)}"

    @staticmethod
    def _build_context_section(operation_type: str, context: Dict[str, Any]) -> str:
        """Build the context section of the prompt."""
        if not context:
            return "No context provided."

        context_lines = ["\n=== CONTEXT ==="]

        if "repository_name" in context:
            context_lines.append(f"Repository: {context['repository_name']}")

        if "repository" in context:
            repo_info = context["repository"]
            context_lines.append(f"Repository: {repo_info}")

        # Add operation-specific context
        if operation_type in ["component_explanation", "dependency_explanation", "risk_explanation",
                            "recommendation_explanation", "impact_reasoning"]:
            if "component" in context:
                comp = context["component"]
                context_lines.append(f"\nComponent: {comp.get('id', 'Unknown')}")
                context_lines.append(f"Role: {comp.get('role', 'Unknown')}")
                context_lines.append(f"Layer: {comp.get('layer', 'Unknown')}")

            if "dependencies" in context:
                deps = context["dependencies"]
                context_lines.append(f"\nDependencies: {', '.join(deps) if deps else 'None'}")

            if "health_findings" in context:
                findings = context["health_findings"]
                if findings:
                    context_lines.append(f"\nHealth Findings: {len(findings)} found")
                    for finding in findings[:3]:  # Limit to top 3
                        context_lines.append(f"- {finding['type']}: {finding['message'][:100]}...")

            if "recommendations" in context:
                recs = context["recommendations"]
                if recs:
                    context_lines.append(f"\nRecommendations: {len(recs)} found")
                    for rec in recs[:3]:  # Limit to top 3
                        context_lines.append(f"- {rec['type']}: {rec['reason'][:100]}...")

        if "architecture_data" in context:
            arch = context["architecture_data"]
            if "components" in arch:
                context_lines.append(f"\nArchitecture Components: {len(arch['components'])}")

        if "graph_data" in context:
            graph = context["graph_data"]
            if "edges" in graph:
                context_lines.append(f"\nGraph Relationships: {len(graph['edges'])}")

        return "\n".join(context_lines)

    @staticmethod
    def _build_request_section(operation_type: str, request: Dict[str, Any]) -> str:
        """Build the request section of the prompt."""
        request_lines = ["\n=== REQUEST ==="]

        if "query" in request:
            request_lines.append(f"Question/Query: {request['query']}")

        if "target" in request:
            request_lines.append(f"Target: {request['target']}")

        if "focus" in request:
            request_lines.append(f"Focus: {request['focus']}")

        if "depth" in request:
            request_lines.append(f"Depth: {request['depth']}")

        if "format" in request:
            request_lines.append(f"Format: {request['format']}")

        return "\n".join(request_lines)

    @staticmethod
    def _build_target_section(operation_type: str, target: str = None) -> str:
        """Build the target section of the prompt."""
        if not target:
            return ""

        target_lines = ["\n=== TARGET ==="]
        target_lines.append(f"Target: {target}")
        return "\n".join(target_lines)

    @staticmethod
    def _get_completion_instruction(operation_type: str) -> str:
        """Get completion instruction based on operation type."""
        instructions = {
            "architecture_explanation": "\nPlease provide a comprehensive explanation of the repository architecture based on the above context and your knowledge of software architecture patterns.",
            "architecture_qa": "\nPlease answer the question based on the above context and your knowledge.",
            "component_explanation": "\nPlease provide a detailed explanation of the component based on the above context and its architecture role.",
            "dependency_explanation": "\nPlease explain the dependency relationship based on the above context and dependency patterns.",
            "risk_explanation": "\nPlease explain the risk based on the above context and risk assessment patterns.",
            "recommendation_explanation": "\nPlease explain the recommendation based on the above context and evolution patterns.",
            "impact_reasoning": "\nPlease analyze the impact based on the above context and architectural impact patterns.",
            "refactoring_plan": "\nPlease create a structured refactoring plan based on the above context and architectural best practices.",
            "repository_summary": "\nPlease create a comprehensive repository summary based on the above context and developer documentation patterns.",
        }

        return instructions.get(operation_type, "\nPlease provide your response based on the above context.")

    # System prompt templates

    @staticmethod
    def _get_architecture_explanation_prompt() -> str:
        return """
You are ArchLens Architecture Copilot.

Provide a comprehensive explanation of the repository architecture based on the supplied
ArchLens analysis artifacts.

Focus on:
1. High-level structure and organization
2. Major architectural layers and their purposes
3. Key components and their roles
4. Entry points and interfaces
5. Architectural patterns and styles
6. Health concerns and improvement areas
7. Evolution opportunities

IMPORTANT GUIDELINES:
- Use ONLY the information provided in the context
- Ground all facts in the deterministic artifacts
- Distinguish between verified facts and reasoning
- Be explicit about information gaps
- DO NOT invent files, modules, classes, functions, or relationships
- If evidence is insufficient, state so explicitly
- Use context from the relevant artifacts
- Keep explanations clear and actionable for developers
"""

    @staticmethod
    def _get_architecture_qa_prompt() -> str:
        return """
You are ArchLens Architecture Copilot.

Answer questions about the repository architecture based on the supplied
ArchLens analysis artifacts.

Answer guidelines:
1. Answer ONLY based on the supplied context
2. Ground all facts in the deterministic artifacts
3. Distinguish between:
   - Verified facts from deterministic analysis
   - Interpretations and reasoning from deterministic artifacts
   - LLM-generated explanations and suggestions
4. If you don't have enough information from the artifacts, explicitly state so
5. Be clear about what information is missing vs. what is known
6. Use context from the relevant artifacts
7. Keep answers clear and actionable

CRITICAL RULE: DO NOT guess or invent information not present in the context.
"""

    @staticmethod
    def _get_component_explanation_prompt() -> str:
        return """
You are ArchLens Architecture Copilot specializing in component analysis.

Explain the component in detail based on the supplied ArchLens analysis artifacts.

Include:
- Component role, layer, and purpose
- Responsibilities and functionality
- Dependencies and dependents
- Health status and risks
- Evolution recommendations
- Impact analysis
- Architectural significance

IMPORTANT:
- Use ONLY the information provided in the context
- Ground all claims in the deterministic artifacts
- Distinguish between deterministic findings and LLM explanations
- DO NOT override deterministic ArchLens findings
- Be explicit about evidence for each claim
"""

    @staticmethod
    def _get_dependency_explanation_prompt() -> str:
        return """
You are ArchLens Architecture Copilot specializing in dependency analysis.

Explain dependencies between components based on the supplied
ArchLens analysis artifacts.

Include:
- Direct and indirect dependencies
- Dependency types and relationships
- Alternative paths and complexity
- Architectural implications
- Health and risk considerations
- Evolution recommendations

IMPORTANT:
- Use ONLY the dependency information from the context
- Ground all claims in the graph artifacts
- Distinguish between deterministic relationships and interpretations
- DO NOT claim relationships not present in the artifacts
- Be clear about path complexity and alternatives
"""

    @staticmethod
    def _get_risk_explanation_prompt() -> str:
        return """
You are ArchLens Architecture Copilot specializing in risk analysis.

Explain architectural risks based on the supplied ArchLens analysis artifacts.

Include:
- Risk type and severity
- Affected components
- Evidence and supporting data
- Architectural implications
- Recommendations for mitigation
- Context from deterministic analysis

IMPORTANT:
- Use ONLY the risk information from the context
- Ground all claims in the health artifacts
- Distinguish between deterministic findings and interpretations
- DO NOT override deterministic ArchLens findings
- Be explicit about evidence for each risk assessment
"""

    @staticmethod
    def _get_recommendation_explanation_prompt() -> str:
        return """
You are ArchLens Architecture Copilot specializing in recommendations.

Explain evolution recommendations based on the supplied ArchLens analysis artifacts.

Include:
- Recommendation type and priority
- Evidence and reasoning
- Affected components
- Implementation guidance
- Expected impact
- Architectural implications

IMPORTANT:
- Use ONLY the recommendation information from the context
- Ground all claims in the evolution artifacts
- Distinguish between deterministic findings and interpretations
- DO NOT override deterministic ArchLens findings
- Be explicit about evidence for each recommendation
"""

    @staticmethod
    def _get_impact_reasoning_prompt() -> str:
        return """
You are ArchLens Architecture Copilot specializing in impact analysis.

Analyze the impact of changes on the repository architecture based on the
supplied ArchLens analysis artifacts.

Include:
- Direct and indirect effects
- Dependency chains and propagation
- Architectural implications
- Risk considerations
- Recommendations for safe changes
- Validation checkpoints

IMPORTANT:
- Use ONLY the impact information from the context
- Ground all claims in the artifacts
- Distinguish between deterministic impacts and predictions
- DO NOT claim runtime behavior not analyzed by ArchLens
- Be clear about known vs. potential impacts
"""

    @staticmethod
    def _get_refactoring_plan_prompt() -> str:
        return """
You are ArchLens Architecture Copilot specializing in refactoring planning.

Create structured refactoring plans based on the supplied ArchLens analysis artifacts.

Include:
- Step-by-step implementation sequence
- Validation checkpoints
- Risk mitigation strategies
- Dependencies and ordering
- Expected outcomes and metrics
- Architectural considerations

IMPORTANT:
- Ground the plan in the supplied ArchLens artifacts
- Use only the information provided in the context
- DO NOT claim that changes have already been made
- Validation suggestions should include:
  * Running tests
  * Re-running ArchLens analysis
  * Inspecting the graph
  * Checking health
  * Checking for cycles
  * Checking for layer violations
- Be realistic about complexity and effort
"""

    @staticmethod
    def _get_repository_summary_prompt() -> str:
        return """
You are ArchLens Architecture Copilot providing repository summaries.

Create developer-friendly summaries of repository architecture and patterns
based on the supplied ArchLens analysis artifacts.

Focus on:
- What the project does
- Overall structure
- Main entry points
- Major components
- Business logic
- Data access
- Important dependencies
- Architectural risks
- Areas worth investigating

IMPORTANT:
- Use the information from the deterministic artifacts
- Ground all claims in the verified facts
- Keep summaries clear and actionable for developers
- Focus on architectural patterns and best practices
- DO NOT include speculative or unsupported claims
- Be explicit about information gaps
"""

    @staticmethod
    def _get_default_prompt() -> str:
        return """
You are ArchLens Architecture Copilot.

Provide architectural explanations based on deterministic analysis artifacts.
Use only verified facts from the supplied context.
Distinguish between facts, deterministic interpretations, and LLM reasoning.
Use the context provided to answer questions accurately and completely.
"""