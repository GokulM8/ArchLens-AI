"""Tests for the requirements/dependency file parser."""

from __future__ import annotations

from pathlib import Path

from app.analyzers.config.requirements_parser import (
    parse_requirements_txt,
    parse_pyproject_toml,
    parse_setup_py,
    parse_dependency_file,
    ParsedDependency,
)


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content)
    return str(path)


class TestRequirementsTxt:
    """Tests for requirements.txt parsing."""

    def test_simple_requirements(self, tmp_path: Path):
        f = _write(tmp_path, "requirements.txt", "fastapi\nflask\n")
        deps = parse_requirements_txt(f)
        assert [d.name for d in deps] == ["fastapi", "flask"]

    def test_version_constraints(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "requirements.txt",
            "fastapi==0.100.0\nnumpy>=1.24\nrequests~=2.31\npydantic==2.0.*\n",
        )
        deps = parse_requirements_txt(f)
        assert [d.version_constraint for d in deps] == [
            "==0.100.0",
            ">=1.24",
            "~=2.31",
            "==2.0.*",
        ]

    def test_comments_and_blank_lines(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "requirements.txt",
            "# A comment\n\nfastapi  # inline comment\n\n-r base.txt\n",
        )
        deps = parse_requirements_txt(f)
        assert [d.name for d in deps] == ["fastapi"]

    def test_extras(self, tmp_path: Path):
        f = _write(tmp_path, "requirements.txt", "uvicorn[standard]>=0.23\n")
        deps = parse_requirements_txt(f)
        assert deps[0].name == "uvicorn"
        assert deps[0].extras == ["standard"]

    def test_environment_markers_stripped(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "requirements.txt",
            "foo>=1.0; python_version < '3.9'\n",
        )
        deps = parse_requirements_txt(f)
        assert deps[0].version_constraint == ">=1.0"

    def test_dev_detection_from_filename(self, tmp_path: Path):
        f = _write(tmp_path, "requirements-dev.txt", "pytest\n")
        deps = parse_requirements_txt(f)
        assert deps[0].is_dev

    def test_skips_urls(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "requirements.txt",
            "git+https://github.com/foo/bar.git@v1\nhttps://example.com/whl.whl\n",
        )
        deps = parse_requirements_txt(f)
        assert deps == []


class TestPyprojectToml:
    """Tests for pyproject.toml parsing."""

    def test_pep621_dependencies(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "pyproject.toml",
            '[project]\nname = "demo"\n'
            'dependencies = [\n'
            '    "fastapi>=0.100",\n'
            '    "sqlalchemy==2.0",\n'
            ']\n',
        )
        deps = parse_pyproject_toml(f)
        assert {d.name for d in deps} == {"fastapi", "sqlalchemy"}

    def test_optional_dependencies_marked_dev(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "pyproject.toml",
            '[project.optional-dependencies]\n'
            'dev = ["pytest", "black"]\n',
        )
        deps = parse_pyproject_toml(f)
        assert all(d.is_dev for d in deps)

    def test_poetry_format(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "pyproject.toml",
            '[tool.poetry.dependencies]\n'
            'python = "^3.11"\n'
            'fastapi = "^0.100"\n'
            'redis = { version = "^4.0", extras = ["hiredis"] }\n'
            '\n'
            '[tool.poetry.group.dev.dependencies]\n'
            'pytest = "^7.0"\n',
        )
        deps = parse_pyproject_toml(f)
        names = {d.name: d for d in deps}
        assert "python" not in names  # python is skipped
        assert names["fastapi"].version_constraint == "^0.100"
        assert names["redis"].version_constraint == "^4.0"
        assert names["pytest"].is_dev


class TestSetupPy:
    """Tests for setup.py parsing."""

    def test_install_requires(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "setup.py",
            'from setuptools import setup\n'
            'setup(\n'
            '    name="demo",\n'
            '    install_requires=["numpy", "requests"],\n'
            ')\n',
        )
        deps = parse_setup_py(f)
        assert {d.name for d in deps} == {"numpy", "requests"}


class TestParseDependencyFile:
    """Tests for the router function."""

    def test_dispatches_by_extension(self, tmp_path: Path):
        req = _write(tmp_path, "requirements.txt", "fastapi\n")
        deps = parse_dependency_file(req)
        assert deps[0].name == "fastapi"

        other = _write(tmp_path, "Pipfile", "[packages]\nflask = \"*\"\n")
        # Pipfile is not supported yet — returns empty
        assert parse_dependency_file(other) == []

    def test_unknown_file_returns_empty(self, tmp_path: Path):
        f = _write(tmp_path, "notes.txt", "nothing here\n")
        assert parse_dependency_file(f) == []


def test_parsed_dependency_fields():
    """ParsedDependency dataclass defaults."""
    dep = ParsedDependency(name="fastapi")
    assert dep.version_constraint is None
    assert dep.extras == []
    assert not dep.is_dev