"""Architectural pattern detector for ArchLens AI Phase 3.

Detects macro architectural patterns like Service-Repository, Layered Architecture, and MVC.
"""

from __future__ import annotations

from typing import List, Dict, Set
import networkx as nx

from app.architecture.schemas import (
    ArchitectureComponent,
    ArchitectureLayerInfo,
    ArchitecturePattern,
    ArchitecturalRole,
    ArchitecturalLayer,
)


class PatternDetector:
    """Detects broad software architecture patterns from classified components and graph."""

    def __init__(
        self,
        components: List[ArchitectureComponent],
        layers: List[ArchitectureLayerInfo],
        graph: nx.MultiDiGraph,
    ):
        self.components = components
        self.layers = layers
        self.graph = graph

        self.role_counts: Dict[ArchitecturalRole, int] = {}
        for c in components:
            self.role_counts[c.role] = self.role_counts.get(c.role, 0) + 1

    def detect_all(self) -> List[ArchitecturePattern]:
        """Detect all applicable architecture patterns."""
        patterns: List[ArchitecturePattern] = []

        # 1. Service-Repository Pattern
        srv_repo = self._detect_service_repository()
        if srv_repo:
            patterns.append(srv_repo)

        # 2. Layered Architecture
        layered = self._detect_layered_architecture()
        if layered:
            patterns.append(layered)

        # 3. API Service Architecture
        api_srv = self._detect_api_service_architecture()
        if api_srv:
            patterns.append(api_srv)

        # 4. MVC-like Architecture
        mvc = self._detect_mvc_like()
        if mvc:
            patterns.append(mvc)

        return patterns

    def _detect_service_repository(self) -> ArchitecturePattern | None:
        """Detect service-repository pattern with strict evidence requirements."""
        has_routes = self.role_counts.get(ArchitecturalRole.ROUTE, 0) > 0
        has_services = self.role_counts.get(ArchitecturalRole.SERVICE, 0) > 0
        has_repos = self.role_counts.get(ArchitecturalRole.REPOSITORY, 0) > 0
        has_models = self.role_counts.get(ArchitecturalRole.MODEL, 0) > 0

        # Service-Repository pattern requires actual Repository components
        # Do not count Models as Repositories; they are distinct concepts
        if has_repos and has_services and (has_routes or has_models):
            evidence = [
                f"Contains {self.role_counts.get(ArchitecturalRole.ROUTE, 0)} Route component(s)",
                f"Contains {self.role_counts.get(ArchitecturalRole.SERVICE, 0)} Service component(s)",
                f"Contains {self.role_counts.get(ArchitecturalRole.REPOSITORY, 0)} Repository component(s)",
            ]
            confidence = 0.90
            return ArchitecturePattern(
                name="service_repository_pattern",
                confidence=confidence,
                evidence=evidence,
                description="Separates API endpoints/routes, application business logic services, and repository pattern data access layers."
            )
        return None

    def _detect_layered_architecture(self) -> ArchitecturePattern | None:
        active_layers = {layer.name for layer in self.layers if layer.components}
        has_presentation = ArchitecturalLayer.PRESENTATION in active_layers
        has_application = ArchitecturalLayer.APPLICATION in active_layers
        has_domain_or_data = (ArchitecturalLayer.DOMAIN in active_layers) or (ArchitecturalLayer.DATA in active_layers)

        if has_presentation and (has_application or has_domain_or_data):
            evidence = [
                f"Identified separation across active layers: {sorted([l.value for l in active_layers if l != ArchitecturalLayer.UNKNOWN])}"
            ]
            return ArchitecturePattern(
                name="layered_architecture",
                confidence=0.80,
                evidence=evidence,
                description="Organizes codebase into discrete horizontal functional layers with directional dependencies."
            )
        return None

    def _detect_api_service_architecture(self) -> ArchitecturePattern | None:
        has_routes = self.role_counts.get(ArchitecturalRole.ROUTE, 0) > 0
        if has_routes:
            evidence = [
                f"Exposes {self.role_counts.get(ArchitecturalRole.ROUTE, 0)} API route component(s) providing HTTP REST service capabilities"
            ]
            return ArchitecturePattern(
                name="api_service_architecture",
                confidence=0.90,
                evidence=evidence,
                description="Web API service structure delivering HTTP/REST application endpoints."
            )
        return None

    def _detect_mvc_like(self) -> ArchitecturePattern | None:
        has_routes = self.role_counts.get(ArchitecturalRole.ROUTE, 0) > 0
        has_models = self.role_counts.get(ArchitecturalRole.MODEL, 0) > 0
        if has_routes and has_models:
            evidence = [
                "Contains Controller (Route) components and Model/Schema entity declarations"
            ]
            return ArchitecturePattern(
                name="mvc_like",
                confidence=0.75,
                evidence=evidence,
                description="Model-View-Controller style separation between endpoints/controllers and domain models."
            )
        return None
