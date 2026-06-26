"""Tests for JSON-RPC protocol engine."""

from __future__ import annotations

from typing import Any

import pytest

from mcph.ast import Initialize
from mcph.protocol import ProtocolEngine
from mcph.transport import Transport


class MockTransport(Transport):
    """Simple mock transport with canned receive responses."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self._responses = list(responses or [])
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def send(self, message: dict[str, Any]) -> None:
        self.sent_messages.append(message)

    async def receive(self) -> dict[str, Any]:
        if not self._responses:
            raise RuntimeError("No mock response configured")
        return self._responses.pop(0)

    async def close(self) -> None:
        self.closed = True


def _ok_response(request_id: int, result: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result or {},
    }


@pytest.mark.asyncio
async def test_initialize_handshake() -> None:
    """initialize request followed by notifications/initialized."""
    transport = MockTransport(
        responses=[
            _ok_response(
                1,
                {
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "Mock Server", "version": "1.0.0"},
                },
            )
        ]
    )
    engine = ProtocolEngine(transport)
    init = Initialize(
        line_number=1,
        protocol_version="2025-03-26",
        client_name="Mcph",
        client_version="1.0.0",
        capabilities={"roots": True},
    )

    capabilities = await engine.initialize(init)
    await engine.send_initialized()

    assert capabilities == {"tools": {"listChanged": True}}
    assert transport.sent_messages[0]["method"] == "initialize"
    assert transport.sent_messages[0]["params"]["protocolVersion"] == "2025-03-26"
    assert transport.sent_messages[0]["params"]["clientInfo"] == {
        "name": "Mcph",
        "version": "1.0.0",
    }
    assert transport.sent_messages[0]["params"]["capabilities"] == {"roots": True}
    assert transport.sent_messages[1]["method"] == "notifications/initialized"


@pytest.mark.asyncio
async def test_request_id_sequencing() -> None:
    """IDs increment 1,2,3 across consecutive requests."""
    transport = MockTransport(
        responses=[
            _ok_response(1, {"tools": []}),
            _ok_response(2, {"prompts": []}),
            _ok_response(3, {"resources": []}),
        ]
    )
    engine = ProtocolEngine(transport)

    await engine.list_tools()
    await engine.list_prompts()
    await engine.list_resources()

    sent_ids = [message["id"] for message in transport.sent_messages]
    assert sent_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_jsonrpc_version_in_all_messages() -> None:
    """Every outgoing message includes jsonrpc: 2.0."""
    transport = MockTransport(responses=[_ok_response(1, {"tools": []})])
    engine = ProtocolEngine(transport)

    await engine.list_tools()
    await engine.send_initialized()

    assert all(message["jsonrpc"] == "2.0" for message in transport.sent_messages)


@pytest.mark.asyncio
async def test_error_response_handling() -> None:
    """JSON-RPC error response is surfaced with is_error=True."""
    transport = MockTransport(
        responses=[
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32601, "message": "Method not found"},
            }
        ]
    )
    engine = ProtocolEngine(transport)

    result = await engine.call_tool("does_not_exist", {})

    assert result["is_error"] is True
    assert result["error"]["code"] == -32601
    assert result["error"]["message"] == "Method not found"


@pytest.mark.asyncio
async def test_list_tools() -> None:
    """list_tools sends tools/list."""
    transport = MockTransport(responses=[_ok_response(1, {"tools": [{"name": "run_sql"}]})])
    engine = ProtocolEngine(transport)

    result = await engine.list_tools()

    assert result == {"tools": [{"name": "run_sql"}]}
    assert transport.sent_messages[0]["method"] == "tools/list"


@pytest.mark.asyncio
async def test_call_tool() -> None:
    """call_tool sends tools/call with name and arguments."""
    transport = MockTransport(responses=[_ok_response(1, {"content": []})])
    engine = ProtocolEngine(transport)

    await engine.call_tool("run_sql", {"query": "SELECT 1"})

    assert transport.sent_messages[0]["method"] == "tools/call"
    assert transport.sent_messages[0]["params"] == {
        "name": "run_sql",
        "arguments": {"query": "SELECT 1"},
    }


@pytest.mark.asyncio
async def test_read_resource() -> None:
    """read_resource sends resources/read with uri."""
    transport = MockTransport(responses=[_ok_response(1, {"contents": []})])
    engine = ProtocolEngine(transport)

    await engine.read_resource("file:///tmp/readme.md")

    assert transport.sent_messages[0]["method"] == "resources/read"
    assert transport.sent_messages[0]["params"] == {"uri": "file:///tmp/readme.md"}


@pytest.mark.asyncio
async def test_get_prompt() -> None:
    """get_prompt sends prompts/get with name and arguments."""
    transport = MockTransport(responses=[_ok_response(1, {"description": "ok"})])
    engine = ProtocolEngine(transport)

    await engine.get_prompt("write_summary", {"topic": "mcp"})

    assert transport.sent_messages[0]["method"] == "prompts/get"
    assert transport.sent_messages[0]["params"] == {
        "name": "write_summary",
        "arguments": {"topic": "mcp"},
    }


@pytest.mark.asyncio
async def test_response_id_mismatch() -> None:
    """Mismatched response id is rejected."""
    transport = MockTransport(responses=[_ok_response(99, {"tools": []})])
    engine = ProtocolEngine(transport)

    with pytest.raises(ValueError, match="Response id mismatch"):
        await engine.list_tools()


@pytest.mark.asyncio
async def test_shutdown() -> None:
    """shutdown sends method and closes transport."""
    transport = MockTransport(responses=[_ok_response(1, {})])
    engine = ProtocolEngine(transport)

    result = await engine.shutdown()

    assert result == {}
    assert transport.sent_messages[0]["method"] == "shutdown"
    assert transport.closed is True
