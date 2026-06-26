"""Session manager and runtime execution for .mcph test files."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from mcph.assertion import AssertionEngine
from mcph.ast import (
    Assert,
    ASTNode,
    CallTool,
    Capture,
    Connect,
    GetPrompt,
    Header,
    Initialize,
    Listen,
    ListPrompts,
    ListResources,
    ListTools,
    ReadResource,
    RequireCapability,
    SetVar,
    Shutdown,
    Subscribe,
    TestFile,
)
from mcph.capture import CaptureRegistry
from mcph.protocol import ProtocolEngine
from mcph.transport import Transport
from mcph.transport.http_transport import HttpTransport
from mcph.transport.stdio import StdioTransport


@dataclass
class SessionConfig:
    continue_on_failure: bool = False
    timeout: float = 30.0
    verbose: bool = False


@dataclass
class StepResult:
    step: ASTNode
    passed: bool
    message: str
    duration_ms: float
    error: Exception | None = None


class Session:
    """Execute a parsed test file with transport, protocol, assertions, and captures."""

    def __init__(self, test_file: TestFile, config: SessionConfig):
        self._test_file = test_file
        self._config = config
        self._assertions = AssertionEngine()
        self._captures = CaptureRegistry()
        self._transport: Transport | None = None
        self._protocol: ProtocolEngine | None = None
        self._server_capabilities: dict[str, Any] = {}
        self._last_response: dict[str, Any] | None = None
        self._http_headers: dict[str, str] = {}
        self._skip_missing_capability: str | None = None

    async def run(self) -> list[StepResult]:
        """Execute the entire test file. Returns list of step results."""
        steps = self._test_file.steps
        if not steps:
            return []

        first_step = steps[0]
        if not isinstance(first_step, Connect):
            error = ValueError("First step must be CONNECT")
            return [
                StepResult(
                    step=first_step,
                    passed=False,
                    message=str(error),
                    duration_ms=0.0,
                    error=error,
                )
            ]

        results: list[StepResult] = []
        try:
            for step in steps:
                if self._skip_missing_capability is not None and not isinstance(
                    step, RequireCapability
                ):
                    results.append(
                        StepResult(
                            step=step,
                            passed=True,
                            message=(
                                f"Skipped due to missing capability "
                                f"'{self._skip_missing_capability}'"
                            ),
                            duration_ms=0.0,
                        )
                    )
                    continue

                result = await self._run_step(step)
                results.append(result)
                if not result.passed and not self._config.continue_on_failure:
                    break
        finally:
            if self._transport is not None:
                await self._transport.close()
                self._transport = None
                self._protocol = None

        return results

    async def _run_step(self, step: ASTNode) -> StepResult:
        start = time.perf_counter()
        try:
            message = await self._execute_step(step)
            duration_ms = (time.perf_counter() - start) * 1000
            return StepResult(
                step=step,
                passed=True,
                message=message,
                duration_ms=duration_ms,
            )
        except Exception as error:
            duration_ms = (time.perf_counter() - start) * 1000
            return StepResult(
                step=step,
                passed=False,
                message=str(error),
                duration_ms=duration_ms,
                error=error,
            )

    async def _execute_step(self, step: ASTNode) -> str:
        if isinstance(step, Connect):
            return await self._connect(step)
        if isinstance(step, Initialize):
            return await self._initialize(step)
        if isinstance(step, SetVar):
            value = self._captures.resolve(step.value)
            self._captures.set(step.variable, value)
            return f"Set variable '{step.variable}'"
        if isinstance(step, Header):
            self._set_header(step)
            return f"Set header '{step.name}'"
        if isinstance(step, ListTools):
            return await self._request("list_tools")
        if isinstance(step, ListPrompts):
            return await self._request("list_prompts")
        if isinstance(step, ListResources):
            return await self._request("list_resources")
        if isinstance(step, CallTool):
            arguments = self._captures.resolve(step.arguments)
            result = await self._protocol_required().call_tool(step.name, arguments)
            self._last_response = self._to_envelope(result)
            return f"Called tool '{step.name}'"
        if isinstance(step, ReadResource):
            uri = self._captures.resolve(step.uri)
            if not isinstance(uri, str):
                raise ValueError("READ uri must resolve to a string")
            result = await self._protocol_required().read_resource(uri)
            self._last_response = self._to_envelope(result)
            return f"Read resource '{uri}'"
        if isinstance(step, GetPrompt):
            arguments = self._captures.resolve(step.arguments)
            result = await self._protocol_required().get_prompt(step.name, arguments)
            self._last_response = self._to_envelope(result)
            return f"Retrieved prompt '{step.name}'"
        if isinstance(step, Subscribe):
            result = await self._protocol_required().subscribe(step.uri)
            self._last_response = self._to_envelope(result)
            return f"Subscribed to '{step.uri}'"
        if isinstance(step, Listen):
            params = await self._protocol_required().listen(step.notification, step.timeout_ms)
            self._last_response = {"jsonrpc": "2.0", "result": params}
            return f"Received notification '{step.notification}'"
        if isinstance(step, Shutdown):
            result = await self._protocol_required().shutdown()
            self._last_response = self._to_envelope(result)
            return "Shutdown completed"
        if isinstance(step, RequireCapability):
            return self._require_capability(step)
        if isinstance(step, Assert):
            if self._last_response is None:
                raise RuntimeError("ASSERT requires a previous response")
            self._assertions.evaluate(step, self._last_response)
            return "Assertion passed"
        if isinstance(step, Capture):
            if self._last_response is None:
                raise RuntimeError("CAPTURE requires a previous response")
            self._captures.capture(step, self._last_response)
            return f"Captured '{step.variable}'"

        raise ValueError(f"Unsupported step type: {type(step).__name__}")

    async def _connect(self, step: Connect) -> str:
        if self._transport is not None:
            await self._transport.close()

        if step.transport == "stdio":
            self._transport = StdioTransport(step.target, timeout=self._config.timeout)
        elif step.transport == "http":
            self._transport = HttpTransport(
                step.target,
                timeout=self._config.timeout,
                headers=self._http_headers,
            )
        else:
            raise ValueError(f"Unsupported transport '{step.transport}'")

        await self._transport.connect()
        self._protocol = ProtocolEngine(self._transport)
        return f"Connected using {step.transport}"

    async def _initialize(self, step: Initialize) -> str:
        initialize_result = await self._protocol_required().initialize(step)
        if initialize_result.get("is_error") is True:
            error_payload = initialize_result.get("error")
            self._last_response = self._to_envelope(initialize_result)
            raise RuntimeError(f"Initialize failed: {error_payload}")

        capabilities = initialize_result.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError("Initialize response capabilities must be an object")
        self._server_capabilities = capabilities
        self._last_response = {
            "jsonrpc": "2.0",
            "result": initialize_result,
        }
        await self._protocol_required().send_initialized()
        return "Initialized session"

    async def _request(self, method_name: str) -> str:
        protocol = self._protocol_required()
        if method_name == "list_tools":
            result = await protocol.list_tools()
            message = "Listed tools"
        elif method_name == "list_prompts":
            result = await protocol.list_prompts()
            message = "Listed prompts"
        elif method_name == "list_resources":
            result = await protocol.list_resources()
            message = "Listed resources"
        else:
            raise ValueError(f"Unsupported request method '{method_name}'")

        self._last_response = self._to_envelope(result)
        return message

    def _set_header(self, step: Header) -> None:
        value = self._captures.resolve(step.value)
        self._http_headers[step.name] = str(value)
        if isinstance(self._transport, HttpTransport):
            self._transport._headers[step.name] = str(value)

    def _require_capability(self, step: RequireCapability) -> str:
        if bool(self._server_capabilities.get(step.capability)):
            self._skip_missing_capability = None
            return f"Capability '{step.capability}' available"

        self._skip_missing_capability = step.capability
        return f"Capability '{step.capability}' missing, subsequent steps will be skipped"

    def _protocol_required(self) -> ProtocolEngine:
        if self._protocol is None:
            raise RuntimeError("Not connected. CONNECT must run first")
        return self._protocol

    def _to_envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("is_error") is True:
            error = payload.get("error", {})
            return {"jsonrpc": "2.0", "error": error}
        return {"jsonrpc": "2.0", "result": payload}
