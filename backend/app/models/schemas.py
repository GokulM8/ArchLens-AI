"""Pydantic models for ArchLens AI analysis output.

These models define the structured schema for analysis.json — the primary
output of the repository analysis pipeline. Every field represents a
deterministic fact extracted from source code, not an inference.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ImportType(str, Enum):
    """Classification of a Python import statement."""
    INTERNAL = "internal"
    EXTERNAL = "external"
    STANDARD_LIBRARY = "standard_library"


class RelationshipType(str, Enum):
    """Types of relationships between code entities."""
    IMPORTS = "IMPORTS"
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    EXPOSES = "EXPOSES"
    DEPENDS_ON = "DEPENDS_ON"


class HTTPMethod(str, Enum):
    """Standard HTTP methods detected in route decorators."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class Framework(str, Enum):
    """Supported web frameworks for route detection."""
    FASTAPI = "fastapi"
    FLASK = "flask"


class RepositoryMetadata(BaseModel):
    """Top-level metadata about the analyzed repository."""
    name: str = Field(description="Repository or directory name")
    root_path: str = Field(description="Absolute path to the analyzed directory")
    analyzed_at: str = Field(description="ISO 8601 timestamp of the analysis")
    python_version: Optional[str] = Field(default=None, description="Python version if detectable")
    total_size_bytes: int = Field(default=0, description="Total size of analyzed Python files")


class FileInfo(BaseModel):
    """Metadata about a single file in the repository."""
    path: str = Field(description="Relative path from repository root")
    size_bytes: int = Field(description="File size in bytes")
    lines: int = Field(description="Total line count")
    module_name: Optional[str] = Field(default=None, description="Python module name (dotted)")
    package: Optional[str] = Field(default=None, description="Containing package name")
    is_init: bool = Field(default=False, description="Whether this is an __init__.py file")


class Parameter(BaseModel):
    """A function or method parameter."""
    name: str
    annotation: Optional[str] = Field(default=None, description="Type annotation as source text")
    default: Optional[str] = Field(default=None, description="Default value as source text")
    kind: str = Field(default="POSITIONAL_OR_KEYWORD", description="Parameter kind (positional, keyword, etc.)")


class Decorator(BaseModel):
    """A decorator applied to a class or function."""
    name: str = Field(description="Full decorator name (e.g., 'app.get')")
    arguments: list[str] = Field(default_factory=list, description="Decorator arguments as source text")
    line: int = Field(description="Line number of the decorator")


class ImportInfo(BaseModel):
    """A single import statement."""
    module: str = Field(description="Imported module path")
    names: list[str] = Field(default_factory=list, description="Specific names imported (from X import Y)")
    alias: Optional[str] = Field(default=None, description="Import alias if present")
    import_type: ImportType = Field(description="Whether internal, external, or stdlib")
    line: int = Field(description="Line number of the import")
    is_from_import: bool = Field(default=False, description="Whether this is a 'from' import")


class FunctionInfo(BaseModel):
    """A function or method extracted from source code."""
    id: str = Field(description="Stable identifier: file:qualified_name")
    name: str = Field(description="Function name")
    qualified_name: str = Field(description="Fully qualified name within the module")
    file: str = Field(description="Relative file path")
    line: int = Field(description="Start line number")
    end_line: int = Field(description="End line number")
    is_async: bool = Field(default=False, description="Whether the function is async")
    parameters: list[Parameter] = Field(default_factory=list)
    return_annotation: Optional[str] = Field(default=None, description="Return type annotation")
    decorators: list[Decorator] = Field(default_factory=list)
    class_id: Optional[str] = Field(default=None, description="ID of containing class, if a method")
    docstring: Optional[str] = Field(default=None, description="First line of docstring")
    is_private: bool = Field(default=False, description="Name starts with _")
    is_dunder: bool = Field(default=False, description="Name starts and ends with __")


class ClassInfo(BaseModel):
    """A class extracted from source code."""
    id: str = Field(description="Stable identifier: file:class_name")
    name: str = Field(description="Class name")
    file: str = Field(description="Relative file path")
    line: int = Field(description="Start line number")
    end_line: int = Field(description="End line number")
    bases: list[str] = Field(default_factory=list, description="Base class names")
    decorators: list[Decorator] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list, description="IDs of methods in this class")
    docstring: Optional[str] = Field(default=None, description="First line of docstring")
    is_dataclass: bool = Field(default=False)
    is_pydantic_model: bool = Field(default=False)


class RouteInfo(BaseModel):
    """An API route/endpoint detected via framework-specific patterns."""
    method: HTTPMethod = Field(description="HTTP method")
    path: str = Field(description="Route path (e.g., '/users/{id}')")
    function_id: str = Field(description="ID of the handler function")
    function_name: str = Field(description="Handler function name")
    file: str = Field(description="Relative file path")
    line: int = Field(description="Line number of the route decorator")
    framework: Framework = Field(description="Detected framework")
    router_name: Optional[str] = Field(default=None, description="Router/app variable name")


class ExternalDependency(BaseModel):
    """An external package dependency from requirements/config files."""
    name: str = Field(description="Package name")
    version_constraint: Optional[str] = Field(default=None, description="Version constraint if specified")
    source_file: Optional[str] = Field(default=None, description="File where dependency was declared")
    category: Optional[str] = Field(default=None, description="Technology category if recognized")


class Relationship(BaseModel):
    """A relationship between two code entities."""
    source: str = Field(description="Source entity ID")
    target: str = Field(description="Target entity ID")
    type: RelationshipType = Field(description="Relationship type")
    file: Optional[str] = Field(default=None, description="File where relationship is established")
    line: Optional[int] = Field(default=None, description="Line number")


class ModuleInfo(BaseModel):
    """A Python module (single .py file) with its contents."""
    id: str = Field(description="Stable identifier: module:dotted.path")
    path: str = Field(description="Relative file path")
    package: Optional[str] = Field(default=None, description="Containing package")
    imports: list[ImportInfo] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list, description="IDs of classes in this module")
    functions: list[str] = Field(default_factory=list, description="IDs of top-level functions in this module")


class AnalysisStatistics(BaseModel):
    """Summary statistics about the analysis."""
    total_files: int = 0
    total_python_files: int = 0
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_routes: int = 0
    total_imports: int = 0
    internal_dependencies: int = 0
    external_dependencies: int = 0
    standard_library_imports: int = 0
    packages: int = 0


class AnalysisResult(BaseModel):
    """Top-level analysis output — the complete analysis.json schema."""
    schema_version: str = Field(default="1.0", description="Schema version for forwards compatibility")
    repository: RepositoryMetadata
    files: list[FileInfo] = Field(default_factory=list)
    modules: list[ModuleInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    functions: list[FunctionInfo] = Field(default_factory=list)
    routes: list[RouteInfo] = Field(default_factory=list)
    dependencies: list[ExternalDependency] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    statistics: AnalysisStatistics = Field(default_factory=AnalysisStatistics)
