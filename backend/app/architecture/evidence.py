"""Evidence and confidence scoring models for ArchLens AI Phase 3.

Provides deterministic scoring calculations and evidence aggregation for
architectural role classification.
"""

from __future__ import annotations

from typing import List, Tuple, Dict
from app.architecture.schemas import Evidence, EvidenceType, ArchitecturalRole


# Standard evidence weights
WEIGHT_STRONG = 0.30
WEIGHT_MODERATE = 0.20
WEIGHT_WEAK = 0.10
WEIGHT_CONTRADICTORY = -0.15


class RoleEvidenceAccumulator:
    """Accumulates evidence items and calculates confidence score for a role."""

    def __init__(self, role: ArchitecturalRole, base_confidence: float = 0.0):
        self.role = role
        self.base_confidence = base_confidence
        self.evidence_list: List[Evidence] = []

    def add_evidence(
        self,
        evidence_type: EvidenceType,
        description: str,
        weight: float,
        source_id: str | None = None
    ) -> None:
        """Add a piece of evidence supporting or contradicting this role."""
        evidence = Evidence(
            type=evidence_type,
            description=description,
            weight=weight,
            source_id=source_id
        )
        self.evidence_list.append(evidence)

    def calculate_confidence(self) -> float:
        """Calculate clamped deterministic confidence score in range [0.0, 1.0]."""
        if not self.evidence_list:
            return self.base_confidence

        total = self.base_confidence + sum(ev.weight for ev in self.evidence_list)
        # Clamp between 0.0 and 1.0
        return max(0.0, min(1.0, round(total, 4)))
