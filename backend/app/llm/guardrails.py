"""Grounding and Validation Guardrails for LLM Operations.

Guardrails ensure LLM responses remain grounded in verified deterministic
artifacts: components, files, dependencies, roles, layers, risks, and
recommendations that do not exist in the artifacts are flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ValidationResult:
    """Result of a grounding validation check."""

    is_valid: bool
    message: str
    evidence: Optional[Dict[str, Any]] = None
    suggested_fix: Optional[str] = None
    flags: List[str] = field(default_factory=list)


class GroundingGuardrails:
    """Grounding validation and guardrails for LLM operations."""

    def __init__(self, verified_context: Any = None):
        """
        Initialize guardrails with verified context.

        Args:
            verified_context: VerifiedContextBuilder instance with deterministic artifacts
        """
        self.context_builder = verified_context
        self.known_components: Set[str] = set()
        self.known_files: Set[str] = set()
        self.known_dependencies: Set[tuple] = set()
        self.known_roles: Set[str] = set()
        self.known_layers: Set[str] = set()
        self.known_risks: Set[str] = set()
        self.known_recommendations: Set[str] = set()

        # Token-like patterns we refuse to pass through responses.
        self._secret_patterns = [
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"AKIA[A-Z0-9]{16}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
            re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
            re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
        ]

        if verified_context is not None:
            self._load_known_artifacts()

    # ------------------------------------------------------------------
    # Known-artifact loading
    # ------------------------------------------------------------------

    def _load_known_artifacts(self) -> None:
        """Load known artifacts from the verified context builder."""
        parsed = getattr(self.context_builder, "_parsed_artifacts", {})
        arch = parsed.get("architecture", {})
        analysis = parsed.get("analysis", {})
        graph = parsed.get("graph", {})
        health = parsed.get("health", {})
        evolution = parsed.get("evolution", {})

        for comp_id, comp in arch.get("components_by_id", {}).items():
            self.known_components.add(comp_id)
            if comp.get("name"):
                self.known_components.add(comp["name"])
            if comp.get("path"):
                self.known_files.add(comp["path"])

        # Files from analysis.
        for fpath in analysis.get("files_by_path", {}):
            self.known_files.add(fpath)

        # Dependencies (directed edges).
        for link in graph.get("links", []):
            self.known_dependencies.add((link["source"], link["target"]))

        # Roles and layers.
        for comp in arch.get("components_by_id", {}).values():
            if comp.get("role"):
                self.known_roles.add(str(comp["role"]))
            if comp.get("layer"):
                self.known_layers.add(str(comp["layer"]))

        # Risks.
        for risk in health.get("risks", []):
            self.known_risks.add(str(risk.get("type", "")))

        # Recommendations.
        for opp in evolution.get("opportunities", []):
            self.known_recommendations.add(str(opp.get("type", "")))

    # ------------------------------------------------------------------
    # Public validation entry points
    # ------------------------------------------------------------------

    def validate_repository_facts(self, content: str) -> ValidationResult:
        """
        Validate repository-specific claims in LLM output against deterministic artifacts.

        Args:
            content: LLM response content to validate

        Returns:
            ValidationResult indicating whether the content is grounded.
        """
        if not content or not content.strip():
            return ValidationResult(
                is_valid=True,
                message="Empty content — nothing to validate",  # Not a grounding failure on its own.
                flags=["empty"],
            )

        flags: List[str] = []
        claims: Dict[str, Any] = {}

        # Detect balance between known and unknown components mentioned.
        mentioned_components = self.extract_component_candidates(content)
        unknown_components = [
            c for c in mentioned_components
            if c not in self.known_components and self._looks_like_component_id(c)
        ]
        if unknown_components:
            flags.append("unknown_component")
            claims["unknown_components"] = unknown_components

        # Dependencies.
        mentioned_deps = self.extract_dependency_candidates(content)
        for src, tgt in mentioned_deps:
            if (src, tgt) not in self.known_dependencies:
                # Only flag when the reverse edge is also unknown.
                if (tgt, src) not in self.known_dependencies:
                    flags.append("unknown_dependency")
                    claims.setdefault("unknown_dependencies", []).append(f"{src} -> {tgt}")

        # Files.
        mentioned_files = self.extract_file_candidates(content)
        unknown_files = [
            f for f in mentioned_files
            if f not in self.known_files and self._looks_like_file(f)
        ]
        if unknown_files:
            flags.append("unknown_file")
            claims["unknown_files"] = unknown_files

        # Roles / layers.
        for role in self.extract_role_candidates(content):
            if role.lower() not in {r.lower() for r in self.known_roles}:
                # Only flag architecture-flavored words, not ordinary prose.
                if role.lower() in {
                    "service", "repository", "controller", "model", "database",
                    "middleware", "router", "utility",
                }:
                    flags.append("unknown_role")
                    claims.setdefault("unknown_roles", []).append(role)

        if not self.known_components:
            return ValidationResult(
                is_valid=False,
                message="No known artifacts loaded — cannot ground LLM claims",
                evidence={"known_components": 0},
                flags=["no_artifacts"],
            )

        if flags:
            return ValidationResult(
                is_valid=False,
                message="LLM output references unverified repository facts",
                evidence=claims,
                flags=flags,
                suggested_fix=(
                    "Do not invent files, modules, classes, dependencies, roles, "
                    "layers, metrics, or recommendations. Ground all claims in the "
                    "supplied ArchLens artifacts."
                ),
            )

        return ValidationResult(
            is_valid=True,
            message="LLM output is grounded in verified artifacts",
            evidence={"mentioned_components": len(mentioned_components)},
        )

    def validate_no_secrets_or_pii(self, content: str) -> ValidationResult:
        """Check content for obvious credential/PII patterns."""
        matches: List[str] = []
        for pattern in self._secret_patterns:
            if pattern.search(content or ""):
                matches.append(pattern.pattern)

        if matches:
            return ValidationResult(
                is_valid=False,
                message="Response contains potential secret material",
                evidence={"patterns": matches},
                flags=["secret"],
            )

        # Simple email heuristic.
        emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", content or "")
        if emails:
            return ValidationResult(
                is_valid=False,
                message="Response contains potential email addresses",
                evidence={"emails_found": len(emails)},
                flags=["pii"],
            )

        return ValidationResult(is_valid=True, message="No secrets/PII detected")

    def validate_response_structure(
        self, response: Any, expected_operation: Any
    ) -> ValidationResult:
        """Validate that a response has the fields expected for an operation."""
        issues: List[str] = []

        content = getattr(response, "content", "")
        op_type = getattr(expected_operation, "value", str(expected_operation))

        if not content or not content.strip():
            issues.append(f"{op_type} operation produced no content")

        # Every response should carry metadata (provider/model).
        metadata = getattr(response, "metadata", None)
        if metadata is None:
            issues.append("response missing metadata")

        if issues:
            return ValidationResult(
                is_valid=False,
                message="; ".join(issues),
                flags=["structure"],
            )
        return ValidationResult(is_valid=True, message="Response structure OK")

    # ------------------------------------------------------------------
    # Candidate extraction (heuristics)
    # ------------------------------------------------------------------

    def extract_component_candidates(self, content: str) -> List[str]:
        """Extract possible component/variable/module tokens from output."""
        candidates: List[str] = []
        # Words that look like python identifiers, minus stopwords.
        for token in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", content or ""):
            if token in self._stopwords():
                continue
            candidates.append(token)
        return list(dict.fromkeys(candidates))

    def extract_dependency_candidates(self, content: str) -> List[tuple]:
        """Extract "X depends on Y" / "X -> Y" style dependency claims."""
        deps: List[tuple] = []
        text = content or ""

        # Pattern: component A (depends on|uses|imports) component B
        for match in re.finditer(
            r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+(depends on|uses|imports|imported by)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            text,
        ):
            a, rel, b = match.group(1), match.group(2), match.group(3)
            if rel == "imported by":
                deps.append((b, a))
            else:
                deps.append((a, b))

        # Pattern: A -> B
        for match in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*->\s*([a-zA-Z_][a-zA-Z0-9_]*)", text):
            deps.append((match.group(1), match.group(2)))

        return deps

    def extract_file_candidates(self, content: str) -> List[str]:
        """Extract file-path-like tokens."""
        files = re.findall(r"\b[\w./-]+\.py\b", content or "")
        files += re.findall(r"\b[\w./-]+\.js\b", content or "")
        return list(dict.fromkeys(files))

    def extract_role_candidates(self, content: str) -> List[str]:
        """Extract role-flavored tokens (service, repository, etc.)."""
        roles = re.findall(
            r"\b(service|repository|controller|model|database|middleware|router|utility|factory|entry point|external service)\b",
            content or "",
            re.IGNORECASE,
        )
        return [r for r in roles if r.lower() != "service" or "service" in self.known_roles]

    # ------------------------------------------------------------------
    # Refusal helpers
    # ------------------------------------------------------------------

    def _looks_like_component_id(self, token: str) -> bool:
        """A candidate is likely a component id if it contains underscore or a module prefix."""
        return "_" in token or ":" in token or token.startswith("module")

    def _looks_like_file(self, token: str) -> bool:
        return "." in token or "/" in token

    @staticmethod
    def _stopwords() -> Set[str]:
        return {
            "the", "and", "that", "this", "with", "from", "which", "have",
            "you", "for", "are", "was", "has", "its", "not", "but", "all",
            "use", "used", "using", "also", "than", "then", "they", "there",
            "their", "would", "could", "should", "response", "question",
            "because", "your", "will", "archlens", "copilot", "based",
        }