"""Tests for Streamable HTTP transport."""

import json
import re
import socket
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from mcph.transport.http_transport import HttpTransport


@dataclass
class _HttpServerState:
    received_headers: list[dict[str, str]] = field(default_factory=list)
    received_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _HttpServerFixture:
    url: str
    state: _HttpServerState


@pytest.fixture
def http_echo_server() -> _HttpServerFixture:
    """Start a tiny HTTP JSON echo server in a background thread."""
    state = _HttpServerState()
    session_id = "session-123"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            request_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(request_body)

            state.received_headers.append(dict(self.headers.items()))
            state.received_messages.append(payload)

            response_payload = {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"echo": payload.get("params", {})},
            }
            response_body = json.dumps(response_payload).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            if len(state.received_messages) == 1:
                self.send_header("Mcp-Session-Id", session_id)
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, _format: str, *args: Any) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield _HttpServerFixture(url=f"http://{host}:{port}/mcp", state=state)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _unused_url() -> str:
    """Return an HTTP URL for a currently unbound local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        _, port = sock.getsockname()
    return f"http://127.0.0.1:{port}/mcp"


@pytest.mark.asyncio
async def test_connect_and_send_receive(http_echo_server: _HttpServerFixture) -> None:
    """POST request produces a JSON response."""
    transport = HttpTransport(http_echo_server.url, timeout=5.0)
    await transport.connect()

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "test/ping",
        "params": {"key": "value"},
    }
    await transport.send(request)
    response = await transport.receive()

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["echo"] == {"key": "value"}

    headers = http_echo_server.state.received_headers[0]
    assert headers["Accept"] == "application/json, text/event-stream"
    assert headers["Content-Type"] == "application/json"

    await transport.close()


@pytest.mark.asyncio
async def test_mcp_session_id_tracking(http_echo_server: _HttpServerFixture) -> None:
    """Session id from response 1 is sent on request 2."""
    transport = HttpTransport(http_echo_server.url, timeout=5.0)
    await transport.connect()

    await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test/first"})
    _ = await transport.receive()

    await transport.send({"jsonrpc": "2.0", "id": 2, "method": "test/second"})
    _ = await transport.receive()

    assert http_echo_server.state.received_headers[1]["Mcp-Session-Id"] == "session-123"

    await transport.close()


@pytest.mark.asyncio
async def test_sequential_exchanges(http_echo_server: _HttpServerFixture) -> None:
    """Multiple request-response cycles succeed in order."""
    transport = HttpTransport(http_echo_server.url, timeout=5.0)
    await transport.connect()

    for request_id in range(5):
        await transport.send({"jsonrpc": "2.0", "id": request_id, "method": "test/seq"})
        response = await transport.receive()
        assert response["id"] == request_id

    assert len(http_echo_server.state.received_messages) == 5
    await transport.close()


@pytest.mark.asyncio
async def test_connection_refusal() -> None:
    """Unreachable endpoint raises a clean ConnectionError."""
    url = _unused_url()
    transport = HttpTransport(url, timeout=1.0)
    await transport.connect()

    with pytest.raises(ConnectionError, match=re.escape(url)):
        await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test/ping"})

    await transport.close()


@pytest.mark.asyncio
async def test_send_before_connect() -> None:
    """send() before connect() raises RuntimeError."""
    transport = HttpTransport("http://127.0.0.1:9999/mcp")
    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test/ping"})


@pytest.mark.asyncio
async def test_close_is_idempotent(http_echo_server: _HttpServerFixture) -> None:
    """Calling close() multiple times is safe."""
    transport = HttpTransport(http_echo_server.url)
    await transport.connect()

    await transport.close()
    await transport.close()

    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test/ping"})
