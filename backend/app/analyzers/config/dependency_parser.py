"""Dependency file parser — extracts external packages from config files.

Parses:
- requirements.txt
- pyproject.toml (PEP 621 and Poetry formats)
- Pipfile
- setup.py (basic pattern matching only)
- setup.cfg

Returns structured information about declared dependencies.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Dependency:
    """A parsed external dependency."""
    name: str
    version_constraint: Optional[str] = None
    source_file: Optional[str] = None
    extras: list[str] = field(default_factory=list)
    is_dev: bool = False

    @property
    def normalized_name(self) -> str:
        """Get normalized package name (lowercase, _ → -)."""
        return self.name.lower().replace("_", "-")


class DependencyParser:
    """Parses Python dependency files and extracts package information."""

    @staticmethod
    def parse_requirements_txt(file_path: str | Path) -> list[Dependency]:
        """Parse a requirements.txt file.

        Handles:
        - Simple package names: `requests`
        - Versioned: `requests>=2.28.0`
        - With extras: `fastapi[all]>=0.100.0`
        - Comments and empty lines

        Skips:
        - -e editable installs
        - -r recursive includes
        - URLs
        - Comments
        """
        path = Path(file_path)
        if not path.exists():
            return []

        dependencies = []
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []

        for line in content.splitlines():
            line = line.strip()

            # Skip empty, comments, and special directives
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Remove inline comments
            if "#" in line:
                line = line.split("#")[0].strip()

            dep = DependencyParser._parse_requirement_line(line, str(path))
            if dep:
                dependencies.append(dep)

        return dependencies

    @staticmethod
    def _parse_requirement_line(line: str, source_file: str) -> Optional[Dependency]:
        """Parse a single requirement line.

        Format: package[extra1,extra2]>=1.0.0,<2.0.0
        """
        # Skip URLs
        if line.startswith(("http://", "https://", "git+")):
            return None

        # Pattern: package_name[extras]version_spec
        match = re.match(
            r"^([a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)"  # package name
            r"(\[[^\]]+\])?"  # optional [extras]
            r"(.*)$",  # version specifiers
            line
        )

        if not match:
            return None

        name = match.group(1)
        extras_str = match.group(3) or ""
        version_part = match.group(4).strip()

        extras = []
        if extras_str:
            extras = [e.strip() for e in extras_str.strip("[]").split(",")]

        return Dependency(
            name=name,
            version_constraint=version_part if version_part else None,
            source_file=source_file,
            extras=extras,
        )

    @staticmethod
    def parse_pyproject_toml(file_path: str | Path) -> list[Dependency]:
        """Parse dependencies from pyproject.toml.

        Supports:
        - PEP 621 format: [project.dependencies]
        - Poetry format: [tool.poetry.dependencies]
        """
        path = Path(file_path)
        if not path.exists():
            return []

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return []

        dependencies = []

        # PEP 621 format
        if "project" in data and "dependencies" in data["project"]:
            for dep_str in data["project"]["dependencies"]:
                dep = DependencyParser._parse_requirement_line(dep_str, str(path))
                if dep:
                    dependencies.append(dep)

        # PEP 621 optional dependencies (extras)
        if "project" in data and "optional-dependencies" in data["project"]:
            for group, deps in data["project"]["optional-dependencies"].items():
                for dep_str in deps:
                    dep = DependencyParser._parse_requirement_line(dep_str, str(path))
                    if dep:
                        dep.is_dev = group in ("dev", "test", "docs")
                        dependencies.append(dep)

        # Poetry format
        if "tool" in data and "poetry" in data["tool"]:
            poetry = data["tool"]["poetry"]

            if "dependencies" in poetry:
                for name, spec in poetry["dependencies"].items():
                    if name == "python":  # Skip Python itself
                        continue
                    dependencies.append(DependencyParser._parse_poetry_dep(name, spec, str(path), False))

            if "dev-dependencies" in poetry or "group" in poetry:
                # Poetry 1.2+ uses groups
                dev_deps = poetry.get("dev-dependencies", {})
                for name, spec in dev_deps.items():
                    dependencies.append(DependencyParser._parse_poetry_dep(name, spec, str(path), True))

        return dependencies

    @staticmethod
    def _parse_poetry_dep(name: str, spec: str | dict, source_file: str, is_dev: bool) -> Dependency:
        """Parse a Poetry dependency specification."""
        if isinstance(spec, str):
            # Simple version string: "^1.0.0"
            return Dependency(
                name=name,
                version_constraint=spec,
                source_file=source_file,
                is_dev=is_dev,
            )
        elif isinstance(spec, dict):
            # Complex spec: {version = "^1.0", extras = ["all"]}
            version = spec.get("version", "")
            extras = spec.get("extras", [])
            return Dependency(
                name=name,
                version_constraint=version,
                source_file=source_file,
                extras=extras,
                is_dev=is_dev,
            )
        else:
            return Dependency(name=name, source_file=source_file, is_dev=is_dev)

    @staticmethod
    def parse_pipfile(file_path: str | Path) -> list[Dependency]:
        """Parse dependencies from a Pipfile (TOML format).

        Sections:
        - [packages] — production dependencies
        - [dev-packages] — development dependencies
        """
        path = Path(file_path)
        if not path.exists():
            return []

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return []

        dependencies = []

        # Production packages
        if "packages" in data:
            for name, spec in data["packages"].items():
                dep = DependencyParser._parse_pipfile_dep(name, spec, str(path), False)
                dependencies.append(dep)

        # Dev packages
        if "dev-packages" in data:
            for name, spec in data["dev-packages"].items():
                dep = DependencyParser._parse_pipfile_dep(name, spec, str(path), True)
                dependencies.append(dep)

        return dependencies

    @staticmethod
    def _parse_pipfile_dep(name: str, spec: str | dict, source_file: str, is_dev: bool) -> Dependency:
        """Parse a Pipfile dependency specification."""
        if isinstance(spec, str):
            return Dependency(
                name=name,
                version_constraint=spec,
                source_file=source_file,
                is_dev=is_dev,
            )
        elif isinstance(spec, dict):
            version = spec.get("version", "")
            extras = spec.get("extras", [])
            return Dependency(
                name=name,
                version_constraint=version,
                source_file=source_file,
                extras=extras,
                is_dev=is_dev,
            )
        else:
            return Dependency(name=name, source_file=source_file, is_dev=is_dev)

    @staticmethod
    def parse_setup_py(file_path: str | Path) -> list[Dependency]:
        """Parse dependencies from setup.py via basic pattern matching.

        This is a heuristic parser that looks for common patterns.
        It will NOT work for complex setup.py files with computed dependencies.
        """
        path = Path(file_path)
        if not path.exists():
            return []

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []

        dependencies = []

        # Look for install_requires=[...] or install_requires = [...]
        install_requires_match = re.search(
            r"install_requires\s*=\s*\[(.*?)\]",
            content,
            re.DOTALL | re.MULTILINE,
        )

        if install_requires_match:
            deps_str = install_requires_match.group(1)
            # Extract quoted strings
            for match in re.finditer(r'["\']([^"\']+)["\']', deps_str):
                dep_str = match.group(1)
                dep = DependencyParser._parse_requirement_line(dep_str, str(path))
                if dep:
                    dependencies.append(dep)

        return dependencies


def parse_all_dependency_files(root_path: str | Path) -> list[Dependency]:
    """Parse all dependency files in a directory and return combined results.

    Args:
        root_path: Repository root directory.

    Returns:
        List of all discovered dependencies, deduplicated by name.
    """
    root = Path(root_path)
    all_deps = []

    # requirements.txt
    req_file = root / "requirements.txt"
    if req_file.exists():
        all_deps.extend(DependencyParser.parse_requirements_txt(req_file))

    # pyproject.toml
    pyproject_file = root / "pyproject.toml"
    if pyproject_file.exists():
        all_deps.extend(DependencyParser.parse_pyproject_toml(pyproject_file))

    # Pipfile
    pipfile = root / "Pipfile"
    if pipfile.exists():
        all_deps.extend(DependencyParser.parse_pipfile(pipfile))

    # setup.py
    setup_file = root / "setup.py"
    if setup_file.exists():
        all_deps.extend(DependencyParser.parse_setup_py(setup_file))

    # Deduplicate by normalized name, keeping first occurrence
    seen = set()
    unique_deps = []
    for dep in all_deps:
        if dep.normalized_name not in seen:
            seen.add(dep.normalized_name)
            unique_deps.append(dep)

    return unique_deps
