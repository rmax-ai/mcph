"""Transport abstraction for MCP-Hurl."""

from abc import ABC, abstractmethod
from typing import Any


class Transport(ABC):
    """Base class for MCP transport layers (stdio, Streamable HTTP)."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish the connection."""

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message."""

    @abstractmethod
    async def receive(self) -> dict[str, Any]:
        """Receive a JSON-RPC message."""

    @abstractmethod
    async def close(self) -> None:
        """Close the connection gracefully."""
