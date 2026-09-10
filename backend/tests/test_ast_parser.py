"""Tests for the Python AST parser."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.python.ast_parser import parse_python_file, PythonASTParser


class TestImports:
    """Import extraction tests."""

    def test_import_simple(self):
        parsed = parse_python_file("test.py", "import numpy\n")
        assert len(parsed.imports) == 1
        imp = parsed.imports[0]
        assert imp.module == "numpy"
        assert imp.line == 1
        assert not imp.is_from_import

    def test_import_multiple_names(self):
        parsed = parse_python_file("test.py", "import os, sys\n")
        assert len(parsed.imports) == 2
        assert [i.module for i in parsed.imports] == ["os", "sys"]

    def test_import_with_alias(self):
        parsed = parse_python_file("test.py", "import numpy as np\n")
        assert parsed.imports[0].module == "numpy"
        assert parsed.imports[0].alias == "np"

    def test_from_import(self):
        parsed = parse_python_file(
            "test.py", "from sklearn.ensemble import RandomForestClassifier\n"
        )
        assert len(parsed.imports) == 1
        imp = parsed.imports[0]
        assert imp.module == "sklearn.ensemble"
        assert imp.names == ["RandomForestClassifier"]
        assert imp.is_from_import

    def test_from_import_multiple_names(self):
        parsed = parse_python_file(
            "test.py", "from services.user import UserService, UserCreate\n"
        )
        assert parsed.imports[0].names == ["UserService", "UserCreate"]

    def test_relative_import(self):
        parsed = parse_python_file("test.py", "from .models import User\n")
        assert parsed.imports[0].module == ".models"

    def test_relative_import_deep(self):
        parsed = parse_python_file("test.py", "from ..services import auth\n")
        assert parsed.imports[0].module == "..services"

    def test_upgrade_import(self):
        parsed = parse_python_file("test.py", "from __future__ import annotations\n")
        assert parsed.imports[0].module == "__future__"

    def test_import_line_numbers(self):
        src = "# comment\nimport os\n\nfrom collections import OrderedDict\n"
        parsed = parse_python_file("test.py", src)
        assert [i.line for i in parsed.imports] == [2, 4]


class TestClasses:
    """Class extraction tests."""

    def test_simple_class(self):
        parsed = parse_python_file(
            "test.py",
            "class UserService(BaseService):\n    pass\n",
        )
        assert len(parsed.classes) == 1
        cls = parsed.classes[0]
        assert cls.name == "UserService"
        assert cls.bases == ["BaseService"]
        assert cls.line == 1

    def test_class_with_multiple_bases(self):
        parsed = parse_python_file(
            "test.py",
            "class Model(Base, ABC, metaclass=type):\n    pass\n",
        )
        cls = parsed.classes[0]
        # metaclass=type is not a base
        assert cls.bases == ["Base", "ABC"]

    def test_class_methods(self):
        src = (
            "class UserService:\n"
            "    def get_user(self, user_id: int) -> str:\n"
            "        pass\n"
            "    async def list_users(self):\n"
            "        pass\n"
        )
        parsed = parse_python_file("test.py", src)
        cls = parsed.classes[0]
        assert len(cls.methods) == 2
        assert [m.name for m in cls.methods] == ["get_user", "list_users"]
        assert cls.methods[0].is_async is False
        assert cls.methods[1].is_async is True

    def test_class_with_decorators(self):
        parsed = parse_python_file(
            "test.py",
            "@dataclass\nclass Point:\n    x: int\n",
        )
        cls = parsed.classes[0]
        assert cls.is_dataclass
        assert cls.decorators[0].name == "dataclass"

    def test_pydantic_model(self):
        parsed = parse_python_file(
            "test.py",
            "from pydantic import BaseModel\nclass User(BaseModel):\n    pass\n",
        )
        cls = parsed.classes[0]
        assert cls.is_pydantic_model

    def test_class_end_line(self):
        src = "class Foo:\n    pass\n\n\nclass Bar:\n    pass\n"
        parsed = parse_python_file("test.py", src)
        assert parsed.classes[0].end_line == 2
        assert parsed.classes[1].end_line == 6


class TestFunctions:
    """Function extraction tests."""

    def test_simple_function(self):
        parsed = parse_python_file(
            "test.py",
            "def hello():\n    return 'world'\n",
        )
        assert len(parsed.functions) == 1
        func = parsed.functions[0]
        assert func.name == "hello"
        assert not func.is_async
        assert func.line == 1

    def test_async_function(self):
        parsed = parse_python_file(
            "test.py",
            "async def fetch(url: str):\n    pass\n",
        )
        func = parsed.functions[0]
        assert func.is_async

    def test_function_with_type_annotations(self):
        parsed = parse_python_file(
            "test.py",
            "def add(a: int, b: int = 0) -> int:\n    return a + b\n",
        )
        func = parsed.functions[0]
        assert func.return_annotation == "int"
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "a"
        assert func.parameters[0].annotation == "int"
        assert func.parameters[1].default == "0"

    def test_var_args(self):
        parsed = parse_python_file(
            "test.py",
            "def f(*args, **kwargs):\n    pass\n",
        )
        func = parsed.functions[0]
        kinds = [p.kind for p in func.parameters]
        assert "VAR_POSITIONAL" in kinds
        assert "VAR_KEYWORD" in kinds

    def test_keyword_only_args(self):
        parsed = parse_python_file(
            "test.py",
            "def f(x, *, y):\n    pass\n",
        )
        func = parsed.functions[0]
        kinds = [p.kind for p in func.parameters]
        assert kinds == ["POSITIONAL_OR_KEYWORD", "KEYWORD_ONLY"]

    def test_multiple_defaults_alignment(self):
        parsed = parse_python_file(
            "test.py",
            "def f(a, b=1, c=2):\n    pass\n",
        )
        func = parsed.functions[0]
        assert [p.default for p in func.parameters] == [None, "1", "2"]

    def test_function_docstring(self):
        parsed = parse_python_file(
            'test.py',
            'def f():\n    """Return something."""\n    return 1\n',
        )
        assert parsed.functions[0].docstring == "Return something."

    def test_function_decorators(self):
        parsed = parse_python_file(
            "test.py",
            "@cache\n@retry(times=3)\ndef f():\n    pass\n",
        )
        func = parsed.functions[0]
        assert [d.name for d in func.decorators] == ["cache", "retry"]
        assert func.decorators[1].arguments == ["times=3"]


class TestRoutes:
    """FastAPI/Flask route detection tests."""

    def test_fastapi_get(self):
        parsed = parse_python_file(
            "test.py",
            'from fastapi import APIRouter\nrouter = APIRouter()\n'
            '@router.get("/users/{user_id}")\ndef get_user(user_id: int):\n    pass\n',
        )
        assert len(parsed.routes) == 1
        route = parsed.routes[0]
        assert route.method == "GET"
        assert route.path == "/users/{user_id}"
        assert route.function_name == "get_user"
        assert route.framework == "fastapi"
        assert route.router_name == "router"

    def test_fastapi_post(self):
        parsed = parse_python_file(
            "test.py",
            'from fastapi import FastAPI\napp = FastAPI()\n'
            '@app.post("/predict")\ndef predict():\n    pass\n',
        )
        route = parsed.routes[0]
        assert route.method == "POST"
        assert route.path == "/predict"
        assert route.router_name == "app"

    def test_fastapi_all_http_methods(self):
        src_lines = []
        for i, method in enumerate(["get", "post", "put", "delete", "patch"]):
            src_lines.append(f'@app.{method}("/path{i}")')
            src_lines.append(f"def handler{i}():\n    pass\n")
        parsed = parse_python_file("test.py", "\n".join(src_lines))
        assert len(parsed.routes) == 5

    def test_flask_route_get(self):
        parsed = parse_python_file(
            "test.py",
            'from flask import Flask\napp = Flask(__name__)\n'
            '@app.route("/home")\ndef home():\n    pass\n',
        )
        route = parsed.routes[0]
        assert route.method == "GET"  # Flask default
        assert route.path == "/home"
        assert route.framework == "flask"

    def test_flask_route_explicit_methods(self):
        parsed = parse_python_file(
            "test.py",
            "@app.route('/predict', methods=['POST', 'PUT'])\ndef predict():\n    pass\n",
        )
        assert len(parsed.routes) == 2
        assert [r.method for r in parsed.routes] == ["POST", "PUT"]

    def test_route_decorator_line_number(self):
        parsed = parse_python_file(
            "test.py",
            '# comment\n@app.get("/x")\ndef get_x():\n    pass\n',
        )
        assert parsed.routes[0].line == 2

    def test_route_within_class(self):
        # FastAPI MethodView-style patterns are uncommon, but a route-like
        # decorator on a method should still be detected.
        parsed = parse_python_file(
            "test.py",
            "class Views:\n"
            "    @router.get('/items')\n"
            "    def get_items(self):\n"
            "        pass\n",
        )
        assert len(parsed.routes) == 1
        assert parsed.routes[0].function_name == "get_items"


class TestParseErrors:
    """Error handling tests."""

    def test_syntax_error_reported(self):
        parsed = parse_python_file("broken.py", "def f(:\n")
        assert len(parsed.parse_errors) > 0

    def test_missing_file(self):
        parsed = parse_python_file("/nonexistent/path/file.py")
        assert len(parsed.parse_errors) > 0

    def test_empty_source(self):
        parsed = parse_python_file("empty.py", "")
        assert parsed.imports == []
        assert parsed.classes == []
        assert parsed.functions == []

    def test_module_docstring(self):
        parsed = parse_python_file(
            "test.py",
            '"""Module docstring."""\nimport os\n',
        )
        assert parsed.module_docstring == "Module docstring."


class TestModuleProperties:
    """ParsedModule helper properties."""

    def test_line_count(self):
        parsed = parse_python_file("test.py", "a = 1\nb = 2\nc = 3\n")
        assert parsed.lines == 3

    def test_line_count_no_trailing_newline(self):
        parsed = parse_python_file("test.py", "a = 1\nb = 2")
        assert parsed.lines == 2

    def test_all_functions_includes_methods(self):
        src = (
            "def top():\n    pass\n"
            "class C:\n"
            "    def method(self):\n"
            "        pass\n"
        )
        parsed = parse_python_file("test.py", src)
        names = [f.name for f in parsed.all_functions]
        assert names == ["top", "method"]


def test_parse_python_file_from_disk(tmp_path: Path):
    """Parsing reads source from the filesystem."""
    f = tmp_path / "mod.py"
    f.write_text("def func():\n    return 1\n")
    parsed = parse_python_file(str(f))
    assert len(parsed.functions) == 1


def test_parse_non_utf8_fallback(tmp_path: Path):
    """Non-UTF8 files fall back to latin-1 rather than failing."""
    f = tmp_path / "legacy.py"
    f.write_bytes("x = 'café'\n".encode("latin-1"))
    parsed = parse_python_file(str(f))
    assert parsed.parse_errors == []