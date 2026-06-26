"""CLI entry point for MCP-Hurl."""

import typer

app = typer.Typer(name="mcph", help="MCP-Hurl: declarative conformance testing for MCP servers")


@app.command()
def run(
    file: str = typer.Argument(..., help="The .mcph test file to execute"),
) -> None:
    """Run a .mcph conformance test suite."""
    typer.echo(f"mcph v0.1.0 — running {file}")
    typer.echo("(runner not yet implemented)")


@app.callback()
def callback() -> None:
    """MCP-Hurl: declarative conformance testing DSL for MCP servers."""


if __name__ == "__main__":
    app()
