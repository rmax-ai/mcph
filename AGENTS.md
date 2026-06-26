# MCP-Hurl (Mcph)

Declarative conformance testing DSL for MCP servers. Hurl-inspired `.mcph` syntax, custom Python async runner.

## Project Structure

```
src/mcph/
  cli.py          — typer CLI entry point
  parser.py       — .mcph lexer/parser/compiler → AST
  ast.py          — AST node definitions
  exceptions.py   — parse and runtime exceptions
  session.py      — environment & session manager
  transport/      — transport registry
    __init__.py
    stdio.py      — subprocess-based stdio transport
    http_transport.py — Streamable HTTP transport
  protocol.py     — JSON-RPC frame handler
  assertion.py    — assertion engine (JSONPath, regex, schema)
  capture.py      — variable capture registry
  runner.py       — test execution runtime
  reporter.py     — JUnit/JSON/console reporters

tests/
  test_parser.py
  test_transport_stdio.py
  test_transport_http.py
  test_protocol.py
  test_assertion.py
  test_capture.py
  test_runner.py
  test_reporter.py
  integration/
    test_e2e_stdio.py

examples/
  echo-server.py      — minimal stdio MCP server
  conformance.mcph    — full conformance suite
```

## Conventions

- Type hints mandatory. mypy strict mode.
- Ruff for lint + format. Line length 100.
- pytest with `asyncio_mode = "auto"`.
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Core dependencies: typer, anyio, jsonpath-ng, jsonschema, httpx, rich.

## Key Design Decisions

- **Python** over Rust/Go: JSON Schema ecosystem, async I/O maturity, user's stack.
- **Custom runner** over Hurl extension: stdio subprocess lifecycle + multiplexed JSON-RPC is a fundamentally different execution model than HTTP request/response chains.
- **Hurl-inspired syntax**: `CONNECT`, `INITIALIZE`, `ASSERT`, `CAPTURE` keywords; `[Asserts]`-style assertion blocks borrowed from Hurl's design.
- **AST-first compilation**: Parse → AST → execute. Enables future optimizations (validation passes, compilation to other formats).
