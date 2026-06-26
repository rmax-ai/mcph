"""Line-oriented recursive descent parser for .mcph files.

Pipeline: raw text → tokenized lines → AST nodes → TestFile.
"""

import json as _json
import re
from typing import Any

from mcph.ast import (
    Assert,
    ASTNode,
    CallTool,
    Capture,
    Connect,
    FuzzyType,
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
    TemplateString,
    TestFile,
)
from mcph.exceptions import McphParseError

# ── Lexer ────────────────────────────────────────────────────────────────────

COMMENT_RE = re.compile(r"^\s*#")
BLANK_RE = re.compile(r"^\s*$")

# Predicate operators, longest-match-first
PREDICATES = [
    ("CONTAINS",  "CONTAINS"),
    ("MATCHES",   "MATCHES"),
    ("EXISTS",    "EXISTS"),
    ("COUNT",     "COUNT"),
    ("!=",        "!="),
    (">=",        ">="),
    ("<=",        "<="),
    ("==",        "=="),
    (">",         ">"),
    ("<",         "<"),
]

# Regex for fuzzy type matchers: ##string, #number, etc.
FUZZY_RE = re.compile(r"^#{1,2}(string|number|boolean|array|object)$")

# Regex for template interpolation: {{var}}
TEMPLATE_RE = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")

# Regex for a quoted string: "…" or '…'
QUOTED_RE = re.compile(r'^"([^"]*)"$')
SINGLE_QUOTED_RE = re.compile(r"^'([^']*)'$")


def _unquote(s: str) -> str:
    """Strip surrounding double or single quotes."""
    m = QUOTED_RE.match(s)
    if m:
        return m.group(1)
    m = SINGLE_QUOTED_RE.match(s)
    if m:
        return m.group(1)
    return s


def _resolve_fuzzy(value_str: str) -> FuzzyType | None:
    """Check if a value string is a fuzzy type matcher like #string."""
    m = FUZZY_RE.match(value_str)
    if m:
        return FuzzyType(type_name=m.group(1), optional=value_str.startswith("##"))
    return None


