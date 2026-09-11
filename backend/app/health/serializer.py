"""Serialization utilities for Phase 4 Health Results."""

import json
from typing import Dict, Any

from app.health.schemas import HealthResult


class HealthSerializer:
    """Serializes HealthResult to JSON."""

    @staticmethod
    def to_json(result: HealthResult) -> Dict[str, Any]:
        """Convert HealthResult to JSON dictionary."""
        return result.model_dump(mode="json")

    @staticmethod
    def to_json_string(result: HealthResult, indent: int = 2) -> str:
        """Convert HealthResult to formatted JSON string."""
        return json.dumps(result.model_dump(mode="json"), indent=indent, sort_keys=False)

    @staticmethod
    def save_to_file(result: HealthResult, file_path: str, indent: int = 2) -> None:
        """Save HealthResult to a JSON file."""
        json_str = HealthSerializer.to_json_string(result, indent=indent)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)

    @staticmethod
    def load_from_file(file_path: str) -> HealthResult:
        """Load HealthResult from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return HealthResult.model_validate(data)
