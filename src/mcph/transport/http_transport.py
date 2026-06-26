"""Streamable HTTP transport for MCP-Hurl.

This phase implements simple request-response over a single MCP HTTP endpoint:
send JSON-RPC via POST, then read JSON-RPC from the response body.
"""

import asyncio
from typing import Any

import httpx

from mcph.transport import Transport


class HttpTransport(Transport):
    """Transport over MCP Streamable HTTP endpoint."""

    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._headers = dict(headers or {})
        self._session_id: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self) -> None:
        """Initialize the async HTTP client."""
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout))

    async def send(self, message: dict[str, Any]) -> None:
        """Send one JSON-RPC message via POST and enqueue JSON response."""
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")

        request_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self._headers,
        }
        if self._session_id is not None:
            request_headers["Mcp-Session-Id"] = self._session_id

        try:
            response = await self._client.post(self._url, json=message, headers=request_headers)
        except httpx.ConnectError:
            raise ConnectionError(f"Failed to connect to MCP server at {self._url}") from None

        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

        try:
            payload = response.json()
        except ValueError as e:
            raise ValueError(f"Invalid JSON response from MCP server at {self._url}") from e

        if not isinstance(payload, dict):
            raise ValueError(
                f"Expected JSON object response from MCP server at {self._url}, got {type(payload)}"
            )

        await self._response_queue.put(payload)

    async def receive(self) -> dict[str, Any]:
        """Receive one JSON-RPC response associated with a prior send()."""
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")

        try:
            return await asyncio.wait_for(self._response_queue.get(), timeout=self._timeout)
        except TimeoutError as e:
            raise TimeoutError(f"No response from MCP server within {self._timeout}s") from e

    async def close(self) -> None:
        """Close the HTTP client. Safe to call multiple times."""
        if self._client is None:
            return

        await self._client.aclose()
        self._client = None
        self._session_id = None
        self._response_queue = asyncio.Queue()
