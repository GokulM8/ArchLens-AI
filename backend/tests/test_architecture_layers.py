"""Unit tests for Phase 3 Architectural Layer Mapping."""

import pytest
from app.architecture.schemas import (
    ArchitectureComponent,
    ArchitecturalRole,
    ArchitecturalLayer,
)
from app.architecture.layers import LayerMapper


def test_layer_mapper_role_to_layer():
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.ROUTE) == ArchitecturalLayer.PRESENTATION
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.SERVICE) == ArchitecturalLayer.APPLICATION
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.MODEL) == ArchitecturalLayer.DOMAIN
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.REPOSITORY) == ArchitecturalLayer.DATA
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.DATABASE) == ArchitecturalLayer.INFRASTRUCTURE
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.MIDDLEWARE) == ArchitecturalLayer.CROSS_CUTTING
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.EXTERNAL_SERVICE) == ArchitecturalLayer.EXTERNAL
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.TEST) == ArchitecturalLayer.TESTING
    assert LayerMapper.get_layer_for_role(ArchitecturalRole.UNKNOWN) == ArchitecturalLayer.UNKNOWN


def test_build_layer_groups():
    components = [
        ArchitectureComponent(
            id="1", name="r", path="routes.py", role=ArchitecturalRole.ROUTE,
            layer=ArchitecturalLayer.PRESENTATION, confidence=0.9, evidence=[], alternative_roles=[]
        ),
        ArchitectureComponent(
            id="2", name="s", path="services.py", role=ArchitecturalRole.SERVICE,
            layer=ArchitecturalLayer.APPLICATION, confidence=0.8, evidence=[], alternative_roles=[]
        ),
    ]

    layer_infos = LayerMapper.build_layer_groups(components)
    assert len(layer_infos) == len(ArchitecturalLayer)

    pres_layer = next(l for l in layer_infos if l.name == ArchitecturalLayer.PRESENTATION)
    assert pres_layer.components == ["1"]

    app_layer = next(l for l in layer_infos if l.name == ArchitecturalLayer.APPLICATION)
    assert app_layer.components == ["2"]
