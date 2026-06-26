# Phase 9+10: CLI Polish, Integration Tests, Example Suite

## Context

You are in `~/src/rmax-ai/mcph`. All core phases done (134 tests). Read AGENTS.md.

## Phase 9: CLI Polish

### `src/mcph/cli.py` additions

- `--version` flag showing `mcph v0.1.0`
- `--env KEY=VALUE` flag for passing variables (stored in CaptureRegistry via SET)
  - Multiple `--env` allowed: `--env TOKEN=abc --env HOST=prod`
- `mcph run --help` shows all flags with descriptions
- Nice error message when .mcph file not found

### `scripts/build.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
# Build a single-binary distribution using PyInstaller
uv run pyinstaller --onefile --name mcph src/mcph/cli.py
echo "Binary: dist/mcph"
```

Add `pyinstaller` to dev dependencies in `pyproject.toml`.

Don't actually run the build in CI — just verify the script is syntactically valid (`bash -n`).

## Phase 10: Integration Tests & Example Suite

### `examples/echo-server.py`

A minimal MCP stdio server that:
- Reads JSON-RPC lines from stdin
- Responds to `initialize` with serverInfo + capabilities (tools, resources, prompts)
- Responds to `tools/list` with a single tool: `echo`
- Responds to `tools/call` with name="echo" by echoing arguments back
- Responds to `prompts/list` with a single prompt
- Responds to `resources/list` with a single resource
- Responds to `shutdown` and exits
- Logs to stderr

This is a complete, working MCP server for testing. It must implement the full
initialize → initialized handshake sequence.

### `examples/conformance.mcph`

The full conformance suite from the design doc (section 8), adapted to test
against the echo server. Key sections:

```mcph
# MCP-Hurl Conformance Suite
# Target: Echo Server

CONNECT stdio "python examples/echo-server.py"
INITIALIZE protocolVersion="2025-03-26"
CLIENT name="McphTest" version="1.0.0"
  CAPABILITIES roots=true sampling=true

ASSERT STATUS == 200
ASSERT serverInfo.name == "McphEchoServer"

LIST tools
ASSERT STATUS == 200
ASSERT tools COUNT >= 1
ASSERT tools[*] EXISTS name == "echo"

CALL "echo" { "message": "hello world" }
ASSERT STATUS == 200
ASSERT isError == false

REQUIRE_CAPABILITY prompts
LIST prompts
ASSERT STATUS == 200

REQUIRE_CAPABILITY resources
LIST resources
ASSERT STATUS == 200

SHUTDOWN
```

### `tests/integration/test_e2e_stdio.py`

End-to-end test: run `conformance.mcph` against the echo server.

```python
@pytest.mark.asyncio
async def test_e2e_conformance_suite():
    """Run the conformance.mcph suite against echo-server.py."""
    import pathlib
    suite_path = pathlib.Path(__file__).parent.parent.parent / "examples" / "conformance.mcph"
    config = SessionConfig(timeout=10.0)
    results = await run_file(str(suite_path), config)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"E2E suite had failures: {failures}"
```

### Update `pyproject.toml`

Add `pyinstaller` to dev deps:
```toml
dev = [
    ...
    "pyinstaller>=6.0",
]
```

## Key Design Decisions

1. **Echo server is a real MCP server** — not a mock. It speaks the full
   initialize → initialized protocol.
2. **Conformance suite is self-documenting** — comments explain each phase.
3. **E2E test runs in CI** — uses the echo server as a subprocess.

## Verification

```bash
uv sync --all-extras
uv run ruff check src/ tests/ examples/
uv run mypy src/
uv run pytest tests/ -v
bash -n scripts/build.sh
python examples/echo-server.py &  # verify it starts
```
