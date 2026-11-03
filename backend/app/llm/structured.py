"""Structured Copilot answers: JSON the model must return, validated before use.

Used only when ``LLMService(structured_output=True)``. Facts the model restates
must cite fact-sheet ids; ids that are not in the sheet are reported as
``unverified_evidence`` instead of being presented as ArchLens findings.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

from pydantic import ValidationError

from app.llm.schemas import CopilotAnswer

ANSWER_INSTRUCTIONS = (
    "Respond with a single JSON object and nothing else, with keys: "
    '"summary" (string), "verified_facts" (list of {"statement", "evidence": [fact ids]}), '
    '"interpretation" (list of strings), "recommendations" (list of strings), '
    '"insufficient_evidence" (boolean). Cite only fact ids that appear in the fact sheet; '
    "put anything you cannot cite under interpretation."
)

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class StructuredOutputError(Exception):
    """The model's output is not a valid CopilotAnswer."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def answer_json_schema() -> Dict[str, Any]:
    return CopilotAnswer.model_json_schema()


def parse_answer(text: str) -> CopilotAnswer:
    if not text or not text.strip():
        raise StructuredOutputError("The model returned an empty answer.")
    fenced = _FENCE.match(text)
    raw = fenced.group(1) if fenced else text.strip()
    try:
        data = json.loads(raw)
    except ValueError:
        raise StructuredOutputError("The model's answer is not valid JSON.")
    if not isinstance(data, dict):
        raise StructuredOutputError("The model's answer is not a JSON object.")
    try:
        return CopilotAnswer.model_validate(data)
    except ValidationError as e:
        fields = ", ".join(".".join(str(p) for p in err["loc"]) for err in e.errors())
        raise StructuredOutputError(f"The model's answer is missing or has invalid fields: {fields}.")


def check_evidence(answer: CopilotAnswer, known_ids: Iterable[str]) -> Dict[str, Any]:
    """Mark each fact verified only if every id it cites is in the fact sheet."""
    known = set(known_ids)
    facts: List[Dict[str, Any]] = []
    unverified: List[str] = []
    for fact in answer.verified_facts:
        missing = [e for e in fact.evidence if e not in known]
        unverified.extend(e for e in missing if e not in unverified)
        facts.append({"statement": fact.statement, "evidence": list(fact.evidence), "verified": not missing})
    return {
        "summary": answer.summary,
        "verified_facts": facts,
        "interpretation": list(answer.interpretation),
        "recommendations": list(answer.recommendations),
        "insufficient_evidence": answer.insufficient_evidence,
        "unverified_evidence": unverified,
    }


def render_answer(structured: Dict[str, Any]) -> str:
    """Plain-text rendering that keeps facts, interpretation and advice apart."""
    lines = [structured["summary"]]
    if structured["verified_facts"]:
        lines += ["", "Facts:"]
        for fact in structured["verified_facts"]:
            mark = "" if fact["verified"] else " (unverified)"
            lines.append(f"- {fact['statement']} [{', '.join(fact['evidence'])}]{mark}")
    if structured["interpretation"]:
        lines += ["", "Interpretation:"] + [f"- {s}" for s in structured["interpretation"]]
    if structured["recommendations"]:
        lines += ["", "Recommendations:"] + [f"- {s}" for s in structured["recommendations"]]
    if structured["insufficient_evidence"]:
        lines += ["", "The artifacts do not contain enough evidence to answer fully."]
    return "\n".join(lines)
