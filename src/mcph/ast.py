"""AST node definitions for MCP-Hurl (Mcph)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ASTNode:
    """Base node with line number for error reporting."""
    line_number: int


@dataclass
class Connect(ASTNode):
    """CONNECT stdio "command" | CONNECT http "url" """
    transport: str  # "stdio" | "http"
    target: str     # command or URL
    timeout: int | None = None
    retry: int | None = None
    retry_interval: int | None = None


@dataclass
class Initialize(ASTNode):
    """INITIALIZE protocolVersion="..." [CLIENT ...]"""
    protocol_version: str
    client_name: str | None = None
    client_version: str | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)


@dataclass
class SetVar(ASTNode):
    """SET name = value"""
    variable: str
    value: str | TemplateString


@dataclass
class Header(ASTNode):
    """HEADER "name" = "value" """
    name: str
    value: str


@dataclass
class ListTools(ASTNode):
    """LIST tools"""
    pass


@dataclass
class ListPrompts(ASTNode):
    """LIST prompts"""
    pass


@dataclass
class ListResources(ASTNode):
    """LIST resources"""
    pass


@dataclass
class CallTool(ASTNode):
    """CALL "name" { ... }"""
    name: str
    arguments: dict[str, Any]


@dataclass
class ReadResource(ASTNode):
    """READ "uri" """
    uri: str


@dataclass
class GetPrompt(ASTNode):
    """GET prompt "name" { ... }"""
    name: str
    arguments: dict[str, Any]


@dataclass
class Subscribe(ASTNode):
    """SUBSCRIBE "uri" """
    uri: str


@dataclass
class Listen(ASTNode):
    """LISTEN "notification" TIMEOUT <ms>"""
    notification: str
    timeout_ms: int


@dataclass
class Shutdown(ASTNode):
    """SHUTDOWN"""
    pass


@dataclass
class RequireCapability(ASTNode):
    """REQUIRE_CAPABILITY <name>"""
    capability: str


@dataclass
class Assert(ASTNode):
    """ASSERT <query> <predicate> <value>"""
    query: str          # e.g. "STATUS", "tools[*]", "result.content.text"
    predicate: str      # "==", "!=", "CONTAINS", "MATCHES", "EXISTS", "COUNT", ">", ">=", "<", "<="
    expected_value: Any  # str, int, bool, FuzzyType, regex string, dict, list


@dataclass
class Capture(ASTNode):
    """CAPTURE <var>: <query> [regex /pattern/ <group>]"""
    variable: str
    query: str
    regex_pattern: str | None = None
    regex_group: int | None = None


@dataclass
class FuzzyType:
    """Fuzzy type matcher: #string, #number, ##string (optional), etc."""
    type_name: str      # "string", "number", "boolean", "array", "object"
    optional: bool = False  # True for ##type (matches if absent OR correct type)

    def __repr__(self) -> str:
        prefix = "##" if self.optional else "#"
        return f"{prefix}{self.type_name}"


@dataclass
class TemplateString:
    """A string containing {{variable}} interpolation markers."""
    parts: list[str | tuple[str, str]]  # alternating str literals and ("var", name) tuples

    def __repr__(self) -> str:
        result = []
        for p in self.parts:
            if isinstance(p, str):
                result.append(p)
            else:
                result.append(f"{{{{{p[1]}}}}}")
        return "".join(result)


@dataclass
class TestFile:
    """Top-level container for a .mcph file."""
    steps: list[ASTNode]
