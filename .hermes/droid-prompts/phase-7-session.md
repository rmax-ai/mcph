# Phase 7: Session Manager & Runtime

## Context

You are in `~/src/rmax-ai/mcph`. Phases 0-6 done (121 tests). All modules exist. Read AGENTS.md.

Existing modules:
- `src/mcph/parser.py` — `parse(text) → TestFile`
- `src/mcph/transport/stdio.py` — `StdioTransport`
- `src/mcph/transport/http_transport.py` — `HttpTransport`
- `src/mcph/protocol.py` — `ProtocolEngine`
- `src/mcph/assertion.py` — `AssertionEngine`, `AssertionError`
- `src/mcph/capture.py` — `CaptureRegistry`
- `src/mcph/ast.py` — all AST node types

## What to Build

### `src/mcph/session.py`

```python
@dataclass
class SessionConfig:
    continue_on_failure: bool = False
    timeout: float = 30.0
    verbose: bool = False

class Session:
    def __init__(self, test_file: TestFile, config: SessionConfig):
        ...

    async def run(self) -> list[StepResult]:
        """Execute the entire test file. Returns list of step results."""

@dataclass
class StepResult:
    step: ASTNode
    passed: bool
    message: str
    duration_ms: float
    error: Exception | None = None
```

### Execution flow

1. **Parse** — already done (TestFile passed in)
2. **Connect** — first step must be `Connect`. Create the appropriate transport
   (StdioTransport or HttpTransport based on `connect.transport`).
3. **Initialize** — if an `Initialize` step is present, run the handshake:
   `ProtocolEngine.initialize()` → check response → `send_initialized()`.
   Store server capabilities for later REQUIRE_CAPABILITY checks.
4. **Execute steps sequentially** — for each AST node in `test_file.steps`:
   - `Connect` — connect transport (already handled in step 2)
   - `Initialize` — already handled in step 3
   - `SetVar` — capture_registry.set(name, value)
   - `Header` — store header for HTTP transport (set on transport)
   - `ListTools` → `protocol.list_tools()` → assert on response
   - `ListPrompts` → `protocol.list_prompts()` → assert
   - `ListResources` → `protocol.list_resources()` → assert
   - `CallTool` → `protocol.call_tool(name, arguments)` → assert
   - `ReadResource` → `protocol.read_resource(uri)` → assert
   - `GetPrompt` → `protocol.get_prompt(name, arguments)` → assert
   - `Subscribe` → `protocol.subscribe(uri)` → assert
   - `Listen` → `protocol.listen(notification, timeout_ms)` → assert
   - `Shutdown` → `protocol.shutdown()` → assert
   - `RequireCapability` — check if server capabilities include this capability.
     If NOT present, skip all subsequent steps until the next `RequireCapability`
     or end of file. Record as "skipped" not "failed".
   - `Assert` — evaluate assertion against the LAST response received.
     `AssertionEngine.evaluate(assertion, last_response)`.
   - `Capture` — `CaptureRegistry.capture(capture, last_response)`.
5. **Resolve variables** — before sending any request that has arguments (CallTool,
   ReadResource, GetPrompt), resolve templates in the arguments via
   `capture_registry.resolve(arguments)`.
6. **Error handling**:
   - `continue_on_failure=True` — log failure, continue to next step
   - `continue_on_failure=False` (default) — stop on first failure
   - Transport errors — record as failure with transport error message
7. **Cleanup** — always close transport, even on error

### `src/mcph/runner.py`

Top-level convenience function:

```python
async def run_file(path: str, config: SessionConfig | None = None) -> list[StepResult]:
    """Parse and execute a .mcph file."""

def run_file_sync(path: str, config: SessionConfig | None = None) -> list[StepResult]:
    """Sync wrapper for CLI use."""
```

### `tests/test_runner.py`

Minimal integration test using the echo server approach:

```python
# Create a minimal .mcph string and run it against an echo server
mcph_source = '''
CONNECT stdio "python echo_server.py"
INITIALIZE protocolVersion="2025-03-26"
LIST tools
ASSERT STATUS == 200
SHUTDOWN
'''
```

Write the echo server as a temp file that speaks enough MCP to satisfy the
runner (responds to initialize, tools/list, etc.).

Tests:
- `test_minimal_run_stdio` — CONNECT → INITIALIZE → LIST tools → SHUTDOWN
- `test_require_capability_skips` — REQUIRE_CAPABILITY with unsupported feature skips steps
- `test_continue_on_failure` — all steps run even when some fail
- `test_hard_failure_stops` — default mode stops on first failure
- `test_variable_resolution_in_call` — SET + CALL with {{var}}, verify template resolved

## Key Design Decisions

1. **Last response tracking** — `ASSERT` and `CAPTURE` always operate on the
   most recent response from the protocol engine. This is the MCP semantics:
   each request produces exactly one response.
2. **Capability gating** — `REQUIRE_CAPABILITY prompts` checks
   `server_capabilities.get("prompts")`. If falsy, skip until next
   `REQUIRE_CAPABILITY` or EOF.
3. **Template resolution in requests** — resolve templates BEFORE sending to
   protocol engine. The protocol engine receives plain values.
4. **Echo server fixture** — write a small Python script that handles:
   initialize → returns fake capabilities, tools/list → returns empty list,
   notifications/initialized → no-op. Run as subprocess.

## Verification

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_runner.py -v
uv run pytest tests/ -v          # full suite — no regressions
```
