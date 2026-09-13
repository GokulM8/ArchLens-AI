"""Repository scanner — walks a project directory and identifies files to analyze.

This is the first step in the analysis pipeline. It produces a manifest of
Python source files and configuration files, filtering out directories and
files that should not be analyzed (VCS directories, virtual environments,
build artifacts, binary files).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable


# Directories to always skip
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".idea",
    ".vscode",
    ".svn",
    ".hg",
    "site-packages",
})

# Configuration/dependency files we want to parse
CONFIG_FILES: frozenset[str] = frozenset({
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "setup.py",
    "setup.cfg",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env",
    ".env.example",
})

# Default max file size: 1MB
DEFAULT_MAX_FILE_SIZE_BYTES = 1024 * 1024


# Environment overrides so the documented ARCHLENS_* knobs actually work.
# ARCHLENS_MAX_FILE_SIZE_KB sets the per-file cap (Kerberos bytes are 1024*KB).
_env_max_kb = os.getenv("ARCHLENS_MAX_FILE_SIZE_KB")
if _env_max_kb:
    try:
        DEFAULT_MAX_FILE_SIZE_BYTES = int(_env_max_kb) * 1024
    except ValueError:
        # Invalid value → keep the safe built-in default.
        pass

_env_excludes = os.getenv("ARCHLENS_EXCLUDE_PATTERNS")
if _env_excludes:
    extra = {p.strip() for p in _env_excludes.split(",") if p.strip()}
    if extra:
        DEFAULT_EXCLUDE_DIRS = frozenset(DEFAULT_EXCLUDE_DIRS) | frozenset(extra)


@dataclass
class ScannedFile:
    """A single file discovered during scanning."""
    absolute_path: str
    relative_path: str
    size_bytes: int
    extension: str
    is_python: bool
    is_config: bool
    is_init: bool


@dataclass
class ScanResult:
    """Result of scanning a repository directory."""
    root_path: str
    name: str
    python_files: list[ScannedFile] = field(default_factory=list)
    config_files: list[ScannedFile] = field(default_factory=list)
    other_files: list[ScannedFile] = field(default_factory=list)
    skipped_dirs: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_python_files(self) -> int:
        return len(self.python_files)

    @property
    def total_files(self) -> int:
        return len(self.python_files) + len(self.config_files) + len(self.other_files)

    @property
    def total_python_size(self) -> int:
        return sum(f.size_bytes for f in self.python_files)


class RepositoryScanner:
    """Walks a project directory and identifies files for analysis.

    The scanner applies exclusion rules to skip irrelevant directories
    (VCS, virtual environments, build artifacts) and large/binary files.
    It categorizes discovered files as Python source, configuration, or other.
    """

    def __init__(
        self,
        exclude_dirs: Optional[set[str]] = None,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
        extra_exclude_patterns: Optional[set[str]] = None,
        verbose: bool = False,
        progress_callback: Optional[Callable] = None,
    ):
        self.exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
        if exclude_dirs:
            self.exclude_dirs.update(exclude_dirs)
        if extra_exclude_patterns:
            self.exclude_dirs.update(extra_exclude_patterns)
        self.max_file_size_bytes = max_file_size_bytes
        self.verbose = verbose
        self.progress_callback = progress_callback

    def scan(self, root_path: str | Path) -> ScanResult:
        """Scan a directory and return categorized file listings.

        Args:
            root_path: Path to the repository root directory.

        Returns:
            ScanResult with categorized files and metadata.

        Raises:
            FileNotFoundError: If root_path does not exist.
            NotADirectoryError: If root_path is not a directory.
        """
        root = Path(root_path).resolve()

        if not root.exists():
            raise FileNotFoundError(f"Path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {root}")

        result = ScanResult(
            root_path=str(root),
            name=root.name,
        )

        if self.verbose:
            print(f"🔍 Scanning repository: {root}")
            print(f"📁 Root directory: {root.name}")
            print(f"📊 Max file size: {self.max_file_size_bytes / (1024*1024):.1f} MB")
            print(f"⚡ Verbose mode: {'enabled' if self.verbose else 'disabled'}")

        self._walk(root, root, result)

        if self.verbose:
            print(f"\n✅ Scan complete: {result.total_files} total files")
            print(f"   Python files: {result.total_python_files}")
            print(f"   Config files: {len(result.config_files)}")
            print(f"   Other files: {len(result.other_files)}")
            print(f"   Skipped dirs: {len(result.skipped_dirs)}")
            print(f"   Skipped files: {len(result.skipped_files)}")
            print(f"   Errors: {len(result.errors)}")
            if result.errors:
                print("   Error details:")
                for error in result.errors:
                    print(f"     - {error}")

        return result

    def _walk(self, current: Path, root: Path, result: ScanResult) -> None:
        """Recursively walk the directory tree."""
        try:
            entries = sorted(current.iterdir(), key=lambda e: e.name)
        except PermissionError:
            result.errors.append(f"Permission denied: {current}")
            if self.verbose:
                print(f"⚠️  Permission denied: {current}")
            return

        if self.verbose:
            print(f"📂 Exploring: {current.relative_to(root)}")

        for entry in entries:
            if entry.is_dir():
                if self._should_exclude_dir(entry.name):
                    result.skipped_dirs.append(str(entry.relative_to(root)))
                    if self.verbose:
                        print(f"⏭️  Skipping directory: {entry.name}")
                    continue
                self._walk(entry, root, result)

            elif entry.is_file():
                scanned = self._process_file(entry, root, result)
                if scanned is None:
                    continue

                if scanned.is_python:
                    result.python_files.append(scanned)
                elif scanned.is_config:
                    result.config_files.append(scanned)
                else:
                    result.other_files.append(scanned)

            # Progress callback every 100 files for large directories
            if self.progress_callback and len(result.python_files) % 100 == 0:
                self.progress_callback({
                    'files_found': len(result.python_files) + len(result.config_files) + len(result.other_files),
                    'current_path': str(current.relative_to(root)),
                    'python_files': len(result.python_files),
                    'config_files': len(result.config_files),
                    'other_files': len(result.other_files)
                })

    def _should_exclude_dir(self, dirname: str) -> bool:
        """Check if a directory should be excluded."""
        if dirname in self.exclude_dirs:
            return True
        # Handle glob-style patterns like *.egg-info
        for pattern in self.exclude_dirs:
            if pattern.startswith("*") and dirname.endswith(pattern[1:]):
                return True
        return False

    def _process_file(
        self, path: Path, root: Path, result: ScanResult
    ) -> Optional[ScannedFile]:
        """Process a single file and return its metadata, or None if skipped."""
        try:
            size = path.stat().st_size
        except OSError:
            result.errors.append(f"Cannot stat: {path}")
            return None

        if size > self.max_file_size_bytes:
            result.skipped_files.append(
                f"{path.relative_to(root)} (exceeds {self.max_file_size_bytes} bytes)"
            )
            return None

        if self._is_likely_binary(path, size):
            return None

        relative = str(path.relative_to(root))
        extension = path.suffix.lower()

        return ScannedFile(
            absolute_path=str(path),
            relative_path=relative,
            size_bytes=size,
            extension=extension,
            is_python=extension == ".py",
            is_config=path.name in CONFIG_FILES,
            is_init=path.name == "__init__.py",
        )

    def _is_likely_binary(self, path: Path, size: int) -> bool:
        """Heuristic check for binary files by reading the first chunk."""
        if size == 0:
            return False

        binary_extensions = {
            ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
            ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
            ".woff", ".woff2", ".ttf", ".eot",
            ".zip", ".tar", ".gz", ".bz2", ".xz",
            ".db", ".sqlite", ".sqlite3",
            ".pkl", ".pickle", ".npy", ".npz",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        }
        if path.suffix.lower() in binary_extensions:
            return True

        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
            # If more than 10% of the first chunk is null bytes, treat as binary
            if b"\x00" in chunk:
                null_ratio = chunk.count(b"\x00") / len(chunk)
                return null_ratio > 0.1
        except OSError:
            return True

        return False


def scan_repository(
    path: str | Path,
    exclude_dirs: Optional[set[str]] = None,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> ScanResult:
    """Convenience function to scan a repository.

    Args:
        path: Path to the repository root.
        exclude_dirs: Additional directories to exclude.
        max_file_size_bytes: Maximum file size to process.

    Returns:
        ScanResult with categorized files.
    """
    scanner = RepositoryScanner(
        exclude_dirs=exclude_dirs,
        max_file_size_bytes=max_file_size_bytes,
    )
    return scanner.scan(path)
