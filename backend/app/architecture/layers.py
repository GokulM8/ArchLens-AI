"""Architectural layer mapping engine for ArchLens AI Phase 3.

Maps inferred ArchitecturalRole to ArchitecturalLayer and groups components.
"""

from __future__ import annotations

from typing import Dict, List
from app.architecture.schemas import (
    ArchitecturalRole,
    ArchitecturalLayer,
    ArchitectureComponent,
    ArchitectureLayerInfo,
)


ROLE_TO_LAYER_MAP: Dict[ArchitecturalRole, ArchitecturalLayer] = {
    ArchitecturalRole.ROUTE: ArchitecturalLayer.PRESENTATION,
    ArchitecturalRole.SERVICE: ArchitecturalLayer.APPLICATION,
    ArchitecturalRole.ML: ArchitecturalLayer.APPLICATION,
    ArchitecturalRole.MODEL: ArchitecturalLayer.DOMAIN,
    ArchitecturalRole.REPOSITORY: ArchitecturalLayer.DATA,
    ArchitecturalRole.DATABASE: ArchitecturalLayer.INFRASTRUCTURE,
    ArchitecturalRole.CONFIGURATION: ArchitecturalLayer.INFRASTRUCTURE,
    ArchitecturalRole.MIDDLEWARE: ArchitecturalLayer.CROSS_CUTTING,
    ArchitecturalRole.AUTHENTICATION: ArchitecturalLayer.CROSS_CUTTING,
    ArchitecturalRole.UTILITY: ArchitecturalLayer.CROSS_CUTTING,
    ArchitecturalRole.EXTERNAL_SERVICE: ArchitecturalLayer.EXTERNAL,
    ArchitecturalRole.TEST: ArchitecturalLayer.TESTING,
    ArchitecturalRole.UNKNOWN: ArchitecturalLayer.UNKNOWN,
}

LAYER_DESCRIPTIONS: Dict[ArchitecturalLayer, str] = {
    ArchitecturalLayer.PRESENTATION: "Handles HTTP API endpoints, controllers, and UI presentation logic.",
    ArchitecturalLayer.APPLICATION: "Contains application services, business use-cases, and orchestration logic.",
    ArchitecturalLayer.DOMAIN: "Defines core domain entities, data models, schemas, and domain contracts.",
    ArchitecturalLayer.DATA: "Manages data persistence, repository pattern interfaces, and CRUD operations.",
    ArchitecturalLayer.INFRASTRUCTURE: "Provides database connectivity, configuration settings, and low-level drivers.",
    ArchitecturalLayer.CROSS_CUTTING: "Handles concerns spanning multiple layers such as security, auth, middleware, and helpers.",
    ArchitecturalLayer.EXTERNAL: "Interfaces with third-party APIs, HTTP clients, and external service SDKs.",
    ArchitecturalLayer.TESTING: "Contains unit tests, integration test suites, and test fixtures.",
    ArchitecturalLayer.UNKNOWN: "Unclassified components with insufficient structural or graph evidence.",
}


class LayerMapper:
    """Maps components to architectural layers and generates layer groupings."""

    @staticmethod
    def get_layer_for_role(role: ArchitecturalRole) -> ArchitecturalLayer:
        """Get the architectural layer for an architectural role."""
        return ROLE_TO_LAYER_MAP.get(role, ArchitecturalLayer.UNKNOWN)

    @staticmethod
    def map_component_layer(component: ArchitectureComponent) -> ArchitecturalLayer:
        """Get the architectural layer for a component based on its primary role."""
        return LayerMapper.get_layer_for_role(component.role)

    @staticmethod
    def build_layer_groups(components: List[ArchitectureComponent]) -> List[ArchitectureLayerInfo]:
        """Group components into layer summary structures."""
        layer_components: Dict[ArchitecturalLayer, List[str]] = {layer: [] for layer in ArchitecturalLayer}

        for comp in components:
            comp.layer = LayerMapper.map_component_layer(comp)
            layer_components[comp.layer].append(comp.id)

        layer_infos: List[ArchitectureLayerInfo] = []
        for layer in ArchitecturalLayer:
            comp_ids = layer_components[layer]
            layer_infos.append(
                ArchitectureLayerInfo(
                    name=layer,
                    components=comp_ids,
                    description=LAYER_DESCRIPTIONS[layer]
                )
            )

        return layer_infos
