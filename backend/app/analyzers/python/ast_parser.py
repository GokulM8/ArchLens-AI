"""Python AST parser — extracts code structure from a single Python file.

Uses Python's built-in ast module to parse source files and extract:
- Imports (import X, from X import Y)
- Classes (name, bases, methods, decorators)
- Functions (name, args, return type, async, decorators)
- API routes (FastAPI and Flask decorator patterns)
- Module-level assignments and constants

This parser extracts FACTS only. No inference or classification happens here.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ParsedImport:
    """An import statement extracted from source."""
    module: str
    names: list[str] = field(default_factory=list)
    alias: Optional[str] = None
    line: int = 0
    is_from_import: bool = False


@dataclass
class ParsedDecorator:
    """A decorator extracted from source."""
    name: str
    arguments: list[str] = field(default_factory=list)
    line: int = 0

    @property
    def full_text(self) -> str:
        if self.arguments:
            return f"@{self.name}({', '.join(self.arguments)})"
        return f"@{self.name}"


@dataclass
class ParsedParameter:
    """A function parameter extracted from source."""
    name: str
    annotation: Optional[str] = None
    default: Optional[str] = None
    kind: str = "POSITIONAL_OR_KEYWORD"


@dataclass
class ParsedFunction:
    """A function or method extracted from source."""
    name: str
    line: int
    end_line: int
    is_async: bool = False
    parameters: list[ParsedParameter] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: list[ParsedDecorator] = field(default_factory=list)
    docstring: Optional[str] = None
    class_name: Optional[str] = None  # set if this is a method


@dataclass
class ParsedClass:
    """A class extracted from source."""
    name: str
    line: int
    end_line: int
    bases: list[str] = field(default_factory=list)
    decorators: list[ParsedDecorator] = field(default_factory=list)
    methods: list[ParsedFunction] = field(default_factory=list)
    docstring: Optional[str] = None
    is_dataclass: bool = False
    is_pydantic_model: bool = False


@dataclass
class ParsedRoute:
    """An API route extracted from a decorator pattern."""
    method: str  # GET, POST, etc.
    path: str  # "/users/{id}"
    function_name: str
    line: int  # line of the decorator
    framework: str  # "fastapi" or "flask"
    router_name: str  # "app", "router", etc.


@dataclass
class ParsedModule:
    """Complete parse result for a single Python file."""
    file_path: str
    lines: int = 0
    imports: list[ParsedImport] = field(default_factory=list)
    classes: list[ParsedClass] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)
    routes: list[ParsedRoute] = field(default_factory=list)
    module_docstring: Optional[str] = None
    parse_errors: list[str] = field(default_factory=list)

    @property
    def all_functions(self) -> list[ParsedFunction]:
        """All functions including methods inside classes."""
        result = list(self.functions)
        for cls in self.classes:
            result.extend(cls.methods)
        return result


class PythonASTParser:
    """Parses a single Python source file and extracts structural information.

    This parser is stateless — each call to parse() is independent.
    It extracts only deterministic facts derivable from the AST.
    """

    def parse(self, file_path: str, source: Optional[str] = None) -> ParsedModule:
        """Parse a Python file and extract its structure.

        Args:
            file_path: Path to the Python file (used for error reporting).
            source: Optional source code string. If None, reads from file_path.

        Returns:
            ParsedModule with all extracted entities.
        """
        result = ParsedModule(file_path=file_path)

        if source is None:
            try:
                source = Path(file_path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    source = Path(file_path).read_text(encoding="latin-1")
                except Exception as e:
                    result.parse_errors.append(f"Cannot read file: {e}")
                    return result
            except Exception as e:
                result.parse_errors.append(f"Cannot read file: {e}")
                return result

        result.lines = source.count("\n") + (1 if source and not source.endswith("\n") else 0)

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            result.parse_errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return result

        # Extract module docstring
        result.module_docstring = ast.get_docstring(tree)

        # Walk top-level nodes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                result.imports.extend(self._extract_import(node))
            elif isinstance(node, ast.ClassDef):
                parsed_class = self._extract_class(node)
                result.classes.append(parsed_class)
                # Extract routes from methods
                for method in parsed_class.methods:
                    routes = self._extract_routes_from_decorators(
                        method.decorators, method.name, method.line
                    )
                    result.routes.extend(routes)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = self._extract_function(node)
                result.functions.append(func)
                # Extract routes from function decorators
                routes = self._extract_routes_from_decorators(
                    func.decorators, func.name, func.line
                )
                result.routes.extend(routes)

        return result

    def _extract_import(self, node: ast.Import | ast.ImportFrom) -> list[ParsedImport]:
        """Extract import information from an import node."""
        imports = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ParsedImport(
                    module=alias.name,
                    names=[],
                    alias=alias.asname,
                    line=node.lineno,
                    is_from_import=False,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            # Handle relative imports
            if node.level and node.level > 0:
                module = "." * node.level + module

            names = [alias.name for alias in (node.names or [])]

            imports.append(ParsedImport(
                module=module,
                names=names,
                alias=None,  # from imports don't have a single alias
                line=node.lineno,
                is_from_import=True,
            ))

        return imports

    def _extract_class(self, node: ast.ClassDef) -> ParsedClass:
        """Extract class information including methods."""
        bases = []
        for base in node.bases:
            bases.append(self._node_to_source(base))

        decorators = [self._extract_decorator(d) for d in node.decorator_list]

        # Check for dataclass/pydantic patterns
        is_dataclass = any(
            d.name in ("dataclass", "dataclasses.dataclass") for d in decorators
        )
        is_pydantic = any(
            base in ("BaseModel", "pydantic.BaseModel") for base in bases
        )

        methods = []
        for item in ast.iter_child_nodes(node):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = self._extract_function(item, class_name=node.name)
                methods.append(func)

        return ParsedClass(
            name=node.name,
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            bases=bases,
            decorators=decorators,
            methods=methods,
            docstring=ast.get_docstring(node),
            is_dataclass=is_dataclass,
            is_pydantic_model=is_pydantic,
        )

    def _extract_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: Optional[str] = None
    ) -> ParsedFunction:
        """Extract function information."""
        parameters = self._extract_parameters(node.args)
        decorators = [self._extract_decorator(d) for d in node.decorator_list]

        return_annotation = None
        if node.returns:
            return_annotation = self._node_to_source(node.returns)

        return ParsedFunction(
            name=node.name,
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            parameters=parameters,
            return_annotation=return_annotation,
            decorators=decorators,
            docstring=ast.get_docstring(node),
            class_name=class_name,
        )

    def _extract_parameters(self, args: ast.arguments) -> list[ParsedParameter]:
        """Extract function parameters."""
        params = []

        # Calculate defaults offset (defaults align to the end of args)
        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults

        for i, arg in enumerate(args.args):
            annotation = self._node_to_source(arg.annotation) if arg.annotation else None
            default = None
            default_idx = i - default_offset
            if default_idx >= 0 and default_idx < len(args.defaults):
                default = self._node_to_source(args.defaults[default_idx])

            params.append(ParsedParameter(
                name=arg.arg,
                annotation=annotation,
                default=default,
                kind="POSITIONAL_OR_KEYWORD",
            ))

        # *args
        if args.vararg:
            annotation = self._node_to_source(args.vararg.annotation) if args.vararg.annotation else None
            params.append(ParsedParameter(
                name=f"*{args.vararg.arg}",
                annotation=annotation,
                kind="VAR_POSITIONAL",
            ))

        # keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            annotation = self._node_to_source(arg.annotation) if arg.annotation else None
            default = None
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                default = self._node_to_source(args.kw_defaults[i])
            params.append(ParsedParameter(
                name=arg.arg,
                annotation=annotation,
                default=default,
                kind="KEYWORD_ONLY",
            ))

        # **kwargs
        if args.kwarg:
            annotation = self._node_to_source(args.kwarg.annotation) if args.kwarg.annotation else None
            params.append(ParsedParameter(
                name=f"**{args.kwarg.arg}",
                annotation=annotation,
                kind="VAR_KEYWORD",
            ))

        return params

    def _extract_decorator(self, node: ast.expr) -> ParsedDecorator:
        """Extract decorator information."""
        if isinstance(node, ast.Call):
            name = self._node_to_source(node.func)
            arguments = []
            for arg in node.args:
                arguments.append(self._node_to_source(arg))
            for kw in node.keywords:
                if kw.arg:
                    arguments.append(f"{kw.arg}={self._node_to_source(kw.value)}")
                else:
                    arguments.append(f"**{self._node_to_source(kw.value)}")
            return ParsedDecorator(
                name=name,
                arguments=arguments,
                line=node.lineno,
            )
        else:
            return ParsedDecorator(
                name=self._node_to_source(node),
                arguments=[],
                line=node.lineno,
            )

    def _extract_routes_from_decorators(
        self,
        decorators: list[ParsedDecorator],
        function_name: str,
        function_line: int,
    ) -> list[ParsedRoute]:
        """Detect API routes from decorator patterns.

        Recognizes:
        - FastAPI: @app.get("/path"), @router.post("/path"), etc.
        - Flask: @app.route("/path"), @app.route("/path", methods=["GET"])
        """
        routes = []

        # FastAPI HTTP method decorators
        fastapi_methods = {"get", "post", "put", "delete", "patch", "options", "head"}

        for dec in decorators:
            name = dec.name
            args = dec.arguments

            # FastAPI pattern: @app.get("/path") or @router.post("/path")
            parts = name.rsplit(".", 1)
            if len(parts) == 2:
                router_name, method_name = parts

                if method_name in fastapi_methods and args:
                    # First argument should be the path
                    path = args[0].strip("'\"")
                    routes.append(ParsedRoute(
                        method=method_name.upper(),
                        path=path,
                        function_name=function_name,
                        line=dec.line,
                        framework="fastapi",
                        router_name=router_name,
                    ))

                # Flask pattern: @app.route("/path") or @app.route("/path", methods=["GET"])
                elif method_name == "route" and args:
                    path = args[0].strip("'\"")
                    methods = ["GET"]  # Flask default

                    # Check for methods= keyword argument
                    for arg in args[1:]:
                        if arg.startswith("methods="):
                            methods_str = arg[len("methods="):]
                            # Parse methods list like ['GET', 'POST']
                            methods = self._parse_methods_list(methods_str)

                    for method in methods:
                        routes.append(ParsedRoute(
                            method=method.upper(),
                            path=path,
                            function_name=function_name,
                            line=dec.line,
                            framework="flask",
                            router_name=router_name,
                        ))

        return routes

    def _parse_methods_list(self, methods_str: str) -> list[str]:
        """Parse a methods list from a Flask route decorator argument.

        Handles strings like: ['GET', 'POST'] or ["GET", "POST"]
        """
        methods = []
        # Strip brackets and split
        cleaned = methods_str.strip("[](){}")
        for part in cleaned.split(","):
            method = part.strip().strip("'\"").strip()
            if method:
                methods.append(method)
        return methods

    def _node_to_source(self, node: ast.AST | None) -> str:
        """Convert an AST node back to source text.

        Uses ast.unparse on Python 3.9+, falls back to a simpler
        representation on older versions.
        """
        if node is None:
            return ""

        try:
            return ast.unparse(node)
        except Exception:
            # Fallback for complex nodes
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                value = self._node_to_source(node.value)
                return f"{value}.{node.attr}"
            elif isinstance(node, ast.Constant):
                return repr(node.value)
            elif isinstance(node, ast.Subscript):
                value = self._node_to_source(node.value)
                slice_val = self._node_to_source(node.slice)
                return f"{value}[{slice_val}]"
            elif isinstance(node, ast.Tuple):
                elts = ", ".join(self._node_to_source(e) for e in node.elts)
                return f"({elts})"
            elif isinstance(node, ast.List):
                elts = ", ".join(self._node_to_source(e) for e in node.elts)
                return f"[{elts}]"
            return "<complex>"


def parse_python_file(file_path: str, source: Optional[str] = None) -> ParsedModule:
    """Convenience function to parse a single Python file.

    Args:
        file_path: Path to the Python file.
        source: Optional source text. If None, reads from file_path.

    Returns:
        ParsedModule with extracted code structure.
    """
    parser = PythonASTParser()
    return parser.parse(file_path, source)
