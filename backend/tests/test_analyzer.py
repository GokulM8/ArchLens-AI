"""Integration tests for the full analysis pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.analyzer import RepositoryAnalyzer

# Path to the example FastAPI project (sibling of backend/)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
EXAMPLE_PROJECT = PROJECT_ROOT / "examples" / "fastapi_project"


@pytest.fixture(scope="module")
def analysis():
    """Analyze the example project once for all integration tests."""
    analyzer = RepositoryAnalyzer(str(EXAMPLE_PROJECT))
    return analyzer.analyze()


class TestRepositoryMetadata:
    """Tests for repository-level metadata."""

    def test_schema_version(self, analysis):
        assert analysis.schema_version == "1.0"

    def test_repository_name(self, analysis):
        assert analysis.repository.name == "fastapi_project"

    def test_repository_root(self, analysis):
        assert analysis.repository.root_path == str(EXAMPLE_PROJECT.resolve())

    def test_analyzed_at_timestamp(self, analysis):
        assert "T" in analysis.repository.analyzed_at

    def test_total_size_positive(self, analysis):
        assert analysis.repository.total_size_bytes > 0


class TestFileExtraction:
    """Tests for file-level extraction."""

    def test_files_present(self, analysis):
        assert len(analysis.files) > 0

    def test_expected_files(self, analysis):
        paths = {f.path for f in analysis.files}
        assert "app/main.py" in paths
        assert "app/routes/users.py" in paths
        assert "app/services/user_service.py" in paths
        assert "app/models/user.py" in paths

    def test_file_module_names(self, analysis):
        files_by_path = {f.path: f for f in analysis.files}
        assert files_by_path["app/main.py"].module_name == "app.main"
        assert files_by_path["app/services/user_service.py"].module_name == "app.services.user_service"

    def test_init_files_detected(self, analysis):
        init_files = [f for f in analysis.files if f.is_init]
        assert len(init_files) >= 4  # app, models, services, routes


class TestModuleExtraction:
    """Tests for module-level extraction."""

    def test_internal_imports_classified(self, analysis):
        modules = {m.path: m for m in analysis.modules}
        user_routes = modules["app/routes/users.py"]
        internal_imports = [
            imp for imp in user_routes.imports
            if imp.import_type.value == "internal"
        ]
        # user_service is internal
        assert any(
            imp.module == "app.services.user_service" for imp in internal_imports
        )
        assert any(
            imp.module == "app.models.user" for imp in internal_imports
        )

    def test_external_imports_classified(self, analysis):
        modules = {m.path: m for m in analysis.modules}
        user_routes = modules["app/routes/users.py"]
        external_imports = [
            imp for imp in user_routes.imports
            if imp.import_type.value == "external"
        ]
        assert any(imp.module == "fastapi" for imp in external_imports)

    def test_stdlib_imports_classified(self, analysis):
        modules = {m.path: m for m in analysis.modules}
        utils_auth = modules["app/utils/auth.py"]
        stdlib_imports = [
            imp for imp in utils_auth.imports
            if imp.import_type.value == "standard_library"
        ]
        assert any(imp.module == "hashlib" for imp in stdlib_imports)


class TestClassExtraction:
    """Tests for class-level extraction."""

    def test_classes_detected(self, analysis):
        assert len(analysis.classes) >= 10

    def test_expected_classes(self, analysis):
        names = {c.name: c for c in analysis.classes}
        assert "UserService" in names
        assert "ProductService" in names
        assert "PredictionService" in names
        assert "User" in names
        assert "Product" in names

    def test_class_inheritance(self, analysis):
        names = {c.name: c for c in analysis.classes}
        # Pydantic base models inherit BaseModel
        user_base = names["UserBase"]
        assert "BaseModel" in user_base.bases

    def test_pydantic_models_flagged(self, analysis):
        names = {c.name: c for c in analysis.classes}
        # UserBase inherits BaseModel directly; User is a SQLAlchemy model
        assert names["UserBase"].is_pydantic_model
        assert not names["User"].is_pydantic_model

    def test_class_file_tracking(self, analysis):
        names = {c.name: c for c in analysis.classes}
        assert names["UserService"].file == "app/services/user_service.py"

    def test_methods_attached(self, analysis):
        names = {c.name: c for c in analysis.classes}
        user_service = names["UserService"]
        # methods field holds stable IDs of the class's methods
        assert len(user_service.methods) > 5
        for method_id in user_service.methods:
            assert method_id.startswith("file:")
            assert "UserService" in method_id


class TestFunctionExtraction:
    """Tests for function-level extraction."""

    def test_functions_detected(self, analysis):
        assert len(analysis.functions) >= 50

    def test_async_functions(self, analysis):
        async_funcs = [f for f in analysis.functions if f.is_async]
        assert len(async_funcs) > 10

    def test_function_parameters(self, analysis):
        functions = {f.name: f for f in analysis.functions}
        auth = functions.get("authenticate_user")
        if auth:
            assert auth.is_async

    def test_class_methods_have_class_id(self, analysis):
        class_methods = [f for f in analysis.functions if f.class_id is not None]
        assert len(class_methods) > 10


class TestRouteExtraction:
    """Tests for API route detection."""

    def test_routes_detected(self, analysis):
        assert len(analysis.routes) >= 15

    def test_health_route(self, analysis):
        health = [r for r in analysis.routes if r.path == "/health"]
        assert len(health) == 1
        assert health[0].method.value == "GET"
        assert health[0].framework.value == "fastapi"
        assert health[0].function_name == "health_check"
        assert health[0].file == "app/main.py"

    def test_user_routes(self, analysis):
        user_routes = [
            r for r in analysis.routes
            if r.function_name.startswith(("create_user", "get_user", "login_user"))
        ]
        methods = {r.function_name: r.method.value for r in user_routes}
        assert methods.get("create_user") == "POST"
        assert methods.get("login_user") == "POST"
        assert methods.get("get_user") == "GET"

    def test_http_methods(self, analysis):
        methods = {r.method.value for r in analysis.routes}
        assert {"GET", "POST", "PUT", "DELETE"} <= methods


class TestDependencyExtraction:
    """Tests for external dependency extraction."""

    def test_requirements_parsed(self, analysis):
        names = {d.name.lower() for d in analysis.dependencies}
        assert "fastapi" in names
        assert "uvicorn" in names

    def test_dependency_categories(self, analysis):
        by_name = {d.name.lower(): d for d in analysis.dependencies}
        assert by_name["fastapi"].category == "Web/API"
        assert by_name["sqlalchemy"].category == "Database/ORM"


class TestRelationships:
    """Tests for relationship graph edges."""

    def test_imports_relationships(self, analysis):
        imports_edges = [
            r for r in analysis.relationships
            if r.type.value == "IMPORTS"
        ]
        assert len(imports_edges) > 5

    def test_contains_relationships(self, analysis):
        contains_edges = [
            r for r in analysis.relationships
            if r.type.value == "CONTAINS"
        ]
        assert len(contains_edges) > 10

    def test_exposes_relationships(self, analysis):
        exposes_edges = [
            r for r in analysis.relationships
            if r.type.value == "EXPOSES"
        ]
        assert len(exposes_edges) >= 15

    def test_import_relationship_modules(self, analysis):
        # routes/users.py imports services/user_service.py
        import_edges = [
            r for r in analysis.relationships
            if r.type.value == "IMPORTS"
            and r.source == "module:app.routes.users"
        ]
        targets = {r.target for r in import_edges}
        assert "module:app.services.user_service" in targets


class TestStatistics:
    """Tests for summary statistics."""

    def test_counts_consistent(self, analysis):
        assert analysis.statistics.total_python_files == len(analysis.files)
        assert analysis.statistics.total_classes == len(analysis.classes)
        assert analysis.statistics.total_functions == len(analysis.functions)
        assert analysis.statistics.total_routes == len(analysis.routes)

    def test_nonzero_counts(self, analysis):
        stats = analysis.statistics
        assert stats.total_lines > 0
        assert stats.total_imports > 0
        assert stats.internal_dependencies > 0
        assert stats.external_dependencies > 0
        assert stats.standard_library_imports > 0


class TestAnalysisJsonSerialization:
    """Tests that the result serializes to valid analysis.json."""

    def test_json_serializable(self, analysis):
        data = analysis.model_dump(mode="json")
        json.dumps(data)  # must not raise

    def test_json_top_level_keys(self, analysis):
        data = analysis.model_dump(mode="json")
        expected_keys = {
            "schema_version", "repository", "files", "modules", "classes",
            "functions", "routes", "dependencies", "relationships", "statistics",
        }
        assert set(data.keys()) == expected_keys

    def test_json_route_shape(self, analysis):
        data = analysis.model_dump(mode="json")
        route = data["routes"][0]
        expected_keys = {
            "method", "path", "function_id", "function_name",
            "file", "line", "framework", "router_name",
        }
        assert set(route.keys()) == expected_keys

    def test_stable_ids(self, analysis):
        data = analysis.model_dump(mode="json")
        for func in data["functions"]:
            assert func["id"].startswith("file:")
        for cls in data["classes"]:
            assert cls["id"].startswith("file:")


class TestSchemaValidation:
    """Verify the pydantic schema validates correctly."""

    def test_route_schema_roundtrip(self):
        from app.models.schemas import RouteInfo, HTTPMethod, Framework

        route = RouteInfo(
            method=HTTPMethod.GET,
            path="/x",
            function_id="file:x",
            function_name="x",
            file="x.py",
            line=1,
            framework=Framework.FASTAPI,
            router_name="app",
        )
        assert route.method.value == "GET"

    def test_import_type_enum(self):
        from app.models.schemas import ImportType

        assert str(ImportType.INTERNAL.value) == "internal"
        assert ImportType("external") == ImportType.EXTERNAL

    def test_relationship_type_enum(self):
        from app.models.schemas import RelationshipType

        assert RelationshipType.IMPORTS.value == "IMPORTS"
        assert RelationshipType("CALLS") == RelationshipType.CALLS