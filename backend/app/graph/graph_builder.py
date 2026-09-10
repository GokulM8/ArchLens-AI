"""NetworkX MultiDiGraph builder for ArchLens AI Phase 2.

Transforms AnalysisResult into a directed graph with multiple edge types,
representing code structure and relationships for further analysis.
"""

from __future__ import annotations

import networkx as nx
from typing import Dict, Set, Optional, Tuple

from app.models.schemas import (
    AnalysisResult,
    ImportType,
)


class GraphBuilder:
    """Builds a NetworkX MultiDiGraph from AnalysisResult."""

    def __init__(self, analysis_result: AnalysisResult):
        """Initialize with analysis results.

        Args:
            analysis_result: The output from Phase 1 analysis
        """
        self.analysis_result = analysis_result
        self.graph = nx.MultiDiGraph()
        self._added_containment: Set[Tuple[str, str]] = set()  # Track added containment edges

    def build(self) -> nx.MultiDiGraph:
        """Build the complete graph from analysis results.

        Returns:
            A NetworkX MultiDiGraph containing all nodes and edges
        """
        self._add_repository_node()
        self._add_directory_nodes()
        self._add_file_nodes()
        self._add_module_nodes()
        self._add_class_nodes()
        self._add_function_nodes()
        self._add_route_nodes()
        self._add_dependency_nodes()
        self._add_containment_edges()
        self._add_import_edges()
        self._add_expose_edges()
        self._add_dependency_edges()
        # CALLS and INHERITS edges would be added in a later phase
        # when we have call graph and inheritance data from deeper analysis

        return self.graph

    def _add_repository_node(self) -> None:
        """Add the repository root node."""
        repo_id = f"repository:{self.analysis_result.repository.name}"
        label = self.analysis_result.repository.name
        self.graph.add_node(
            repo_id,
            type="repository",
            label=label,
            path=self.analysis_result.repository.root_path,
        )

    def _add_directory_nodes(self) -> None:
        """Add nodes for directories containing Python files."""
        directories: Set[str] = set()
        for file_info in self.analysis_result.files:
            # Get directory path (everything before the filename)
            dir_path = "/".join(file_info.path.split("/")[:-1]) if "/" in file_info.path else ""
            if dir_path:
                directories.add(dir_path)
            # Also add intermediate directories
            parts = file_info.path.split("/")
            for i in range(1, len(parts)):
                dir_path = "/".join(parts[:i])
                directories.add(dir_path)

        for dir_path in sorted(directories):
            node_id = f"directory:{dir_path}"
            label = dir_path.split("/")[-1] if dir_path else "(root)"
            self.graph.add_node(
                node_id,
                type="directory",
                label=label,
                path=dir_path,
            )

    def _add_file_nodes(self) -> None:
        """Add nodes for each Python file."""
        for file_info in self.analysis_result.files:
            node_id = f"file:{file_info.path}"
            self.graph.add_node(
                node_id,
                type="file",
                label=file_info.path,
                path=file_info.path,
                size_bytes=file_info.size_bytes,
                lines=file_info.lines,
                module_name=file_info.module_name,
                package=file_info.package,
                is_init=file_info.is_init,
            )

    def _add_module_nodes(self) -> None:
        """Add nodes for each Python module."""
        for module_info in self.analysis_result.modules:
            node_id = module_info.id  # Already in format "module:dotted.path"
            self.graph.add_node(
                node_id,
                type="module",
                label=module_info.id.split(":")[-1],  # Just the module name part
                path=module_info.path,
                package=module_info.package,
            )

    def _add_class_nodes(self) -> None:
        """Add nodes for each class."""
        for class_info in self.analysis_result.classes:
            node_id = class_info.id  # Already in format "file:class_name"
            self.graph.add_node(
                node_id,
                type="class",
                label=class_info.name,
                file=class_info.file,
                line_start=class_info.line,
                line_end=class_info.end_line,
                bases=class_info.bases,
                is_dataclass=class_info.is_dataclass,
                is_pydantic_model=class_info.is_pydantic_model,
            )

    def _add_function_nodes(self) -> None:
        """Add nodes for each function/method."""
        for func_info in self.analysis_result.functions:
            node_id = func_info.id  # Already in format "file:qualified_name"
            self.graph.add_node(
                node_id,
                type="function",
                label=func_info.name,
                file=func_info.file,
                line_start=func_info.line,
                line_end=func_info.end_line,
                is_async=func_info.is_async,
                is_private=func_info.is_private,
                is_dunder=func_info.is_dunder,
                class_id=func_info.class_id,
            )

    def _add_route_nodes(self) -> None:
        """Add nodes for each API route."""
        for route_info in self.analysis_result.routes:
            # Route ID format: route:{method}:{path}
            node_id = f"route:{route_info.method.value.lower()}:{route_info.path}"
            self.graph.add_node(
                node_id,
                type="route",
                label=f"{route_info.method.value} {route_info.path}",
                method=route_info.method.value,
                path=route_info.path,
                function_id=route_info.function_id,
                function_name=route_info.function_name,
                file=route_info.file,
                line=route_info.line,
                framework=route_info.framework.value,
                router_name=route_info.router_name,
            )

    def _add_dependency_nodes(self) -> None:
        """Add nodes for each external dependency."""
        for dep in self.analysis_result.dependencies:
            # Dependency ID format: dependency:{name}
            node_id = f"dependency:{dep.name}"
            self.graph.add_node(
                node_id,
                type="dependency",
                label=dep.name,
                name=dep.name,
                version_constraint=dep.version_constraint,
                source_file=dep.source_file,
                category=dep.category,
            )

    def _add_containment_edges(self) -> None:
        """Add CONTAINS edges for hierarchical relationships."""
        # Repository contains directories
        for file_info in self.analysis_result.files:
            dir_path = "/".join(file_info.path.split("/")[:-1]) if "/" in file_info.path else ""
            if dir_path:
                dir_id = f"directory:{dir_path}"
                repo_id = f"repository:{self.analysis_result.repository.name}"
                if self.graph.has_node(repo_id) and self.graph.has_node(dir_id):
                    self.graph.add_edge(repo_id, dir_id, type="CONTAINS")

        # Directories contain files and subdirectories
        file_dirs: Dict[str, str] = {}  # file path -> its direct parent directory
        for file_info in self.analysis_result.files:
            dir_path = "/".join(file_info.path.split("/")[:-1]) if "/" in file_info.path else ""
            file_dirs[file_info.path] = dir_path
            if dir_path:
                dir_id = f"directory:{dir_path}"
                file_id = f"file:{file_info.path}"
                if self.graph.has_node(dir_id) and self.graph.has_node(file_id):
                    self.graph.add_edge(dir_id, file_id, type="CONTAINS")

        # Modules are contained in files (1:1 mapping for Python files)
        for module_info in self.analysis_result.modules:
            file_id = f"file:{module_info.path}"
            module_id = module_info.id
            if self.graph.has_node(file_id) and self.graph.has_node(module_id):
                self.graph.add_edge(file_id, module_id, type="CONTAINS")

        # Modules contain classes and functions
        for module_info in self.analysis_result.modules:
            module_id = module_info.id
            for class_id in module_info.classes:
                if self.graph.has_node(module_id) and self.graph.has_node(class_id):
                    self.graph.add_edge(module_id, class_id, type="CONTAINS")
            for function_id in module_info.functions:
                if self.graph.has_node(module_id) and self.graph.has_node(function_id):
                    self.graph.add_edge(module_id, function_id, type="CONTAINS")

        # Classes contain methods
        for class_info in self.analysis_result.classes:
            class_id = class_info.id
            for method_id in class_info.methods:
                if self.graph.has_node(class_id) and self.graph.has_node(method_id):
                    self.graph.add_edge(class_id, method_id, type="CONTAINS")

    def _add_import_edges(self) -> None:
        """Add IMPORTS edges between modules."""
        for module_info in self.analysis_result.modules:
            source_module_id = module_info.id
            if not self.graph.has_node(source_module_id):
                continue

            for import_info in module_info.imports:
                targets: Set[str] = set()

                # If it's a "from pkg import submodule" import, resolve each imported name
                if import_info.is_from_import and import_info.names:
                    for name in import_info.names:
                        submodule_id = f"module:{import_info.module}.{name}"
                        if self.graph.has_node(submodule_id):
                            targets.add(submodule_id)

                if not targets:
                    target = self._resolve_import_target(
                        import_info.module,
                        source_module_id,
                    )
                    if target:
                        targets.add(target)

                for target_module_id in targets:
                    if target_module_id and target_module_id != source_module_id and self.graph.has_node(target_module_id):
                        self.graph.add_edge(
                            source_module_id,
                            target_module_id,
                            type="IMPORTS",
                            import_type=import_info.import_type.value,
                            is_from_import=import_info.is_from_import,
                            names=import_info.names,
                            alias=import_info.alias,
                            line=import_info.line,
                        )

    def _resolve_import_target(
        self,
        imported_module: str,
        source_module_id: str,
    ) -> Optional[str]:
        """Resolve an import to a target module ID.

        Args:
            imported_module: The imported module string (e.g., "os", "app.utils.helpers")
            source_module_id: The ID of the source module

        Returns:
            Target module ID if resolvable to an internal module, None otherwise
        """
        # Handle relative imports
        if imported_module.startswith("."):
            # For relative imports, we need the source module's package
            # This is a simplified version - full implementation would need more context
            return None

        # Check if it's an internal module in our analysis
        # Convert dotted path to module ID format
        potential_id = f"module:{imported_module}"
        if self.graph.has_node(potential_id):
            return potential_id

        # Check for submodules (e.g., importing "app.utils" when we have "app.utils.helpers")
        # This handles cases where we import a package and the __init__.py is represented
        parts = imported_module.split(".")
        for i in range(len(parts), 0, -1):
            submodule = ".".join(parts[:i])
            submodule_id = f"module:{submodule}"
            if self.graph.has_node(submodule_id):
                return submodule_id

        return None

    def _add_expose_edges(self) -> None:
        """Add EXPOSES edges from functions to routes."""
        for route_info in self.analysis_result.routes:
            function_id = route_info.function_id
            route_id = f"route:{route_info.method.value.lower()}:{route_info.path}"

            if self.graph.has_node(function_id) and self.graph.has_node(route_id):
                self.graph.add_edge(
                    function_id,
                    route_id,
                    type="EXPOSES",
                    line=route_info.line,
                )

    def _add_dependency_edges(self) -> None:
        """Add DEPENDS_ON edges for external dependencies."""
        # File -> Dependency edges based on where imports occur
        for module_info in self.analysis_result.modules:
            file_id = f"file:{module_info.path}"
            if not self.graph.has_node(file_id):
                continue

            for import_info in module_info.imports:
                if import_info.import_type in (ImportType.EXTERNAL, ImportType.STANDARD_LIBRARY):
                    # Create or find dependency node
                    dep_name = self._extract_package_name(import_info.module)
                    if dep_name:
                        dep_id = f"dependency:{dep_name}"
                        # Ensure dependency node exists (might not if not in requirements)
                        if not self.graph.has_node(dep_id):
                            self.graph.add_node(
                                dep_id,
                                type="dependency",
                                label=dep_name,
                                name=dep_name,
                            )

                        if self.graph.has_node(file_id) and self.graph.has_node(dep_id):
                            self.graph.add_edge(
                                file_id,
                                dep_id,
                                type="DEPENDS_ON",
                                import_type=import_info.import_type.value,
                                names=import_info.names,
                                alias=import_info.alias,
                                line=import_info.line,
                            )

    def _extract_package_name(self, module_name: str) -> Optional[str]:
        """Extract top-level package name from a module import.

        Args:
            module_name: Full module name (e.g., "pydantic.main", "numpy.lib")

        Returns:
            Top-level package name (e.g., "pydantic", "numpy") or None for stdlib
        """
        # This is a simplified version - in reality we'd check against stdlib list
        # and known external packages from dependencies
        if not module_name:
            return None

        # Check if it looks like a standard library module
        stdlib_modules = {
            "os", "sys", "json", "csv", "sqlite3", "collections", "itertools",
            "functools", "re", "math", "random", "datetime", "pathlib", "typing",
            "argparse", "copy", "io", "tempfile", "shutil", "subprocess", "threading",
            "multiprocessing", "socket", "ssl", "http", "urllib", "email", "html",
            "xml", "unittest", "test", "ast", "symtable", "symbol", "tokenize",
            "keyword", "builtins", "gc", "inspect", "site", "sysconfig", "traceback",
            "linecache", "pickle", "copyreg", "shelve", "marshal", "dbm", "sqlite3",
            "zlib", "gzip", "bz2", "lzma", "zipfile", "tarfile", "csv", "configparser",
            "netrc", "xdrlib", "plistlib", "hashlib", "hmac", "secrets", "heapq",
            "bisect", "array", "weakref", "types", "copy", "pprint", "reprlib",
            "enum", "numbers", "decimal", "fractions", "random", "statistics",
            "cmath", "decimal", "fractions", "heapq", "bisect", "array", "queue",
            "sched", "select", "mmap", "fcntl", "pty", "resource", "syslog",
            "tty", "termios", "grp", "pwd", "crypt", "spwd", "broken", "time",
            "atexit", "profile", "tracemalloc", "py_compile", "dis", "pickletools",
            "formatter", "gettext", "locale", "msilib", "msvcrt", "winreg",
            "winsound", "posix", "pwd", "grp", "spwd", "crypt", "broken", "time",
        }

        top_level = module_name.split(".")[0]
        if top_level in stdlib_modules:
            return None  # Standard library, not an external dependency

        # Check if it matches any of our known external dependencies
        for dep in self.analysis_result.dependencies:
            if dep.name == top_level or dep.name.replace("-", "_") == top_level:
                return dep.name

        # Default: assume it's external if not stdlib
        return top_level

    def get_statistics(self) -> Dict[str, int | Dict[str, int]]:
        """Get basic statistics about the graph.

        Returns:
            Dictionary with node and edge counts
        """
        node_counts: Dict[str, int] = {}
        edge_counts: Dict[str, int] = {}

        for node in self.graph.nodes(data=True):
            node_type = node[1].get("type", "unknown")
            node_counts[node_type] = node_counts.get(node_type, 0) + 1

        for edge in self.graph.edges(data=True):
            edge_type = edge[2].get("type", "unknown")
            edge_counts[edge_type] = edge_counts.get(edge_type, 0) + 1

        return {
            "nodes": node_counts,
            "edges": edge_counts,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
        }