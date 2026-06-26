"""CLI entry point for MCP-Hurl."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer

from mcph.ast import Connect, TestFile
from mcph.parser import parse
from mcph.reporter import write_reports
from mcph.session import Session, SessionConfig

app = typer.Typer(name="mcph", help="MCP-Hurl: declarative conformance testing for MCP servers")


def _find_connect_step(file_path: str, test_file: TestFile) -> Connect:
    for step in test_file.steps:
        if isinstance(step, Connect):
            return step
    raise typer.BadParameter(f"No CONNECT step found in {file_path}")


@app.command()
def run(
    file: str = typer.Argument(...),
    transport: str = typer.Option("stdio", help="Transport: stdio or http"),
    command: str | None = typer.Option(None, help="Server command (stdio)"),
    url: str | None = typer.Option(None, help="Server URL (http)"),
    reporter: list[str] = typer.Option(["console"], help="Reporters: console, junit, json"),
    timeout: float = typer.Option(30.0, help="Timeout in seconds"),
    continue_on_failure: bool = typer.Option(False, help="Continue after failures"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Run a .mcph conformance test suite."""
    if command is not None and url is not None:
        raise typer.BadParameter("Use either --command or --url, not both.")
    if transport not in {"stdio", "http"}:
        raise typer.BadParameter("Transport must be 'stdio' or 'http'.")

    source = Path(file).read_text(encoding="utf-8")
    test_file = parse(source)
    connect_step = _find_connect_step(file, test_file)

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
def callback() -> None:
    """MCP-Hurl: declarative conformance testing DSL for MCP servers."""


if __name__ == "__main__":
    app()
