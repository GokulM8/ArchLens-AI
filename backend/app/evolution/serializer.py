"""Phase 5 Evolution Result Serializer."""

import json
from pathlib import Path

from app.evolution.schemas import EvolutionResult


class EvolutionSerializer:
    """Serializes EvolutionResult to JSON."""

    @staticmethod
    def to_json_string(result: EvolutionResult) -> str:
        """Serialize result to JSON string."""
        return json.dumps(result.model_dump(mode="json"), indent=2)

    @staticmethod
    def save_to_file(result: EvolutionResult, file_path: str) -> None:
        """Save result to JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2)

    @staticmethod
    def load_from_file(file_path: str) -> EvolutionResult:
        """Load result from JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return EvolutionResult(**data)
