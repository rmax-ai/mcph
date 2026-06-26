"""Stdio transport for MCP-Hurl.

Spawns an MCP server as a subprocess and communicates over stdin/stdout
with newline-delimited JSON-RPC messages. Stderr is captured separately.
"""

import asyncio
import contextlib
import json
import shlex
from typing import Any

from mcph.transport import Transport


class StdioTransport(Transport):
    """Transport over a subprocess's stdin/stdout.

    The MCP server is spawned as a child process. Each JSON-RPC message is
    sent as a single line of JSON on stdin. Responses are read line-by-line
    from stdout. Stderr is captured to a buffer for diagnostics.

    Newlines inside JSON payloads are forbidden by the MCP spec — messages
    must be single-line.
    """

    def __init__(
        self,
        command: str,
        timeout: float = 30.0,
    ) -> None:
        self._command = command
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_buffer: list[str] = []
        self._stderr_task: asyncio.Task[Any] | None = None

    async def connect(self) -> None:
        """Spawn the subprocess."""
        cmd_parts = shlex.split(self._command)
        if not cmd_parts:
            raise ValueError(f"Empty command: {self._command}")

        self._process = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if self._process.stderr is not None:
            self._stderr_task = asyncio.create_task(self._read_stderr())

    async def _read_stderr(self) -> None:
        """Read stderr lines into the buffer."""
        assert self._process is not None
        assert self._process.stderr is not None
        try:
            async for line in self._process.stderr:
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                self._stderr_buffer.append(decoded)
        except asyncio.CancelledError:
            pass

    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the server's stdin."""
        if self._process is None:
            raise RuntimeError("Not connected. Call connect() first.")
        if self._process.stdin is None:
            raise RuntimeError("Subprocess stdin is not available")

        payload = json.dumps(message, ensure_ascii=False)
        if "\n" in payload:
            raise ValueError(
                "JSON-RPC message contains newlines — MCP spec requires "
                "single-line messages on stdio"
            )

        self._process.stdin.write((payload + "\n").encode("utf-8"))
        await self._process.stdin.drain()

    async def receive(self) -> dict[str, Any]:
        """Read a single JSON-RPC message from the server's stdout."""
        if self._process is None:
            raise RuntimeError("Not connected. Call connect() first.")
        if self._process.stdout is None:
            raise RuntimeError("Subprocess stdout is not available")

        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self._timeout,
            )
        except TimeoutError:
            raise TimeoutError(
                f"No response from MCP server within {self._timeout}s. "
                f"Stderr tail: {self.stderr_tail()}"
            )

        if not line:
            raise ConnectionError(
                "MCP server closed stdout unexpectedly. "
                f"Stderr tail: {self.stderr_tail()}"
            )

        decoded = line.decode("utf-8", errors="replace").rstrip("\n")
        try:
            return json.loads(decoded)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON from server: {e}\n"
                f"Received: {decoded[:200]}"
            ) from e

    async def close(self) -> None:
        """Close the transport gracefully. SIGTERM → SIGKILL escalation."""
        if self._process is None:
            return

        # Cancel stderr reader
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task
            self._stderr_task = None

        proc = self._process

        # Close stdin to signal EOF
        try:
            if proc.stdin is not None:
                proc.stdin.close()
                await proc.stdin.wait_closed()
        except Exception:
            pass

        # SIGTERM, wait, SIGKILL
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass  # Already exited

        self._process = None

    def stderr_tail(self, n: int = 20) -> str:
        """Return the last N lines of captured stderr."""
        return "\n".join(self._stderr_buffer[-n:])

    @property
    def stderr_lines(self) -> list[str]:
        """All captured stderr lines."""
        return list(self._stderr_buffer)
