"""Tests for mcph CLI behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from mcph import __version__
from mcph.cli import app

runner = CliRunner()


def _write_suite(path: Path, source: str) -> str:
    path.write_text(dedent(source).strip() + "\n", encoding="utf-8")
    return str(path)


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"mcph v{__version__}" in result.stdout


def test_run_help_includes_env_flag() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--env" in result.stdout


def test_run_missing_file_error_message() -> None:
    result = runner.invoke(app, ["run", "missing.mcph"])
    assert result.exit_code != 0
    output = f"{result.stdout}\n{result.stderr}"
    assert ".mcph file not found: missing.mcph" in output


def test_run_env_sets_variables(tmp_path: Path) -> None:
    echo_script = (Path(__file__).parent.parent / "examples" / "echo-server.py").resolve()
    suite_path = _write_suite(
        tmp_path / "env_suite.mcph",
        f"""
        CONNECT stdio "{sys.executable} {echo_script}"
        INITIALIZE protocolVersion="2025-03-26"
        CALL "echo" {{ "token": "{{{{TOKEN}}}}" }}
        ASSERT STATUS == 200
        ASSERT result.echo.token == "abc"
        SHUTDOWN
        """,
    )

    result = runner.invoke(app, ["run", suite_path, "--env", "TOKEN=abc"])
    assert result.exit_code == 0, result.stdout
