"""Deterministic rule-based component classifier for ArchLens AI Phase 3.

Evaluates 10 structural & graph signals to infer architectural roles with evidence and confidence scores.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple, Optional, Any
import networkx as nx

from app.models.schemas import AnalysisResult, ModuleInfo, FileInfo, ImportType
from app.architecture.schemas import (
    ArchitecturalRole,
    Evidence,
    EvidenceType,
    ArchitectureComponent,
    ArchitecturalLayer,
)
from app.architecture.evidence import (
    RoleEvidenceAccumulator,
    WEIGHT_STRONG,
    WEIGHT_MODERATE,
    WEIGHT_WEAK,
    WEIGHT_CONTRADICTORY,
)


class ArchitectureClassifier:
    """Classifies repository modules/files into architectural roles deterministically."""

    # Priority order when choosing primary role among candidate matches
    ROLE_PRECEDENCE: List[ArchitecturalRole] = [
        ArchitecturalRole.TEST,
        ArchitecturalRole.ROUTE,
        ArchitecturalRole.MIDDLEWARE,
        ArchitecturalRole.AUTHENTICATION,
        ArchitecturalRole.DATABASE,
        ArchitecturalRole.REPOSITORY,
        ArchitecturalRole.MODEL,
        ArchitecturalRole.SERVICE,
        ArchitecturalRole.ML,
        ArchitecturalRole.CONFIGURATION,
        ArchitecturalRole.UTILITY,
        ArchitecturalRole.EXTERNAL_SERVICE,
        ArchitecturalRole.UNKNOWN,
    ]

    def __init__(self, analysis: AnalysisResult, graph: nx.MultiDiGraph):
        self.analysis = analysis
        self.graph = graph

        # Indexes for fast lookup
        self.module_map: Dict[str, ModuleInfo] = {m.id: m for m in analysis.modules}
        self.file_map: Dict[str, FileInfo] = {f.path: f for f in analysis.files}
        self.class_map = {c.id: c for c in analysis.classes}
        self.function_map = {fn.id: fn for fn in analysis.functions}
        self.route_map = {r.function_id: r for r in analysis.routes}

        # Build incoming IMPORTS mapping (target_module -> set of source_modules)
        self.imported_by_map: Dict[str, Set[str]] = {}
        for u, v, data in graph.edges(data=True):
            if data.get("type") == "IMPORTS":
                self.imported_by_map.setdefault(v, set()).add(u)

    def classify_all(self) -> List[ArchitectureComponent]:
        """Classify all modules in the repository."""
        components: List[ArchitectureComponent] = []

        # If no modules are found (e.g. empty repo), return empty list
        for module in self.analysis.modules:
            comp = self.classify_module(module)
            components.append(comp)

        return components

    def classify_module(self, module: ModuleInfo) -> ArchitectureComponent:
        """Classify a single module into an architectural component."""
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator] = {
            role: RoleEvidenceAccumulator(role, base_confidence=0.10 if role == ArchitecturalRole.UNKNOWN else 0.0)
            for role in ArchitecturalRole
        }

        # Collect evidence across 10 signals
        self._evaluate_path_signal(module, accumulators)
        self._evaluate_module_name_signal(module, accumulators)
        self._evaluate_imports_signal(module, accumulators)
        self._evaluate_imported_by_signal(module, accumulators)
        self._evaluate_classes_signal(module, accumulators)
        self._evaluate_functions_signal(module, accumulators)
        self._evaluate_decorators_and_routes_signal(module, accumulators)
        self._evaluate_graph_signal(module, accumulators)

        # Determine primary and alternative roles
        role_scores: List[Tuple[ArchitecturalRole, float, List[Evidence]]] = []
        for role, accum in accumulators.items():
            conf = accum.calculate_confidence()
            if conf > 0.0 or role == ArchitecturalRole.UNKNOWN:
                role_scores.append((role, conf, accum.evidence_list))

        # Select primary role based on precedence and highest confidence score threshold (>= 0.30)
        primary_role = ArchitecturalRole.UNKNOWN
        primary_confidence = 0.10
        primary_evidence: List[Evidence] = []

        # Filter candidates with score >= 0.30
        candidates = [(r, c, ev) for r, c, ev in role_scores if c >= 0.30 and r != ArchitecturalRole.UNKNOWN]

        if candidates:
            # Sort candidates by confidence descending, then by priority index ascending
            candidates.sort(key=lambda item: (-item[1], self.ROLE_PRECEDENCE.index(item[0])))
            primary_role, primary_confidence, primary_evidence = candidates[0]
        else:
            # Check unknown accumulator
            unkn_accum = accumulators[ArchitecturalRole.UNKNOWN]
            unkn_accum.add_evidence(
                EvidenceType.STRUCTURE,
                "Insufficient structural or graph evidence to assign a specific role",
                WEIGHT_WEAK
            )
            primary_confidence = unkn_accum.calculate_confidence()
            primary_evidence = unkn_accum.evidence_list

        # Gather alternative roles (candidates with confidence >= 0.25 excluding primary)
        alternative_roles = [
            r for r, c, _ in role_scores
            if r != primary_role and r != ArchitecturalRole.UNKNOWN and c >= 0.25
        ]

        # Extract friendly module name from module ID (e.g. "module:app.services.user_service" -> "user_service")
        name = module.path.split("/")[-1].removesuffix(".py")
        if not name:
            name = module.path

        # Placeholder for layer mapping (assigned in layers.py)
        layer = ArchitecturalLayer.UNKNOWN

        return ArchitectureComponent(
            id=module.id,
            name=name,
            path=module.path,
            role=primary_role,
            layer=layer,
            confidence=primary_confidence,
            evidence=primary_evidence,
            alternative_roles=alternative_roles,
        )

    def _evaluate_path_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        path_lower = module.path.lower()
        parts = path_lower.split("/")

        # Test
        if "tests" in parts or "test" in parts or path_lower.startswith("test_") or "/test_" in path_lower or path_lower.endswith("_test.py"):
            accumulators[ArchitecturalRole.TEST].add_evidence(
                EvidenceType.PATH,
                f"Located in test path or filename '{module.path}'",
                WEIGHT_STRONG
            )

        # Route / Controller
        if any(p in ("routes", "controllers", "endpoints", "api") for p in parts):
            accumulators[ArchitecturalRole.ROUTE].add_evidence(
                EvidenceType.PATH,
                f"Located under route/controller directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Service
        if any(p in ("services", "service", "use_cases", "domain_services") for p in parts):
            accumulators[ArchitecturalRole.SERVICE].add_evidence(
                EvidenceType.PATH,
                f"Located under services directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Repository
        if any(p in ("repositories", "repository", "dao", "data_access") for p in parts):
            accumulators[ArchitecturalRole.REPOSITORY].add_evidence(
                EvidenceType.PATH,
                f"Located under repository directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Model / Schema
        if any(p in ("models", "schemas", "entities", "dtos") for p in parts):
            accumulators[ArchitecturalRole.MODEL].add_evidence(
                EvidenceType.PATH,
                f"Located under models/schemas directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Middleware
        if "middleware" in parts or "middlewares" in parts:
            accumulators[ArchitecturalRole.MIDDLEWARE].add_evidence(
                EvidenceType.PATH,
                f"Located under middleware directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Auth
        if "auth" in parts or "authentication" in parts:
            accumulators[ArchitecturalRole.AUTHENTICATION].add_evidence(
                EvidenceType.PATH,
                f"Located under auth directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Utils
        if any(p in ("utils", "utilities", "helpers", "common", "shared") for p in parts):
            accumulators[ArchitecturalRole.UTILITY].add_evidence(
                EvidenceType.PATH,
                f"Located under utility directory in '{module.path}'",
                WEIGHT_STRONG
            )

        # Configuration
        if any(p in ("config", "settings", "configuration") for p in parts):
            accumulators[ArchitecturalRole.CONFIGURATION].add_evidence(
                EvidenceType.PATH,
                f"Located under config directory in '{module.path}'",
                WEIGHT_STRONG
            )

    def _evaluate_module_name_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        filename = module.path.split("/")[-1].lower()

        if filename in ("config.py", "settings.py", "configuration.py"):
            accumulators[ArchitecturalRole.CONFIGURATION].add_evidence(
                EvidenceType.MODULE_NAME,
                f"Filename '{filename}' indicates configuration module",
                WEIGHT_STRONG
            )

        if filename in ("database.py", "db.py", "session.py"):
            accumulators[ArchitecturalRole.DATABASE].add_evidence(
                EvidenceType.MODULE_NAME,
                f"Filename '{filename}' indicates database connection module",
                WEIGHT_STRONG
            )

        if filename in ("auth.py", "jwt.py", "security.py"):
            accumulators[ArchitecturalRole.AUTHENTICATION].add_evidence(
                EvidenceType.MODULE_NAME,
                f"Filename '{filename}' indicates authentication module",
                WEIGHT_MODERATE
            )

    def _evaluate_imports_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        for imp in module.imports:
            mod_imp = imp.module.lower()

            # Framework routes
            if any(fw in mod_imp for fw in ("fastapi", "flask", "starlette", "django.urls", "rest_framework")):
                accumulators[ArchitecturalRole.ROUTE].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports web framework module '{imp.module}'",
                    WEIGHT_MODERATE
                )

            # Database / ORM
            if any(db_lib in mod_imp for db_lib in ("sqlalchemy", "sqlmodel", "peewee", "tortoise", "psycopg2", "asyncpg", "pymongo", "redis")):
                accumulators[ArchitecturalRole.DATABASE].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports database / ORM library '{imp.module}'",
                    WEIGHT_MODERATE
                )

            # Models / Schemas
            if "pydantic" in mod_imp or "dataclasses" in mod_imp:
                accumulators[ArchitecturalRole.MODEL].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports model/schema library '{imp.module}'",
                    WEIGHT_MODERATE
                )

            # Auth
            if any(auth_lib in mod_imp for auth_lib in ("jwt", "jose", "passlib", "bcrypt", "oauth")):
                accumulators[ArchitecturalRole.AUTHENTICATION].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports security/authentication package '{imp.module}'",
                    WEIGHT_STRONG
                )

            # ML / Data Processing
            if any(ml_lib in mod_imp for ml_lib in ("sklearn", "torch", "tensorflow", "pandas", "numpy", "lightgbm", "xgboost", "transformers")):
                accumulators[ArchitecturalRole.ML].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports ML/data library '{imp.module}'",
                    WEIGHT_STRONG
                )

            # External Service HTTP Clients
            if any(http_lib in mod_imp for http_lib in ("httpx", "requests", "aiohttp", "boto3", "stripe", "twilio")):
                accumulators[ArchitecturalRole.EXTERNAL_SERVICE].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports HTTP client/external SDK '{imp.module}'",
                    WEIGHT_MODERATE
                )

            # Test
            if any(test_lib in mod_imp for test_lib in ("pytest", "unittest", "unittest.mock")):
                accumulators[ArchitecturalRole.TEST].add_evidence(
                    EvidenceType.IMPORTS,
                    f"Imports test framework '{imp.module}'",
                    WEIGHT_STRONG
                )

    def _evaluate_imported_by_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        importers = self.imported_by_map.get(module.id, set())
        if len(importers) >= 3:
            # Check if importers are routes or services
            importer_paths = [self.module_map[imp_id].path.lower() for imp_id in importers if imp_id in self.module_map]
            has_route_importers = any("route" in p or "controller" in p or "api" in p for p in importer_paths)

            if has_route_importers:
                accumulators[ArchitecturalRole.SERVICE].add_evidence(
                    EvidenceType.IMPORTED_BY,
                    f"Imported by {len(importers)} modules including API routes",
                    WEIGHT_MODERATE
                )
            else:
                accumulators[ArchitecturalRole.UTILITY].add_evidence(
                    EvidenceType.IMPORTED_BY,
                    f"Widely imported across {len(importers)} modules",
                    WEIGHT_WEAK
                )

    def _evaluate_classes_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        for class_id in module.classes:
            if class_id not in self.class_map:
                continue
            cls_info = self.class_map[class_id]

            # Pydantic or dataclass
            if cls_info.is_pydantic_model or cls_info.is_dataclass:
                accumulators[ArchitecturalRole.MODEL].add_evidence(
                    EvidenceType.STRUCTURE,
                    f"Contains Pydantic model or dataclass '{cls_info.name}'",
                    WEIGHT_STRONG
                )

            # Check base classes for ORM / Middleware
            bases_lower = [b.lower() for b in cls_info.bases]
            if any("base" in b or "model" in b or "declarative" in b for b in bases_lower):
                accumulators[ArchitecturalRole.MODEL].add_evidence(
                    EvidenceType.STRUCTURE,
                    f"Class '{cls_info.name}' inherits from ORM base {cls_info.bases}",
                    WEIGHT_STRONG
                )

            if any("middleware" in b for b in bases_lower):
                accumulators[ArchitecturalRole.MIDDLEWARE].add_evidence(
                    EvidenceType.STRUCTURE,
                    f"Class '{cls_info.name}' inherits from Middleware base {cls_info.bases}",
                    WEIGHT_STRONG
                )

    def _evaluate_functions_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        for func_id in module.functions:
            if func_id not in self.function_map:
                continue
            func_info = self.function_map[func_id]

            # Database functions
            if func_info.name in ("get_db", "create_db", "init_db", "get_session"):
                accumulators[ArchitecturalRole.DATABASE].add_evidence(
                    EvidenceType.STRUCTURE,
                    f"Contains database initialization function '{func_info.name}'",
                    WEIGHT_STRONG
                )

            # Auth functions
            if any(kw in func_info.name.lower() for kw in ("create_access_token", "verify_password", "get_current_user", "hash_password")):
                accumulators[ArchitecturalRole.AUTHENTICATION].add_evidence(
                    EvidenceType.STRUCTURE,
                    f"Contains authentication function '{func_info.name}'",
                    WEIGHT_STRONG
                )

    def _evaluate_decorators_and_routes_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        # Check if any route in analysis.json belongs to functions in this module
        module_func_set = set(module.functions)
        for class_id in module.classes:
            if class_id in self.class_map:
                module_func_set.update(self.class_map[class_id].methods)

        matching_routes = [r for r in self.analysis.routes if r.function_id in module_func_set]

        if matching_routes:
            accumulators[ArchitecturalRole.ROUTE].add_evidence(
                EvidenceType.ROUTE,
                f"Exposes {len(matching_routes)} API route handler(s) (e.g. {matching_routes[0].method.value} {matching_routes[0].path})",
                WEIGHT_STRONG
            )

    def _evaluate_graph_signal(
        self,
        module: ModuleInfo,
        accumulators: Dict[ArchitecturalRole, RoleEvidenceAccumulator],
    ) -> None:
        # Check graph EXPOSES edges from module functions
        if self.graph.has_node(module.id):
            out_edges = self.graph.out_edges(module.id, data=True)
            for u, v, data in out_edges:
                if data.get("type") == "EXPOSES":
                    accumulators[ArchitecturalRole.ROUTE].add_evidence(
                        EvidenceType.GRAPH,
                        f"Graph node {module.id} exposes endpoint node {v}",
                        WEIGHT_STRONG
                    )
