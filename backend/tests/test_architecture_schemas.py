"""Unit tests for Phase 3 Architecture Schemas."""

import pytest
from app.architecture.schemas import (
    ArchitecturalRole,
    ArchitecturalLayer,
    EvidenceType,
    Evidence,
    ArchitectureComponent,
    ArchitectureLayerInfo,
    EntryPoint,
    ArchitecturePattern,
    ArchitectureRelationship,
    ArchitectureSummary,
    ArchitectureResult,
)


def test_architectural_role_enum_values():
    assert ArchitecturalRole.ROUTE.value == "route"
    assert ArchitecturalRole.SERVICE.value == "service"
    assert ArchitecturalRole.REPOSITORY.value == "repository"
    assert ArchitecturalRole.MODEL.value == "model"
    assert ArchitecturalRole.DATABASE.value == "database"
    assert ArchitecturalRole.UTILITY.value == "utility"
    assert ArchitecturalRole.CONFIGURATION.value == "configuration"
    assert ArchitecturalRole.MIDDLEWARE.value == "middleware"
    assert ArchitecturalRole.AUTHENTICATION.value == "authentication"
    assert ArchitecturalRole.EXTERNAL_SERVICE.value == "external_service"
    assert ArchitecturalRole.ML.value == "ml"
    assert ArchitecturalRole.TEST.value == "test"
    assert ArchitecturalRole.UNKNOWN.value == "unknown"


def test_architectural_layer_enum_values():
    assert ArchitecturalLayer.PRESENTATION.value == "Presentation"
    assert ArchitecturalLayer.APPLICATION.value == "Application"
    assert ArchitecturalLayer.DOMAIN.value == "Domain"
    assert ArchitecturalLayer.DATA.value == "Data"
    assert ArchitecturalLayer.INFRASTRUCTURE.value == "Infrastructure"
    assert ArchitecturalLayer.CROSS_CUTTING.value == "Cross-Cutting"
    assert ArchitecturalLayer.EXTERNAL.value == "External"
    assert ArchitecturalLayer.TESTING.value == "Testing"
    assert ArchitecturalLayer.UNKNOWN.value == "Unknown"


def test_evidence_model():
    ev = Evidence(
        type=EvidenceType.DECORATOR,
        description="FastAPI router decorator",
        weight=0.30,
        source_id="app.routes.items",
    )
    assert ev.type == EvidenceType.DECORATOR
    assert ev.weight == 0.30
    assert ev.source_id == "app.routes.items"


def test_architecture_component_model():
    comp = ArchitectureComponent(
        id="mod:app.routes",
        name="app.routes",
        path="app/routes.py",
        role=ArchitecturalRole.ROUTE,
        layer=ArchitecturalLayer.PRESENTATION,
        confidence=0.85,
        evidence=[
            Evidence(
                type=EvidenceType.PATH,
                description="Path contains routes/",
                weight=0.20,
            )
        ],
        alternative_roles=[ArchitecturalRole.UTILITY],
    )
    assert comp.id == "mod:app.routes"
    assert comp.role == ArchitecturalRole.ROUTE
    assert comp.layer == ArchitecturalLayer.PRESENTATION
    assert len(comp.evidence) == 1


def test_architecture_result_serialization():
    res = ArchitectureResult(
        schema_version="1.0",
        repository_name="test_repo",
        components=[],
        layers=[],
        entry_points=[],
        patterns=[],
        relationships=[],
        summary=ArchitectureSummary(
            component_count=0,
            roles={},
            layers={},
            entry_point_count=0,
            pattern_count=0,
        ),
    )
    dumped = res.model_dump(mode="json")
    assert dumped["schema_version"] == "1.0"
    assert dumped["repository_name"] == "test_repo"
    assert dumped["summary"]["component_count"] == 0
