"""Unit tests for Phase 3 Evidence Model and Score Calculator."""

import pytest
from app.architecture.schemas import ArchitecturalRole, EvidenceType
from app.architecture.evidence import (
    RoleEvidenceAccumulator,
    WEIGHT_STRONG,
    WEIGHT_MODERATE,
    WEIGHT_WEAK,
    WEIGHT_CONTRADICTORY,
)


def test_evidence_accumulator_clamping():
    acc = RoleEvidenceAccumulator(ArchitecturalRole.ROUTE, base_confidence=0.20)
    acc.add_evidence(EvidenceType.DECORATOR, "FastAPI route decorator", WEIGHT_STRONG)
    acc.add_evidence(EvidenceType.PATH, "File in routes/", WEIGHT_MODERATE)
    acc.add_evidence(EvidenceType.IMPORTS, "Imports fastapi", WEIGHT_STRONG)
    acc.add_evidence(EvidenceType.STRUCTURE, "Has route functions", WEIGHT_STRONG)

    # 0.20 + 0.30 + 0.20 + 0.30 + 0.30 = 1.30 -> clamped to 1.0
    assert acc.calculate_confidence() == 1.00


def test_evidence_accumulator_negative_weights():
    acc = RoleEvidenceAccumulator(ArchitecturalRole.SERVICE, base_confidence=0.30)
    acc.add_evidence(EvidenceType.PATH, "Path in utils/", WEIGHT_CONTRADICTORY)

    # 0.30 - 0.15 = 0.15
    assert acc.calculate_confidence() == 0.15


def test_evidence_accumulator_no_evidence():
    acc = RoleEvidenceAccumulator(ArchitecturalRole.UNKNOWN, base_confidence=0.10)
    assert acc.calculate_confidence() == 0.10
