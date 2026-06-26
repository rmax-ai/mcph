"""Minimal MCP stdio echo server for integration and conformance testing."""

from __future__ import annotations

import json
import sys
from typing import Any

JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2025-03-26"


def _log(message: str) -> None:
    print(f"[echo-server] {message}", file=sys.stderr, flush=True)


def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def main() -> int:
    _log("starting stdio loop")
    initialized = False

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"invalid JSON received: {exc}")
            continue

        method = message.get("method")
        request_id = message.get("id")
        _log(f"received method={method!r} id={request_id!r}")

        if method == "notifications/initialized":
            initialized = True
            _log("initialized notification received")
            continue

        if request_id is None:
            _log("notification without id ignored")
            continue

        if method == "initialize":
            _send(
                _success_response(
                    request_id,
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "serverInfo": {"name": "McphEchoServer", "version": "0.1.0"},
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "prompts": {"listChanged": False},
                            "resources": {"listChanged": False, "subscribe": False},
                        },
                    },
                )
            )
            continue

        if not initialized:
            _send(_error_response(request_id, -32002, "Server not initialized"))
            continue

        if method == "tools/list":
            _send(
                _success_response(
                    request_id,
                    {
                        "tools": [
                            {
                                "name": "echo",
                                "description": "Echo arguments back",
                                "inputSchema": {
                                    "type": "object",
                                    "additionalProperties": True,
                                },
                            }
                        ]
                    },
                )
            )
            continue

        if method == "tools/call":
            params = message.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            if name != "echo":
                _send(_error_response(request_id, -32602, "Unknown tool"))
                continue
            if not isinstance(arguments, dict):
                _send(_error_response(request_id, -32602, "Tool arguments must be an object"))
                continue
            _send(
                _success_response(
                    request_id,
                    {
                        "isError": False,
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(arguments, ensure_ascii=False),
                            }
                        ],
                        "echo": arguments,
                    },
                )
            )
            continue

        if method == "prompts/list":
            _send(
                _success_response(
                    request_id,
                    {
                        "prompts": [
                            {
                                "name": "echo-prompt",
                                "description": "Simple echo prompt for conformance tests",
                            }
                        ]
                    },
                )
            )
            continue

        if method == "resources/list":
            _send(
                _success_response(
                    request_id,
                    {
                        "resources": [
                            {
                                "uri": "echo://resource",
                                "name": "Echo Resource",
                                "mimeType": "text/plain",
                            }
                        ]
                    },
                )
            )
            continue

        if method == "shutdown":
            _send(_success_response(request_id, {}))
            _log("shutdown request processed, exiting")
            return 0

        _send(_error_response(request_id, -32601, f"Method not found: {method}"))

    _log("stdin closed, exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
