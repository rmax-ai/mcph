"""Tests for the stdio transport."""

import sys

import pytest

from mcph.transport.stdio import StdioTransport

# ── Echo server script ───────────────────────────────────────────────────────

ECHO_SERVER = """import json, sys

# MCP stdio echo server: reads JSON-RPC lines from stdin, echoes back on stdout.
# Stderr is used for logging (should not contaminate protocol stream).

def log(msg: str) -> None:
    print(f"[echo-server] {msg}", file=sys.stderr, flush=True)

log("started")
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        log(f"invalid json: {line[:100]}")
        continue

    log(f"received: {msg.get('method', msg.get('id', '?'))}")

    # Echo back with id preserved
    if "id" in msg and "method" in msg:
        response = {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {"echo": msg.get("params", {})},
        }
    elif "id" in msg:
        response = {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": msg,
        }
    else:
        continue  # notifications — don't respond

    sys.stdout.write(json.dumps(response) + "\\n")
    sys.stdout.flush()

log("done")
"""


@pytest.fixture
def echo_script_path(tmp_path):
    """Write echo server script to a temp file."""
    path = tmp_path / "echo_server.py"
    path.write_text(ECHO_SERVER)
    return str(path)


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_and_send_receive(echo_script_path):
    """Basic connect → send → receive → close lifecycle."""
    transport = StdioTransport(f"{sys.executable} {echo_script_path}", timeout=5.0)

    await transport.connect()

    # Send a request
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "test/ping",
        "params": {"key": "value"},
    }
    await transport.send(msg)

    response = await transport.receive()
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["echo"] == {"key": "value"}

    await transport.close()


@pytest.mark.asyncio
async def test_sequential_exchanges(echo_script_path):
    """Multiple send/receive cycles."""
    transport = StdioTransport(f"{sys.executable} {echo_script_path}", timeout=5.0)
    await transport.connect()

    for i in range(5):
        msg = {"jsonrpc": "2.0", "id": i, "method": "test/seq"}
        await transport.send(msg)
        response = await transport.receive()
        assert response["id"] == i

    await transport.close()


@pytest.mark.asyncio
async def test_stderr_captured(echo_script_path):
    """Stderr output is captured separately, not mixed with protocol stream."""
    transport = StdioTransport(f"{sys.executable} {echo_script_path}", timeout=5.0)
    await transport.connect()

    msg = {"jsonrpc": "2.0", "id": 1, "method": "test/ping"}
    await transport.send(msg)
    response = await transport.receive()
    assert response["id"] == 1

    # Stderr should contain startup and receive logs
    stderr_all = "\n".join(transport.stderr_lines)
    assert "started" in stderr_all
    assert "received" in stderr_all

    await transport.close()


@pytest.mark.asyncio
async def test_newline_delimited_framing(echo_script_path):
    """Each message is a single JSON line."""
    transport = StdioTransport(f"{sys.executable} {echo_script_path}", timeout=5.0)
    await transport.connect()

    # Send two messages consecutively
    msg1 = {"jsonrpc": "2.0", "id": 1, "method": "test/a"}
    msg2 = {"jsonrpc": "2.0", "id": 2, "method": "test/b"}

    await transport.send(msg1)
    await transport.send(msg2)

    r1 = await transport.receive()
    r2 = await transport.receive()

    assert r1["id"] == 1
    assert r2["id"] == 2

    await transport.close()


@pytest.mark.asyncio
async def test_timeout_on_no_response():
    """Transport times out gracefully when server produces no output."""
    # Use a Python process that sleeps and never writes to stdout
    transport = StdioTransport(
        f"{sys.executable} -c \"import time, sys; sys.stderr.write('sleeping\\n'); time.sleep(30)\"",
        timeout=1.0,
    )
    await transport.connect()

    msg = {"jsonrpc": "2.0", "id": 1, "method": "test/ping"}
    await transport.send(msg)

    with pytest.raises(TimeoutError, match="No response"):
        await transport.receive()

    await transport.close()


@pytest.mark.asyncio
async def test_send_after_connect_raises_on_closed():
    """send() raises RuntimeError on unconnected transport."""
    transport = StdioTransport("python -c 'pass'")
    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test"})


@pytest.mark.asyncio
async def test_receive_after_connect_raises_on_closed():
    """receive() raises RuntimeError on unconnected transport."""
    transport = StdioTransport("python -c 'pass'")
    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.receive()


@pytest.mark.asyncio
async def test_invalid_json_response(echo_script_path):
    """Invalid JSON lines from server raise ValueError."""
    transport = StdioTransport(
        f"{sys.executable} -c \"import sys, time; sys.stdout.write('not json\\n'); sys.stdout.flush(); time.sleep(10)\"",
        timeout=5.0,
    )
    await transport.connect()

    with pytest.raises(ValueError, match="Invalid JSON"):
        await transport.receive()

    await transport.close()


@pytest.mark.asyncio
async def test_close_is_idempotent(echo_script_path):
    """Calling close() multiple times is safe."""
    transport = StdioTransport(f"{sys.executable} {echo_script_path}", timeout=5.0)
    await transport.connect()

    await transport.close()
    await transport.close()  # should not raise

    # After close, send should raise
    with pytest.raises(RuntimeError, match="Not connected"):
        await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test"})


@pytest.mark.asyncio
async def test_empty_command_raises():
    """Empty command string raises ValueError."""
    transport = StdioTransport("")
    with pytest.raises(ValueError, match="Empty command"):
        await transport.connect()


@pytest.mark.asyncio
async def test_process_crash_detected(echo_script_path):
    """When the server crashes, receive() detects the closed stdout."""
    # Server that immediately exits
    transport = StdioTransport(
        f"{sys.executable} -c \"import sys; sys.stderr.write('crashing\\n'); sys.exit(1)\"",
        timeout=5.0,
    )
    await transport.connect()

    msg = {"jsonrpc": "2.0", "id": 1, "method": "test/ping"}
    await transport.send(msg)

    with pytest.raises(ConnectionError, match="closed stdout"):
        await transport.receive()

    await transport.close()


@pytest.mark.asyncio
async def test_quoted_command_with_spaces(echo_script_path):
    """Commands with spaces in path work via shlex splitting."""
    transport = StdioTransport(f'"{sys.executable}" "{echo_script_path}"', timeout=5.0)
    await transport.connect()

    msg = {"jsonrpc": "2.0", "id": 1, "method": "test/ping"}
    await transport.send(msg)
    response = await transport.receive()
    assert response["id"] == 1

    await transport.close()
