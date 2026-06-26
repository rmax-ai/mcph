# Phase 3: Streamable HTTP Transport

## Context

You are in `~/src/rmax-ai/mcph`. Phase 0 (scaffold), Phase 1 (parser/AST),
and Phase 2 (stdio transport) are done. Read AGENTS.md for conventions.

The existing Transport base class is in `src/mcph/transport/__init__.py`.
The stdio transport is in `src/mcph/transport/stdio.py` — use it as a reference
for patterns.

## What to Build

### 1. `src/mcph/transport/http_transport.py`

Implement `HttpTransport` class that extends `Transport` from `mcph.transport`.

```python
class HttpTransport(Transport):
    def __init__(self, url: str, timeout: float = 30.0, headers: dict | None = None):
        ...
```

Key behaviors:
- Uses `httpx.AsyncClient` for HTTP requests
- POSTs JSON-RPC messages to `{url}` (the single MCP endpoint)
- Reads JSON responses from the POST response body
- Tracks `Mcp-Session-Id` response header and sends it back on subsequent requests
- Sets `Accept: application/json, text/event-stream` header
- Sets `Content-Type: application/json` header
- Connection refusal returns a clean `ConnectionError` with the URL, not a raw traceback

### 2. `tests/test_transport_http.py`

Test using a simple HTTP echo server (started as a fixture via `http.server` or a
tiny asyncio HTTP server).

Tests needed:
- `test_connect_and_send_receive` — POST → get response
- `test_mcp_session_id_tracking` — verify session ID is sent back on request 2
- `test_sequential_exchanges` — multiple request/response cycles
- `test_connection_refusal` — gracefully handle unreachable server
- `test_send_before_connect` — raises RuntimeError
- `test_close_is_idempotent` — multiple close() calls are safe

## Key Design Decisions

1. **httpx** — already in dependencies. Use `httpx.AsyncClient` with a context
   manager for proper cleanup.
2. **Session ID tracking** — store `_session_id` as a string, read from
   `response.headers["Mcp-Session-Id"]`, send as `request.headers["Mcp-Session-Id"]`.
3. **Simple request-response** — no SSE streaming in this phase. Just POST and
   read the synchronous JSON response body.
4. **Timeout** — use `httpx.Timeout(self._timeout)` for connect + read timeout.

## Verification

```bash
cd ~/src/rmax-ai/mcph
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_transport_http.py -v
uv run pytest tests/ -v          # full suite — no regressions
```

All tests must pass. Ruff and mypy must be clean.
