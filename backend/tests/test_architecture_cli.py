"""Integration tests for CLI analyze command generating architecture.json."""

import os
import tempfile
import pytest
from click.testing import CliRunner
from app.cli import cli


def test_cli_analyze_produces_architecture_json():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(
            cli,
            ["analyze", "../examples/fastapi_project", "-o", tmpdir],
        )

        assert result.exit_code == 0
        assert "Components:" in result.output
        assert "Architecture:" in result.output

        assert os.path.exists(os.path.join(tmpdir, "analysis.json"))
        assert os.path.exists(os.path.join(tmpdir, "graph.json"))
        assert os.path.exists(os.path.join(tmpdir, "architecture.json"))
