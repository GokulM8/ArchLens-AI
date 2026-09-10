"""Serialization utilities for ArchLens AI Phase 3 Architecture Result.

Converts ArchitectureResult to and from JSON dictionary and JSON files.
"""

from __future__ import annotations

import json
from typing import Dict, Any
from app.architecture.schemas import ArchitectureResult, ArchitectureSummary


class ArchitectureSerializer:
    """Handles serialization and deserialization of ArchitectureResult."""

    @staticmethod
    def to_json(result: ArchitectureResult) -> Dict[str, Any]:
        """Convert ArchitectureResult to JSON dictionary."""
        return result.model_dump(mode="json")

    @staticmethod
    def to_json_string(result: ArchitectureResult, indent: int = 2) -> str:
        """Convert ArchitectureResult to formatted JSON string."""
        return json.dumps(result.model_dump(mode="json"), indent=indent, sort_keys=False)

    @staticmethod
    def save_to_file(result: ArchitectureResult, file_path: str, indent: int = 2) -> None:
        """Save ArchitectureResult to a JSON file."""
        json_str = ArchitectureSerializer.to_json_string(result, indent=indent)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)

    @staticmethod
    def load_from_file(file_path: str) -> ArchitectureResult:
        """Load ArchitectureResult from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ArchitectureResult.model_validate(data)

    @staticmethod
    def get_summary(result: ArchitectureResult) -> ArchitectureSummary:
        """Extract summary from ArchitectureResult."""
        return result.summary
