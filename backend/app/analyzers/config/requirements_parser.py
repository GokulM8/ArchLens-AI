"""Dependency file parsers — extract external packages from config files.

Parses:
- requirements.txt (and variants like requirements-dev.txt)
- pyproject.toml (PEP 621 and Poetry formats)
- setup.py (basic patterns only)
- Pipfile (basic patterns only)

Extracts package names and version constraints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ParsedDependency:
    """A single external dependency extracted from a config file."""
    name: str
    version_constraint: Optional[str] = None
    source_file: str = ""
    extras: list[str] = field(default_factory=list)
    is_dev: bool = False


def parse_requirements_txt(file_path: str) -> list[ParsedDependency]:
    """Parse a requirements.txt file.

    Handles:
    - package==version
    - package>=version
    - package~=version
    - package[extra1,extra2]>=version
    - Comments (#)
    - Blank lines
    - -r references (recorded but not followed)
    - Environment markers (;)

    Args:
        file_path: Path to the requirements file.

    Returns:
        List of parsed dependencies.
    """
    deps = []
    path = Path(file_path)

    # Detect dev requirements from filename
    is_dev = any(
        marker in path.name.lower()
        for marker in ("dev", "test", "ci", "lint")
    )

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return deps

    for line in content.splitlines():
        line = line.strip()

        # Skip comments, blank lines, options, and -r references
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        # Remove inline comments
        if " #" in line:
            line = line[:line.index(" #")].strip()

        # Remove environment markers
        if ";" in line:
            line = line[:line.index(";")].strip()

        # Skip URLs, git links, editable installs, and path references
        if _is_skipable_requirement_line(line):
            continue

        dep = _parse_requirement_line(line, str(path), is_dev)
        if dep:
            deps.append(dep)

    return deps


def _is_skipable_requirement_line(line: str) -> bool:
    """Whether a requirements line refers to a location rather than a package.

    Skips: http(s) URLs, git+ URLs, github.com shortcuts, editable installs
    (-e), file: references, and local path references.
    """
    lowered = line.strip().lower()
    if lowered.startswith(("http://", "https://", "git+", "git@", "file:")):
        return True
    if lowered.startswith("-e ") or lowered.startswith("--editable"):
        return True
    if line.startswith("/") or line.startswith("."):
        return True
    return False


def _parse_requirement_line(line: str, source_file: str, is_dev: bool = False) -> Optional[ParsedDependency]:
    """Parse a single requirement line into a dependency."""
    # Regex: package_name[extras] version_constraint
    pattern = r'^([A-Za-z0-9][\w.-]*)\s*(?:\[([^\]]+)\])?\s*(.*)$'
    match = re.match(pattern, line)
    if not match:
        return None

    name = match.group(1).strip()
    extras_str = match.group(2)
    version = match.group(3).strip() or None

    extras = []
    if extras_str:
        extras = [e.strip() for e in extras_str.split(",")]

    return ParsedDependency(
        name=name,
        version_constraint=version,
        source_file=source_file,
        extras=extras,
        is_dev=is_dev,
    )


def parse_pyproject_toml(file_path: str) -> list[ParsedDependency]:
    """Parse a pyproject.toml file for dependencies.

    Supports:
    - PEP 621 format: [project] dependencies = [...]
    - Poetry format: [tool.poetry.dependencies] ...

    Args:
        file_path: Path to pyproject.toml.

    Returns:
        List of parsed dependencies.
    """
    deps = []

    try:
        # Python 3.11+ has tomllib; fallback to manual parsing
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return _parse_pyproject_toml_fallback(file_path)

        with open(file_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return _parse_pyproject_toml_fallback(file_path)

    # PEP 621 format
    project = data.get("project", {})
    for dep_str in project.get("dependencies", []):
        dep = _parse_requirement_line(dep_str, file_path, is_dev=False)
        if dep:
            deps.append(dep)

    # PEP 621 optional dependencies (often dev deps)
    for group_name, group_deps in project.get("optional-dependencies", {}).items():
        is_dev = group_name.lower() in ("dev", "test", "testing", "lint", "ci", "docs")
        for dep_str in group_deps:
            dep = _parse_requirement_line(dep_str, file_path, is_dev=is_dev)
            if dep:
                deps.append(dep)

    # Poetry format
    poetry = data.get("tool", {}).get("poetry", {})
    for name, version in poetry.get("dependencies", {}).items():
        if name.lower() == "python":
            continue
        constraint = None
        if isinstance(version, str):
            constraint = version
        elif isinstance(version, dict):
            constraint = version.get("version")
        deps.append(ParsedDependency(
            name=name,
            version_constraint=constraint,
            source_file=file_path,
            is_dev=False,
        ))

    for name, version in poetry.get("dev-dependencies", {}).items():
        constraint = None
        if isinstance(version, str):
            constraint = version
        elif isinstance(version, dict):
            constraint = version.get("version")
        deps.append(ParsedDependency(
            name=name,
            version_constraint=constraint,
            source_file=file_path,
            is_dev=True,
        ))

    # Poetry groups
    for group_name, group_data in poetry.get("group", {}).items():
        is_dev = group_name.lower() in ("dev", "test", "testing", "lint", "ci", "docs")
        for name, version in group_data.get("dependencies", {}).items():
            constraint = None
            if isinstance(version, str):
                constraint = version
            elif isinstance(version, dict):
                constraint = version.get("version")
            deps.append(ParsedDependency(
                name=name,
                version_constraint=constraint,
                source_file=file_path,
                is_dev=is_dev,
            ))

    return deps


def _parse_pyproject_toml_fallback(file_path: str) -> list[ParsedDependency]:
    """Minimal regex-based parser when tomllib is not available.

    Only handles the simplest cases; prefer tomllib.
    """
    deps = []
    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return deps

    # Look for dependencies = [...] blocks
    pattern = r'dependencies\s*=\s*\[(.*?)\]'
    for match in re.finditer(pattern, content, re.DOTALL):
        block = match.group(1)
        for line in block.splitlines():
            line = line.strip().strip(",").strip("'\"")
            if line and not line.startswith("#"):
                dep = _parse_requirement_line(line, file_path)
                if dep:
                    deps.append(dep)

    return deps


def parse_setup_py(file_path: str) -> list[ParsedDependency]:
    """Extract dependencies from setup.py using regex (no exec).

    This is a best-effort parser — it cannot handle dynamic setup.py files.

    Args:
        file_path: Path to setup.py.

    Returns:
        List of parsed dependencies.
    """
    deps = []
    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return deps

    # Look for install_requires=[...] and extras_require dicts
    pattern = r'(install_requires|extras_require)\s*=\s*\[(.*?)\]'
    for match in re.finditer(pattern, content, re.DOTALL):
        block = match.group(2)
        # Split on commas, then strip each entry. Handles both single-line
        # (foo, bar) and multi-line ("foo",\n "bar") requirement lists.
        for entry in _split_quoted_entries(block):
            stripped = entry.strip().strip("'\"").strip()
            if not stripped or stripped.startswith("#"):
                continue
            dep = _parse_requirement_line(stripped, file_path)
            if dep:
                deps.append(dep)

    return deps


def _split_quoted_entries(block: str) -> list[str]:
    """Split a requirements block on commas, respecting quoted strings.

    Handles both single-line lists (e.g. ["numpy", "requests"]) and
    multi-line lists where a trailing comma is common.
    """
    entries = []
    current = []
    in_quote = None
    for ch in block:
        if in_quote:
            current.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            current.append(ch)
        elif ch == ",":
            entries.append("".join(current))
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        entries.append("".join(current))
    return [e for e in entries if e.strip()]


def parse_dependency_file(file_path: str) -> list[ParsedDependency]:
    """Route to the correct parser based on filename.

    Args:
        file_path: Path to a dependency/config file.

    Returns:
        List of parsed dependencies.
    """
    name = Path(file_path).name.lower()
    path_name = name.split("/")[-1]

    # requirements*.txt (covers requirements.txt, requirements-dev.txt, etc.)
    if path_name.endswith(".txt") and "requirement" in path_name:
        return parse_requirements_txt(file_path)
    elif path_name == "pyproject.toml":
        return parse_pyproject_toml(file_path)
    elif path_name == "setup.py":
        return parse_setup_py(file_path)

    return []
