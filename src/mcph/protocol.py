"""JSON-RPC protocol engine for MCP-Hurl."""

from __future__ import annotations

import asyncio
from typing import Any

from mcph.ast import Initialize
from mcph.transport import Transport


class ProtocolEngine:
    """Wrap AST-level actions into JSON-RPC requests and notifications."""

    def __init__(self, transport: Transport):
        self._transport = transport
        self._next_request_id = 1

    async def initialize(self, init: Initialize) -> dict[str, Any]:
        """Send initialize request, return server capabilities."""
        client_info = {
            "name": init.client_name or "mcph",
            "version": init.client_version or "0.1.0",
        }
        params = {
            "protocolVersion": init.protocol_version,
            "clientInfo": client_info,
            "capabilities": init.capabilities,
        }
        response = await self._send_request("initialize", params)
        if response.get("is_error") is True:
            return response

        capabilities = response.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError("Initialize response capabilities must be an object")
        return capabilities

    async def send_initialized(self) -> None:
        """Send notifications/initialized after successful initialize."""
        message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        await self._transport.send(message)

    async def list_tools(self) -> dict[str, Any]:
        """Send tools/list, return response result."""
        return await self._send_request("tools/list")

    async def list_prompts(self) -> dict[str, Any]:
        """Send prompts/list, return response result."""
        return await self._send_request("prompts/list")

    async def list_resources(self) -> dict[str, Any]:
        """Send resources/list, return response result."""
        return await self._send_request("resources/list")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Send tools/call, return response result or error."""
        return await self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Send resources/read, return response result."""
        return await self._send_request("resources/read", {"uri": uri})

    async def get_prompt(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Send prompts/get, return response result."""
        return await self._send_request(
            "prompts/get",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    async def subscribe(self, uri: str) -> dict[str, Any]:
        """Send resources/subscribe, return response result."""
        return await self._send_request("resources/subscribe", {"uri": uri})

    async def listen(self, notification: str, timeout_ms: int) -> dict[str, Any]:
        """Wait for a notification from the server."""
        try:
            message = await asyncio.wait_for(
                self._transport.receive(),
                timeout=timeout_ms / 1000,
            )
        except TimeoutError as e:
            raise TimeoutError(
                f"Did not receive notification '{notification}' within {timeout_ms}ms"
            ) from e

        self._validate_jsonrpc_version(message)

        method = message.get("method")
        if method != notification:
            raise ValueError(f"Unexpected notification '{method}', expected '{notification}'")

        params = message.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("Notification params must be an object")

        return params

    async def shutdown(self) -> dict[str, Any]:
        """Send shutdown request and close transport."""
        try:
            return await self._send_request("shutdown")
        finally:
            await self._transport.close()

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = self._allocate_request_id()
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        await self._transport.send(message)
        response = await self._transport.receive()

        self._validate_jsonrpc_version(response)
        self._validate_response_id(response, request_id)

        if "error" in response:
            error_payload = response["error"]
            if not isinstance(error_payload, dict):
                error_payload = {"message": str(error_payload)}
            return {
                "is_error": True,
                "error": error_payload,
            }

        if "result" not in response:
            raise ValueError("JSON-RPC response must include either result or error")

        result_payload = response["result"]
        if not isinstance(result_payload, dict):
            raise ValueError("JSON-RPC result must be an object")

        return dict(result_payload)

    def _allocate_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _validate_response_id(self, response: dict[str, Any], expected_id: int) -> None:
        if response.get("id") != expected_id:
            raise ValueError(
                f"Response id mismatch: expected {expected_id}, got {response.get('id')}"
            )

    def _validate_jsonrpc_version(self, message: dict[str, Any]) -> None:
        if message.get("jsonrpc") != "2.0":
            raise ValueError("JSON-RPC message must include jsonrpc='2.0'")
