"""Tests for the repository scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.analyzers.scanner import RepositoryScanner, scan_repository


class TestRepositoryScanner:
    """Unit tests for RepositoryScanner."""

    def test_scan_empty_directory(self, tmp_path: Path):
        """Scanning an empty directory returns an empty result."""
        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        assert result.root_path == str(tmp_path.resolve())
        assert result.name == tmp_path.name
        assert result.total_python_files == 0
        assert result.total_files == 0
        assert result.errors == []

    def test_scan_python_files(self, tmp_path: Path):
        """Scanning detects Python files and categorizes them correctly."""
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "utils").mkdir()
        (tmp_path / "utils" / "helper.py").write_text("def helper():\n    pass\n")

        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        assert result.total_python_files == 2
        assert result.total_files == 2

        paths = {f.relative_path for f in result.python_files}
        assert paths == {"main.py", "utils/helper.py"}

        main_file = next(f for f in result.python_files if f.relative_path == "main.py")
        assert main_file.extension == ".py"
        assert main_file.is_python
        assert not main_file.is_init
        assert not main_file.is_config

    def test_excludes_git_and_venv(self, tmp_path: Path):
        """Scanning skips .git and virtual environment directories."""
        (tmp_path / "main.py").write_text("import os\n")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("secret config\n")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib.py").write_text("x = 1\n")

        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        assert result.total_python_files == 1
        assert result.total_files == 1
        paths = {f.relative_path for f in result.python_files}
        assert paths == {"main.py"}
        assert ".git" in result.skipped_dirs
        assert ".venv" in result.skipped_dirs

    def test_excludes_build_artifacts(self, tmp_path: Path):
        """Scanning skips build/dist/cache directories."""
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.cpython-311.pyc").write_bytes(b"\x00")

        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        assert result.total_python_files == 0

    def test_detects_config_files(self, tmp_path: Path):
        """Config files like requirements.txt are categorized."""
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        (tmp_path / "pyproject.toml").write_text("[project]\n")

        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        assert result.total_python_files == 0
        assert len(result.config_files) == 2

        config_paths = {f.relative_path for f in result.config_files}
        assert config_paths == {"requirements.txt", "pyproject.toml"}

    def test_skips_oversized_files(self, tmp_path: Path):
        """Files larger than the max size are skipped."""
        (tmp_path / "big.py").write_text("# big file\n" * 10000)

        scanner = RepositoryScanner(max_file_size_bytes=100)
        result = scanner.scan(tmp_path)

        assert result.total_python_files == 0
        assert len(result.skipped_files) == 1

    def test_binary_file_detection(self, tmp_path: Path):
        """Binary files are skipped even if they have unexpected extensions."""
        (tmp_path / "data.pkl").write_bytes(b"\x80\x04\x95\x01\x00\x00\x00")

        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        assert result.total_files == 0

    def test_scan_nonexistent_directory_raises(self, tmp_path: Path):
        """Scanning a nonexistent path raises FileNotFoundError."""
        scanner = RepositoryScanner()
        with pytest.raises(FileNotFoundError):
            scanner.scan(tmp_path / "does-not-exist")

    def test_scan_file_path_raises(self, tmp_path: Path):
        """Scanning a file (not directory) raises NotADirectoryError."""
        f = tmp_path / "file.txt"
        f.write_text("hello")
        scanner = RepositoryScanner()
        with pytest.raises(NotADirectoryError):
            scanner.scan(f)

    def test_custom_exclude_dirs(self, tmp_path: Path):
        """Additional exclude dirs can be supplied."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x = 1\n")
        (tmp_path / "generated").mkdir()
        (tmp_path / "generated" / "g.py").write_text("y = 2\n")

        scanner = RepositoryScanner(exclude_dirs={"generated"})
        result = scanner.scan(tmp_path)

        assert result.total_python_files == 1
        assert "generated" in result.skipped_dirs

    def test_size_property(self, tmp_path: Path):
        """total_python_size sums the bytes of Python files."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n" * 100)

        scanner = RepositoryScanner()
        result = scanner.scan(tmp_path)

        a_size = (tmp_path / "a.py").stat().st_size
        b_size = (tmp_path / "b.py").stat().st_size
        assert result.total_python_size == a_size + b_size


def test_scan_repository_convenience(tmp_path: Path):
    """The scan_repository convenience function works."""
    (tmp_path / "main.py").write_text("import os\n")
    result = scan_repository(tmp_path)

    assert result.total_python_files == 1
    assert result.name == tmp_path.name