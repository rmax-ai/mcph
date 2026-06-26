# Phase 4: JSON-RPC Protocol Engine

## Context

You are in `~/src/rmax-ai/mcph`. Phases 0-3 are done. Read AGENTS.md.

Existing modules:
- `src/mcph/ast.py` — AST node types (Initialize, CallTool, ReadResource, etc.)
- `src/mcph/parser.py` — parse .mcph → TestFile AST
- `src/mcph/transport/stdio.py` — StdioTransport (async subprocess)
- `src/mcph/transport/http_transport.py` — HttpTransport (httpx)

## What to Build

### `src/mcph/protocol.py`

A JSON-RPC protocol engine that wraps abstract test operations (from the AST)
into compliant JSON-RPC envelopes.

```python
class ProtocolEngine:
    def __init__(self, transport: Transport):
        ...

    async def initialize(self, init: Initialize) -> dict[str, Any]:
        """Send initialize request, return server capabilities."""

    async def send_initialized(self) -> None:
        """Send notifications/initialized after successful initialize."""

    async def list_tools(self) -> dict[str, Any]:
        """Send tools/list, return response result."""

    async def list_prompts(self) -> dict[str, Any]:
        """Send prompts/list, return response result."""

    async def list_resources(self) -> dict[str, Any]:
        """Send resources/list, return response result."""

    async def call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        """Send tools/call, return response result or error."""

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Send resources/read, return response result."""

    async def get_prompt(self, name: str, arguments: dict) -> dict[str, Any]:
        """Send prompts/get, return response result."""

    async def subscribe(self, uri: str) -> dict[str, Any]:
        """Send resources/subscribe, return response result."""

    async def listen(self, notification: str, timeout_ms: int) -> dict[str, Any]:
        """Wait for a notification from the server."""

    async def shutdown(self) -> dict[str, Any]:
        """Send shutdown request and close transport."""
```

Key behaviors:
- **Sequential request IDs** — counter starts at 1, increments per request
- **Every message** includes `"jsonrpc": "2.0"`
- **Distinguish success from error** — if response has `"error"` key, populate
  `is_error` and propagate. If `"result"`, return it
- **Initialize handshake** — sends `initialize` with protocolVersion, clientInfo,
  capabilities → parses server capabilities response → sends `notifications/initialized`
- **Method mapping** — translates AST action types to JSON-RPC method strings:
  `ListTools` → `"tools/list"`, `CallTool` → `"tools/call"`,
  `ReadResource` → `"resources/read"`, etc.
- **Response validation** — checks that response `id` matches request `id`

### `tests/test_protocol.py`

Test with a mock transport (a simple `MockTransport` that records what was sent
and returns canned responses). No real subprocess/HTTP needed.

Tests:
- `test_initialize_handshake` — full init → response → initialized
- `test_request_id_sequencing` — IDs increment (1, 2, 3...)
- `test_jsonrpc_version_in_all_messages` — every message has jsonrpc: "2.0"
- `test_error_response_handling` — responses with "error" key are detected
- `test_list_tools` — sends correct method name
- `test_call_tool` — sends tools/call with name + arguments
- `test_read_resource` — sends resources/read with uri
- `test_get_prompt` — sends prompts/get with name + arguments
- `test_response_id_mismatch` — detects when response id != request id
- `test_shutdown` — sends shutdown, closes transport

## Key Design Decisions

1. **Transport-agnostic** — ProtocolEngine receives any Transport (stdio or HTTP),
   doesn't care about the underlying transport details.
2. **MockTransport** — implement in test file. Simple class that stores sent
   messages and returns pre-configured responses.
3. **No variable resolution yet** — that's Phase 6. Just pass raw values through.

## Verification

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_protocol.py -v
uv run pytest tests/ -v          # full suite — no regressions
```
