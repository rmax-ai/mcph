"""CLI entry point for MCP-Hurl."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer

from mcph import __version__
from mcph.ast import Connect, SetVar, TestFile
from mcph.parser import parse
from mcph.reporter import write_reports
from mcph.session import Session, SessionConfig

app = typer.Typer(name="mcph", help="MCP-Hurl: declarative conformance testing for MCP servers")


def _find_connect_step(file_path: str, test_file: TestFile) -> Connect:
    for step in test_file.steps:
        if isinstance(step, Connect):
            return step
    raise typer.BadParameter(f"No CONNECT step found in {file_path}")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mcph v{__version__}")
        raise typer.Exit()


def _parse_env_flags(values: list[str]) -> list[SetVar]:
    env_steps: list[SetVar] = []
    for raw in values:
        if "=" not in raw:
            raise typer.BadParameter(
                f"Invalid --env value '{raw}'. Expected KEY=VALUE format.",
            )
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter(
                f"Invalid --env value '{raw}'. KEY cannot be empty.",
            )
        env_steps.append(SetVar(line_number=0, variable=key, value=value))
    return env_steps


@app.command()
def run(
    file: str = typer.Argument(..., help="Path to a .mcph suite file"),
    transport: str = typer.Option("stdio", help="Transport override: stdio or http"),
    command: str | None = typer.Option(None, help="Server command override for stdio transport"),
    url: str | None = typer.Option(None, help="Server URL override for http transport"),
    reporter: list[str] = typer.Option(
        ["console"], help="Reporters to write: console, junit, json"
    ),
    timeout: float = typer.Option(30.0, help="Per-request timeout in seconds"),
    continue_on_failure: bool = typer.Option(False, help="Continue running steps after failures"),
    verbose: bool = typer.Option(False, help="Enable verbose runtime logging"),
    env: list[str] = typer.Option(
        [],
        "--env",
        help="Set a variable before execution (KEY=VALUE). Repeatable.",
    ),
) -> None:
    """Run a .mcph conformance test suite."""
    if command is not None and url is not None:
        raise typer.BadParameter("Use either --command or --url, not both.")
    if transport not in {"stdio", "http"}:
        raise typer.BadParameter("Transport must be 'stdio' or 'http'.")

    suite_path = Path(file)
    if not suite_path.is_file():
        raise typer.BadParameter(f".mcph file not found: {file}")

    source = suite_path.read_text(encoding="utf-8")
    test_file = parse(source)
    connect_step = _find_connect_step(file, test_file)
    env_steps = _parse_env_flags(env)
    if env_steps:
        connect_index = test_file.steps.index(connect_step)
        insertion_index = connect_index + 1
        test_file.steps = [
            *test_file.steps[:insertion_index],
            *env_steps,
            *test_file.steps[insertion_index:],
        ]

    transport_was_explicit = any(
        arg == "--transport" or arg.startswith("--transport=") for arg in sys.argv[1:]
    )
    if transport_was_explicit:
        connect_step.transport = transport

    if command is not None:
        connect_step.transport = "stdio"
        connect_step.target = command
    elif url is not None:
        connect_step.transport = "http"
        connect_step.target = url

    config = SessionConfig(
        continue_on_failure=continue_on_failure,
        timeout=timeout,
        verbose=verbose,
    )
    session = Session(test_file=test_file, config=config)
    results = asyncio.run(session.run())

    write_reports(results=results, reporters=reporter, output_dir=".")

    has_failures = any(not result.passed for result in results)
    sys.exit(1 if has_failures else 0)


@app.callback()
def callback(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show mcph version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """MCP-Hurl: declarative conformance testing DSL for MCP servers."""


if __name__ == "__main__":
    app()
