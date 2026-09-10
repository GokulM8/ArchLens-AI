"""Main analyzer orchestrator — coordinates all analysis components.

This is the primary entry point for repository analysis. It orchestrates:
1. Repository scanning (file discovery)
2. AST parsing (per-file code extraction)
3. Import classification (internal vs external vs stdlib)
4. Dependency extraction (requirements.txt, pyproject.toml)
5. Relationship graph construction
6. Final JSON output generation

The analyzer produces analysis.json — a complete structured representation
of the repository's code structure.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from app.analyzers.scanner import scan_repository, ScannedFile
from app.analyzers.python.ast_parser import parse_python_file
from app.analyzers.python.import_classifier import ImportClassifier
from app.analyzers.config.requirements_parser import parse_dependency_file
from app.models.schemas import (
    AnalysisResult,
    RepositoryMetadata,
    FileInfo,
    ModuleInfo,
    ClassInfo,
    FunctionInfo,
    RouteInfo,
    ExternalDependency,
    ImportInfo,
    ImportType,
    Relationship,
    RelationshipType,
    AnalysisStatistics,
    Parameter,
    Decorator,
    HTTPMethod,
    Framework,
)


class RepositoryAnalyzer:
    """Orchestrates complete repository analysis."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.root_str = str(self.root_path)

    def analyze(self) -> AnalysisResult:
        """Run complete analysis and return structured result."""

        # Step 1: Scan repository
        scan_result = scan_repository(self.root_str)

        # Step 2: Build internal module name set for import classification
        internal_modules = self._extract_internal_module_names(scan_result.python_files)
        classifier = ImportClassifier(internal_modules)

        # Step 3: Parse each Python file
        parsed_files = []
        for scanned_file in scan_result.python_files:
            parsed = parse_python_file(scanned_file.absolute_path)
            parsed_files.append((scanned_file, parsed))

        # Step 4: Parse dependency files
        external_deps = []
        for config_file in scan_result.config_files:
            deps = parse_dependency_file(config_file.absolute_path)
            for dep in deps:
                category = classifier.categorize_package(dep.name)
                external_deps.append(ExternalDependency(
                    name=dep.name,
                    version_constraint=dep.version_constraint,
                    source_file=config_file.relative_path,
                    category=category,
                ))

        # Step 5: Build schema objects
        files_info = []
        modules_info = []
        classes_info = []
        functions_info = []
        routes_info = []
        relationships = []

        total_lines = 0

        for scanned_file, parsed_module in parsed_files:
            rel_path = scanned_file.relative_path
            total_lines += parsed_module.lines

            # File info
            module_name = self._path_to_module_name(rel_path)
            package = self._extract_package_name(module_name)

            files_info.append(FileInfo(
                path=rel_path,
                size_bytes=scanned_file.size_bytes,
                lines=parsed_module.lines,
                module_name=module_name,
                package=package,
                is_init=scanned_file.is_init,
            ))

            # Module info
            module_id = f"module:{module_name}"
            import_infos = []

            for imp in parsed_module.imports:
                import_type = classifier.classify(imp.module)
                import_infos.append(ImportInfo(
                    module=imp.module,
                    names=imp.names,
                    alias=imp.alias,
                    import_type=ImportType(import_type),
                    line=imp.line,
                    is_from_import=imp.is_from_import,
                ))

                # Create IMPORTS relationship — resolve to the exact internal
                # module being imported (deepest match within the repository).
                target_module = self._resolve_internal_import_target(
                    imp.module, internal_modules
                )
                if target_module and import_type == "internal":
                    relationships.append(Relationship(
                        source=module_id,
                        target=f"module:{target_module}",
                        type=RelationshipType.IMPORTS,
                        file=rel_path,
                        line=imp.line,
                    ))

            class_ids = []
            function_ids = []

            # Classes
            for cls in parsed_module.classes:
                class_id = f"file:{rel_path}:{cls.name}"
                class_ids.append(class_id)

                method_ids = []
                for method in cls.methods:
                    func_id = f"file:{rel_path}:{cls.name}.{method.name}"
                    method_ids.append(func_id)

                    functions_info.append(FunctionInfo(
                        id=func_id,
                        name=method.name,
                        qualified_name=f"{cls.name}.{method.name}",
                        file=rel_path,
                        line=method.line,
                        end_line=method.end_line,
                        is_async=method.is_async,
                        parameters=[Parameter(
                            name=p.name,
                            annotation=p.annotation,
                            default=p.default,
                            kind=p.kind,
                        ) for p in method.parameters],
                        return_annotation=method.return_annotation,
                        decorators=[Decorator(
                            name=d.name,
                            arguments=d.arguments,
                            line=d.line,
                        ) for d in method.decorators],
                        class_id=class_id,
                        docstring=method.docstring,
                        is_private=method.name.startswith("_") and not method.name.startswith("__"),
                        is_dunder=method.name.startswith("__") and method.name.endswith("__"),
                    ))

                classes_info.append(ClassInfo(
                    id=class_id,
                    name=cls.name,
                    file=rel_path,
                    line=cls.line,
                    end_line=cls.end_line,
                    bases=cls.bases,
                    decorators=[Decorator(
                        name=d.name,
                        arguments=d.arguments,
                        line=d.line,
                    ) for d in cls.decorators],
                    methods=method_ids,
                    docstring=cls.docstring,
                    is_dataclass=cls.is_dataclass,
                    is_pydantic_model=cls.is_pydantic_model,
                ))

                # CONTAINS relationship
                relationships.append(Relationship(
                    source=module_id,
                    target=class_id,
                    type=RelationshipType.CONTAINS,
                    file=rel_path,
                    line=cls.line,
                ))

            # Top-level functions
            for func in parsed_module.functions:
                func_id = f"file:{rel_path}:{func.name}"
                function_ids.append(func_id)

                functions_info.append(FunctionInfo(
                    id=func_id,
                    name=func.name,
                    qualified_name=func.name,
                    file=rel_path,
                    line=func.line,
                    end_line=func.end_line,
                    is_async=func.is_async,
                    parameters=[Parameter(
                        name=p.name,
                        annotation=p.annotation,
                        default=p.default,
                        kind=p.kind,
                    ) for p in func.parameters],
                    return_annotation=func.return_annotation,
                    decorators=[Decorator(
                        name=d.name,
                        arguments=d.arguments,
                        line=d.line,
                    ) for d in func.decorators],
                    class_id=None,
                    docstring=func.docstring,
                    is_private=func.name.startswith("_") and not func.name.startswith("__"),
                    is_dunder=func.name.startswith("__") and func.name.endswith("__"),
                ))

                # CONTAINS relationship
                relationships.append(Relationship(
                    source=module_id,
                    target=func_id,
                    type=RelationshipType.CONTAINS,
                    file=rel_path,
                    line=func.line,
                ))

            # Routes
            for route in parsed_module.routes:
                func_id = f"file:{rel_path}:{route.function_name}"

                routes_info.append(RouteInfo(
                    method=HTTPMethod(route.method),
                    path=route.path,
                    function_id=func_id,
                    function_name=route.function_name,
                    file=rel_path,
                    line=route.line,
                    framework=Framework(route.framework),
                    router_name=route.router_name,
                ))

                # EXPOSES relationship
                relationships.append(Relationship(
                    source=func_id,
                    target=f"route:{route.method.lower()}:{route.path}",
                    type=RelationshipType.EXPOSES,
                    file=rel_path,
                    line=route.line,
                ))

            modules_info.append(ModuleInfo(
                id=module_id,
                path=rel_path,
                package=package,
                imports=import_infos,
                classes=class_ids,
                functions=function_ids,
            ))

        # Step 6: Calculate statistics
        internal_deps = sum(
            1 for m in modules_info for imp in m.imports if imp.import_type == ImportType.INTERNAL
        )
        stdlib_imports = sum(
            1 for m in modules_info for imp in m.imports if imp.import_type == ImportType.STANDARD_LIBRARY
        )

        packages = len({f.package for f in files_info if f.package})

        statistics = AnalysisStatistics(
            total_files=scan_result.total_files,
            total_python_files=scan_result.total_python_files,
            total_lines=total_lines,
            total_classes=len(classes_info),
            total_functions=len(functions_info),
            total_routes=len(routes_info),
            total_imports=sum(len(m.imports) for m in modules_info),
            internal_dependencies=internal_deps,
            external_dependencies=len(external_deps),
            standard_library_imports=stdlib_imports,
            packages=packages,
        )

        # Step 7: Build final result
        return AnalysisResult(
            schema_version="1.0",
            repository=RepositoryMetadata(
                name=self.root_path.name,
                root_path=self.root_str,
                analyzed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                python_version=None,
                total_size_bytes=scan_result.total_python_size,
            ),
            files=files_info,
            modules=modules_info,
            classes=classes_info,
            functions=functions_info,
            routes=routes_info,
            dependencies=external_deps,
            relationships=relationships,
            statistics=statistics,
        )

    def _resolve_internal_import_target(
        self, module: str, internal_modules: set[str]
    ) -> Optional[str]:
        """Resolve an imported module to the exact internal module it targets.

        Strips relative-import dots, then walks from the full module path up
        to its parent packages, returning the deepest module that actually
        exists within the analyzed repository. Returns None when the import
        does not refer to an internal module at all.

        Examples:
            "app.services.user_service" -> "app.services.user_service"
            "app.models"                -> "app.models"  (a package)
            "app" (only)                -> "app"
        """
        if not module or module.startswith("."):
            return None

        if module in internal_modules:
            return module

        # Walk up parent packages (app.services -> app -> None)
        parts = module.split(".")
        for i in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in internal_modules:
                return candidate

        return None

    def _extract_internal_module_names(self, python_files: list[ScannedFile]) -> set[str]:
        """Build set of all internal module names for import classification."""
        names = set()
        for f in python_files:
            module_name = self._path_to_module_name(f.relative_path)
            names.add(module_name)
            # Also add parent packages
            parts = module_name.split(".")
            for i in range(1, len(parts)):
                names.add(".".join(parts[:i]))
        return names

    def _path_to_module_name(self, relative_path: str) -> str:
        """Convert file path to Python module name."""
        path = Path(relative_path)
        if path.suffix == ".py":
            path = path.with_suffix("")
        parts = list(path.parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else "__main__"

    def _extract_package_name(self, module_name: str) -> Optional[str]:
        """Extract package name from module name."""
        parts = module_name.split(".")
        return parts[0] if len(parts) > 1 else None