def _resolve_value(value_str: str) -> Any:
    """Parse a value string into a Python value.

    Order: fuzzy types → booleans → null → integer → float → regex → quoted string → raw string.
    """
    # Fuzzy types
    fuzzy = _resolve_fuzzy(value_str)
    if fuzzy is not None:
        return fuzzy

    # Boolean
    if value_str == "true":
        return True
    if value_str == "false":
        return False

    # Null
    if value_str == "null" or value_str == "none":
        return None

    # Regex: /pattern/
    if value_str.startswith("/") and value_str.endswith("/") and len(value_str) > 1:
        return value_str[1:-1]

    # Integer
    try:
        if value_str.startswith("-"):
            return int(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Float
    try:
        return float(value_str)
    except ValueError:
        pass

    # Quoted string
    m = QUOTED_RE.match(value_str)
    if m:
        s = m.group(1)
        return _parse_template(s)
    m = SINGLE_QUOTED_RE.match(value_str)
    if m:
        return m.group(1)

    # Raw string (keyword values like "stdio", "http")
    return value_str


def _parse_template(s: str) -> str | TemplateString:
    """Parse a string for {{var}} interpolation. Returns plain str if no templates."""
    parts = TEMPLATE_RE.split(s)
    if len(parts) == 1:
        return parts[0]
    result: list[str | tuple[str, str]] = []
    i = 0
    while i < len(parts):
        if i % 2 == 0:
            if parts[i]:
                result.append(parts[i])
        else:
            result.append(("var", parts[i]))
        i += 1
    return TemplateString(parts=result)


def _resolve_quoted_key_value(s: str) -> tuple[str, str]:
    """Parse 'name = "value"' or 'name = value' into (name, value)."""
    eq = s.find("=")
    if eq == -1:
        raise McphParseError(f"Expected 'key = value', got: {s}")
    key = s[:eq].strip()
    value = s[eq + 1:].strip()
    return key, value


# ── Line iterator ─────────────────────────────────────────────────────────────

class LineReader:
    """Iterate over lines with lookahead and multi-line JSON body collection."""

    def __init__(self, text: str) -> None:
        self._lines = text.split("\n")
        self._pos = 0
        self._line_no = 1  # 1-indexed

    def __bool__(self) -> bool:
        return self._pos < len(self._lines)

    def peek(self) -> tuple[str, int] | None:
        """Return (line, line_number) without advancing."""
        while self._pos < len(self._lines):
            line = self._lines[self._pos]
            ln = self._line_no + self._pos
            if COMMENT_RE.match(line) or BLANK_RE.match(line):
                self._pos += 1
                continue
            return line.strip(), ln
        return None

    def next(self) -> tuple[str, int] | None:
        """Return (stripped_line, line_number), advancing past comments/blanks.

        Returns None when the file ends with no more content.
        """
        while self._pos < len(self._lines):
            raw = self._lines[self._pos]
            ln = self._line_no + self._pos
            self._pos += 1
            stripped = raw.strip()
            if COMMENT_RE.match(stripped) or BLANK_RE.match(stripped):
                continue
            return stripped, ln
        return None

    def collect_json_body(self, start_line: str, start_ln: int) -> str:
        """Collect a multi-line JSON body starting from 'start_line'.

        start_line should contain the opening '{' or '['. Returns the full text
        including the opening brace/bracket.
        """
        # Find the opening brace/bracket in the start_line
        open_idx = -1
        open_ch = ""
        close_ch = ""
        for ch, close in [("{", "}"), ("[", "]")]:
            idx = start_line.find(ch)
            if idx != -1:
                open_idx = idx
                open_ch = ch
                close_ch = close
                break

        if open_idx == -1:
            raise McphParseError(
                "Expected '{' or '[' to start JSON body", start_ln, start_line
            )

        # Count braces/brackets to find the matching closing one
        depth = 0
        collected = start_line[open_idx:]
        for ch in collected:
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1

        while depth > 0 and self._pos < len(self._lines):
            raw = self._lines[self._pos]
            self._pos += 1
            stripped = raw.strip()
            if COMMENT_RE.match(stripped) or BLANK_RE.match(stripped):
                continue
            collected += stripped
            for ch in stripped:
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1

        if depth != 0:
            raise McphParseError(
                f"Unmatched '{open_ch}' in JSON body (missing {depth} closing '{close_ch}')",
                start_ln,
            )

        return collected


def _parse_value_templates(obj: Any) -> Any:
    """Recursively parse {{var}} templates in JSON body string values."""
    if isinstance(obj, dict):
        return {k: _parse_value_templates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_parse_value_templates(v) for v in obj]
    if isinstance(obj, str):
        result = _parse_template(obj)
        if isinstance(result, TemplateString):
            return result
        return obj
    return obj


# ── Parser ────────────────────────────────────────────────────────────────────

class Parser:
    """Recursive descent parser for .mcph files."""

    def __init__(self, reader: LineReader) -> None:
        self._r = reader

    def parse(self) -> TestFile:
        """Parse the entire file into a TestFile AST."""
        steps: list[ASTNode] = []
        while self._r:
            result = self._r.next()
            if result is None:
                break
            line, ln = result
            step = self._parse_step(line, ln)
            if step is not None:
                steps.append(step)
        return TestFile(steps=steps)

    def _parse_step(self, line: str, ln: int) -> ASTNode | None:
        """Dispatch to the appropriate sub-parser based on the keyword."""
        try:
            keyword, rest = line.split(maxsplit=1)
        except ValueError:
            keyword = line
            rest = ""

        kw = keyword.upper()

        if kw == "CONNECT":
            return self._parse_connect(rest, ln)
        elif kw == "INITIALIZE":
            return self._parse_initialize(rest, line, ln)
        elif kw == "SET":
            return self._parse_set(rest, ln)
        elif kw == "HEADER":
            return self._parse_header(rest, ln)
        elif kw == "LIST":
            return self._parse_list(rest, ln)
        elif kw == "CALL":
            return self._parse_call(rest, line, ln)
        elif kw == "READ":
            return self._parse_read(rest, ln)
        elif kw == "GET":
            return self._parse_get_prompt(rest, line, ln)
        elif kw == "SUBSCRIBE":
            return self._parse_subscribe(rest, ln)
        elif kw == "LISTEN":
            return self._parse_listen(rest, ln)
        elif kw == "SHUTDOWN":
            return Shutdown(line_number=ln)
        elif kw == "REQUIRE_CAPABILITY":
            return self._parse_require_capability(rest, ln)
        elif kw == "ASSERT":
            return self._parse_assert(rest, ln)
        elif kw == "CAPTURE":
            return self._parse_capture(rest, ln)
        elif kw == "CLIENT":
            # CLIENT should only appear as a sub-block of INITIALIZE
            raise McphParseError(
                "CLIENT must appear inside an INITIALIZE block", ln, line
            )
        elif kw == "CAPABILITIES":
            raise McphParseError(
                "CAPABILITIES must appear inside a CLIENT block", ln, line
            )
        else:
            raise McphParseError(
                f"Unknown keyword: {keyword}", ln, line
            )

    # ── Individual parsers ────────────────────────────────────────────────

    def _parse_connect(self, rest: str, ln: int) -> Connect:
        """CONNECT stdio "command" | CONNECT http "url" """
        parts = rest.split(maxsplit=1)
        if len(parts) < 2:
            raise McphParseError(
                "CONNECT requires transport and target, e.g. CONNECT stdio \"cmd\"",
                ln,
            )
        transport = parts[0].lower()
        if transport not in ("stdio", "http"):
            raise McphParseError(
                f"Unknown transport '{transport}'. Expected 'stdio' or 'http'",
                ln,
            )
        target = _unquote(parts[1])
        return Connect(transport=transport, target=target, line_number=ln)

    def _parse_initialize(self, rest: str, full_line: str, ln: int) -> Initialize:
        """INITIALIZE protocolVersion="..." optionally followed by CLIENT block."""
        kv = _resolve_quoted_key_value(rest)
        if kv[0] != "protocolVersion":
            raise McphParseError(
                f"INITIALIZE requires protocolVersion=, got {kv[0]}", ln, full_line
            )
        protocol_version = _unquote(kv[1])

        client_name = None
        client_version = None
        capabilities: dict[str, bool] = {}

        # Check for CLIENT sub-block
        peeked = self._r.peek()
        if peeked:
            peek_line, _peek_ln = peeked
            if peek_line.upper().startswith("CLIENT"):
                self._r.next()  # consume CLIENT line
                rest_client = peek_line[len("CLIENT"):].strip()
                # Parse name="..." version="..."
                # Simple key=value parsing
                if rest_client:
                    kvs = self._parse_key_value_list(rest_client)
                    client_name = _unquote(kvs.get("name", ""))
                    client_version = _unquote(kvs.get("version", ""))

                # Check for CAPABILITIES sub-block (indented)
                peeked2 = self._r.peek()
                if peeked2:
                    p2_line, _p2_ln = peeked2
                    if p2_line.upper().startswith("CAPABILITIES"):
                        self._r.next()
                        caps_str = p2_line[len("CAPABILITIES"):].strip()
                        capabilities = self._parse_capabilities(caps_str)

        return Initialize(
            protocol_version=protocol_version,
            client_name=client_name,
            client_version=client_version,
            capabilities=capabilities,
            line_number=ln,
        )

    def _parse_key_value_list(self, s: str) -> dict[str, str]:
        """Parse 'key="value" key2="value2"' into a dict."""
        result: dict[str, str] = {}
        # Naive split on spaces, handle quoted values
        parts = re.findall(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)', s)
        for key, val in parts:
            result[key] = _unquote(val)
        return result

    def _parse_capabilities(self, s: str) -> dict[str, bool]:
        """Parse 'roots=true sampling=true' into {roots: True, sampling: True}."""
        caps: dict[str, bool] = {}
        parts = s.split()
        for part in parts:
            kv = part.split("=", 1)
            if len(kv) == 2:
                caps[kv[0]] = kv[1].lower() == "true"
        return caps

    def _collect_json_body_ext(
        self, after_name: str, full_line: str, ln: int
    ) -> str:
        """Collect a JSON body, checking current line then next line."""
        # Check current line remainder for { or [
        if "{" in after_name or "[" in after_name:
            return self._r.collect_json_body(after_name, ln)

        # Check next line
        peeked = self._r.peek()
        if peeked:
            next_line, _ = peeked
            if next_line.startswith("{") or next_line.startswith("["):
                self._r.next()  # consume the peeked line
                return self._r.collect_json_body(next_line, ln)

        return "{}"

    def _parse_set(self, rest: str, ln: int) -> SetVar:
        """SET name = value"""
        key, value = _resolve_quoted_key_value(rest)
        parsed = _parse_template(_unquote(value))
        return SetVar(
            variable=key,
            value=parsed if isinstance(parsed, TemplateString) else str(parsed),
            line_number=ln,
        )

    def _parse_header(self, rest: str, ln: int) -> Header:
        """HEADER "name" = "value" """
        key, value = _resolve_quoted_key_value(rest)
        return Header(name=_unquote(key), value=_unquote(value), line_number=ln)

    def _parse_list(self, rest: str, ln: int) -> ASTNode:
        """LIST tools | LIST prompts | LIST resources"""
        what = rest.strip().lower()
        if what == "tools":
            return ListTools(line_number=ln)
        elif what == "prompts":
            return ListPrompts(line_number=ln)
        elif what == "resources":
            return ListResources(line_number=ln)
        else:
            raise McphParseError(
                f"LIST expects 'tools', 'prompts', or 'resources', got '{rest}'",
                ln,
            )

    def _parse_call(self, rest: str, full_line: str, ln: int) -> CallTool:
        """CALL "tool_name" { json_body }"""
        # Extract the quoted tool name
        name_match = re.match(r'"([^"]*)"', rest)
        if not name_match:
            raise McphParseError(
                "CALL requires a quoted tool name, e.g. CALL \"my_tool\"",
                ln,
                full_line,
            )
        name = name_match.group(1)
        after_name = rest[name_match.end():].strip()

        # Collect JSON body — check current line, then next line
        body_text = self._collect_json_body_ext(after_name, full_line, ln)

        try:
            arguments = _json.loads(body_text)
        except _json.JSONDecodeError as e:
            raise McphParseError(
                f"Invalid JSON in CALL body: {e}", ln, body_text
            ) from e

        if not isinstance(arguments, dict):
            raise McphParseError(
                "CALL body must be a JSON object", ln, body_text
            )

        # Parse templates in argument values
        arguments = _parse_value_templates(arguments)

        return CallTool(name=name, arguments=arguments, line_number=ln)

    def _parse_read(self, rest: str, ln: int) -> ReadResource:
        """READ "uri" """
        return ReadResource(uri=_unquote(rest.strip()), line_number=ln)

    def _parse_get_prompt(self, rest: str, full_line: str, ln: int) -> GetPrompt:
        """GET prompt "name" { json_args }"""
        # "prompt" keyword then name then optional JSON
        if not rest.lower().startswith("prompt"):
            raise McphParseError(
                "GET expects 'prompt', e.g. GET prompt \"name\"", ln, full_line
            )
        rest = rest[len("prompt"):].strip()

        name_match = re.match(r'"([^"]*)"', rest)
        if not name_match:
            raise McphParseError(
                "GET prompt requires a quoted name", ln, full_line
            )
        name = name_match.group(1)
        after_name = rest[name_match.end():].strip()

        body_text = self._collect_json_body_ext(after_name, full_line, ln)

        try:
            arguments = _json.loads(body_text)
        except _json.JSONDecodeError as e:
            raise McphParseError(
                f"Invalid JSON in GET prompt body: {e}", ln, body_text
            ) from e

        if not isinstance(arguments, dict):
            raise McphParseError(
                "GET prompt body must be a JSON object", ln, body_text
            )

        arguments = _parse_value_templates(arguments)

        return GetPrompt(name=name, arguments=arguments, line_number=ln)

    def _parse_subscribe(self, rest: str, ln: int) -> Subscribe:
        """SUBSCRIBE "uri" """
        return Subscribe(uri=_unquote(rest.strip()), line_number=ln)

    def _parse_listen(self, rest: str, ln: int) -> Listen:
        """LISTEN "notification" TIMEOUT <ms>"""
        # Extract quoted notification name
        name_match = re.match(r'"([^"]*)"', rest)
        if not name_match:
            raise McphParseError(
                "LISTEN requires a quoted notification name", ln
            )
        notification = name_match.group(1)
        after = rest[name_match.end():].strip()

        timeout_ms = 5000  # default
        if after.upper().startswith("TIMEOUT"):
            timeout_str = after[len("TIMEOUT"):].strip()
            try:
                timeout_ms = int(timeout_str)
            except ValueError:
                raise McphParseError(
                    f"Invalid TIMEOUT value: {timeout_str}", ln
                ) from None

        return Listen(notification=notification, timeout_ms=timeout_ms, line_number=ln)

    def _parse_require_capability(self, rest: str, ln: int) -> RequireCapability:
        """REQUIRE_CAPABILITY <name>"""
        return RequireCapability(capability=rest.strip(), line_number=ln)

    def _parse_assert(self, rest: str, ln: int) -> Assert:
        """ASSERT <query> <predicate> <value>"""
        # Try predicates longest-match-first
        op_name = ""
        for p_text, p_name in PREDICATES:
            # Look for the predicate preceded and followed by whitespace
            idx = rest.find(f" {p_text} ")
            if idx == -1 and rest.endswith(f" {p_text}"):
                # Edge case: "ASSERT query CONTAINS" with no value
                idx = rest.rfind(f" {p_text}")
                query = rest[:idx].strip()
                value_str = ""
                op_name = p_name
                break
            if idx != -1:
                query = rest[:idx].strip()
                value_str = rest[idx + len(p_text) + 2:].strip()
                op_name = p_name
                break
        else:
            raise McphParseError(
                f"ASSERT requires a predicate ({', '.join(p[0] for p in PREDICATES)})",
                ln,
                rest,
            )

        # Handle multi-line JSON body as assertion value
        expected: Any
        if value_str.startswith("{") or value_str.startswith("["):
            try:
                body_text = self._r.collect_json_body(value_str, ln)
                expected = _json.loads(body_text)
            except (_json.JSONDecodeError, McphParseError):
                expected = _resolve_value(value_str)
        elif value_str == "":
            # Check if next line is a JSON body
            peeked = self._r.peek()
            if peeked:
                next_line, _ = peeked
                if next_line.startswith("{") or next_line.startswith("["):
                    self._r.next()
                    body_text = self._r.collect_json_body(next_line, ln)
                    expected = _json.loads(body_text)
                else:
                    expected = _resolve_value(value_str)
            else:
                expected = _resolve_value(value_str)
        else:
            expected = _resolve_value(value_str)

        return Assert(query=query, predicate=op_name, expected_value=expected, line_number=ln)

    def _parse_capture(self, rest: str, ln: int) -> Capture:
        """CAPTURE <var>: <query> [regex /pattern/ <group>]"""
        # Split on first ":"
        colon = rest.find(":")
        if colon == -1:
            raise McphParseError(
                "CAPTURE requires 'variable: query', e.g. CAPTURE x: result.id",
                ln,
            )
        variable = rest[:colon].strip()
        after = rest[colon + 1:].strip()

        # Check for regex suffix
        regex_match = re.search(r'\s+regex\s+/(.+?)/(\s+\d+)?\s*$', after)
        if regex_match:
            query = after[:regex_match.start()].strip()
            pattern = regex_match.group(1)
            group_str = regex_match.group(2)
            group = int(group_str.strip()) if group_str else 0
            return Capture(
                variable=variable, query=query,
                regex_pattern=pattern, regex_group=group,
                line_number=ln,
            )

        return Capture(variable=variable, query=after, line_number=ln)


# ── Public API ────────────────────────────────────────────────────────────────

def parse(text: str) -> TestFile:
    """Parse a .mcph file string into a TestFile AST.

    Args:
        text: The contents of a .mcph file.

    Returns:
        TestFile AST node containing all parsed steps.

    Raises:
        McphParseError: If parsing fails with a syntax error.
    """
    reader = LineReader(text)
    parser = Parser(reader)
    return parser.parse()
