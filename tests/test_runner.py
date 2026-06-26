"""Integration-style tests for session runtime and runner helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

from mcph.ast import Assert, CallTool, Shutdown
from mcph.runner import run_file_sync
from mcph.session import SessionConfig

ECHO_SERVER = dedent(
    """
    import json
    import sys

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        if "id" not in msg:
            continue

        req_id = msg["id"]

        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "serverInfo": {"name": "echo", "version": "0.1.0"},
                "capabilities": {"tools": {"listChanged": True}},
            }
        elif method == "tools/list":
            result = {"tools": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "tools/call":
            params = msg.get("params", {})
            result = {
                "tool": params.get("name"),
                "received": params.get("arguments", {}),
            }
        elif method == "resources/read":
            result = {"contents": []}
        elif method == "prompts/get":
            result = {"description": "ok"}
        elif method == "resources/subscribe":
            result = {}
        elif method == "shutdown":
            result = {}
        else:
            result = {}

        response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        sys.stdout.write(json.dumps(response) + "\\n")
        sys.stdout.flush()
    """
)


def _write_suite(tmp_path: Path, source: str) -> str:
    file_path = tmp_path / "suite.mcph"
    file_path.write_text(dedent(source).strip() + "\n", encoding="utf-8")
    return str(file_path)


def _echo_command(tmp_path: Path) -> str:
    script_path = tmp_path / "echo_server.py"
    script_path.write_text(ECHO_SERVER, encoding="utf-8")
    return f"{sys.executable} {script_path}"


def test_minimal_run_stdio(tmp_path: Path) -> None:
    command = _echo_command(tmp_path)
    suite_path = _write_suite(
        tmp_path,
        f"""
        CONNECT stdio "{command}"
        INITIALIZE protocolVersion="2025-03-26"
        LIST tools
        ASSERT STATUS == 200
        SHUTDOWN
        """,
    )

    results = run_file_sync(suite_path)

    assert len(results) == 5
    assert all(result.passed for result in results)


def test_require_capability_skips(tmp_path: Path) -> None:
    command = _echo_command(tmp_path)
    suite_path = _write_suite(
        tmp_path,
        f"""
        CONNECT stdio "{command}"
        INITIALIZE protocolVersion="2025-03-26"
        REQUIRE_CAPABILITY prompts
        LIST prompts
        ASSERT STATUS == 200
        REQUIRE_CAPABILITY tools
        LIST tools
        ASSERT STATUS == 200
        SHUTDOWN
        """,
    )

    results = run_file_sync(suite_path)

    skipped = [
        result for result in results if "Skipped due to missing capability" in result.message
    ]
    assert len(results) == 9
    assert len(skipped) == 2
    assert all(result.passed for result in results)


def test_continue_on_failure(tmp_path: Path) -> None:
    command = _echo_command(tmp_path)
    suite_path = _write_suite(
        tmp_path,
        f"""
        CONNECT stdio "{command}"
        INITIALIZE protocolVersion="2025-03-26"
        LIST tools
        ASSERT tools[*] COUNT >= 1
        SHUTDOWN
        """,
    )

    results = run_file_sync(suite_path, config=SessionConfig(continue_on_failure=True))

    assert len(results) == 5
    assert any(not result.passed for result in results)
    assert isinstance(results[-1].step, Shutdown)
    assert results[-1].passed is True


def test_hard_failure_stops(tmp_path: Path) -> None:
    command = _echo_command(tmp_path)
    suite_path = _write_suite(
        tmp_path,
        f"""
        CONNECT stdio "{command}"
        INITIALIZE protocolVersion="2025-03-26"
        LIST tools
        ASSERT tools[*] COUNT >= 1
        SHUTDOWN
        """,
    )

    results = run_file_sync(suite_path)

    assert len(results) == 4
    assert isinstance(results[-1].step, Assert)
    assert results[-1].passed is False


def test_variable_resolution_in_call(tmp_path: Path) -> None:
    command = _echo_command(tmp_path)
    suite_path = _write_suite(
        tmp_path,
        f"""
        CONNECT stdio "{command}"
        INITIALIZE protocolVersion="2025-03-26"
        SET user = "alice"
        SET count = 7
        CALL "echo" {{
          "message": "hi {{{{user}}}}",
          "count": "{{{{count}}}}"
        }}
        ASSERT result.received.message == "hi alice"
        ASSERT result.received.count == "7"
        SHUTDOWN
        """,
    )

    results = run_file_sync(suite_path)

    assert len(results) == 8
    assert all(result.passed for result in results)
    assert any(isinstance(result.step, CallTool) for result in results)
