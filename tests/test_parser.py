"""Tests for the MCP-Hurl parser."""


import pytest

from mcph.ast import (
    Assert,
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
from mcph.parser import parse

# ── Test helpers ──────────────────────────────────────────────────────────────

def find_step(steps: list, cls: type, index: int = 0) -> object:
    """Find the nth step of a given type in the list."""
    found = [s for s in steps if isinstance(s, cls)]
    assert len(found) > index, f"Expected at least {index + 1} {cls.__name__} steps"
    return found[index]


def count_steps(steps: list, cls: type) -> int:
    """Count steps of a given type."""
    return sum(1 for s in steps if isinstance(s, cls))


# ── Minimal valid file ───────────────────────────────────────────────────────

def test_minimal_valid_file() -> None:
    result = parse("""CONNECT stdio "echo-server"
INITIALIZE protocolVersion="2025-03-26"
SHUTDOWN""")

    assert len(result.steps) == 3
    conn = result.steps[0]
    assert isinstance(conn, Connect)
    assert conn.transport == "stdio"
    assert conn.target == "echo-server"

    init = result.steps[1]
    assert isinstance(init, Initialize)
    assert init.protocol_version == "2025-03-26"

    shut = result.steps[2]
    assert isinstance(shut, Shutdown)


# ── CONNECT ──────────────────────────────────────────────────────────────────

def test_connect_stdio() -> None:
    result = parse('CONNECT stdio "python -m my_server"')
    conn = result.steps[0]
    assert isinstance(conn, Connect)
    assert conn.transport == "stdio"
    assert conn.target == "python -m my_server"


def test_connect_http() -> None:
    result = parse('CONNECT http "https://api.internal/mcp"')
    conn = result.steps[0]
    assert isinstance(conn, Connect)
    assert conn.transport == "http"
    assert conn.target == "https://api.internal/mcp"


def test_connect_unknown_transport() -> None:
    with pytest.raises(McphParseError, match="Unknown transport"):
        parse('CONNECT tcp "something"')


def test_connect_missing_target() -> None:
    with pytest.raises(McphParseError, match="CONNECT requires"):
        parse("CONNECT stdio")


# ── INITIALIZE with CLIENT + CAPABILITIES ────────────────────────────────────

def test_initialize_with_client_and_capabilities() -> None:
    result = parse("""CONNECT stdio "server"
INITIALIZE protocolVersion="2025-03-26"
CLIENT name="EnterpriseValidator" version="1.0.0"
  CAPABILITIES roots=true sampling=true
SHUTDOWN""")

    init = find_step(result.steps, Initialize)
    assert init.protocol_version == "2025-03-26"
    assert init.client_name == "EnterpriseValidator"
    assert init.client_version == "1.0.0"
    assert init.capabilities == {"roots": True, "sampling": True}


def test_initialize_minimal() -> None:
    result = parse("""CONNECT stdio "s"
INITIALIZE protocolVersion="2025-06-26"
SHUTDOWN""")

    init = find_step(result.steps, Initialize)
    assert init.protocol_version == "2025-06-26"
    assert init.client_name is None
    assert init.client_version is None
    assert init.capabilities == {}


# ── SET and HEADER ───────────────────────────────────────────────────────────

def test_set_variable() -> None:
    result = parse('SET myvar = "hello"')
    sv = result.steps[0]
    assert isinstance(sv, SetVar)
    assert sv.variable == "myvar"
    assert sv.value == "hello"


def test_set_meta() -> None:
    result = parse('SET _meta.protocolVersion = "DRAFT-2026-v1"')
    sv = result.steps[0]
    assert isinstance(sv, SetVar)
    assert sv.variable == "_meta.protocolVersion"
    assert sv.value == "DRAFT-2026-v1"


def test_header() -> None:
    result = parse('HEADER "Authorization" = "Bearer {{TOKEN}}"')
    h = result.steps[0]
    assert isinstance(h, Header)
    assert h.name == "Authorization"
    assert h.value == "Bearer {{TOKEN}}"


# ── LIST commands ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cmd,cls", [
    ("LIST tools", ListTools),
    ("LIST prompts", ListPrompts),
    ("LIST resources", ListResources),
])
def test_list_commands(cmd: str, cls: type) -> None:
    result = parse(f"CONNECT stdio x\n{cmd}\nSHUTDOWN")
    assert isinstance(result.steps[1], cls)


def test_list_unknown() -> None:
    with pytest.raises(McphParseError, match="LIST expects"):
        parse("CONNECT stdio x\nLIST widgets\nSHUTDOWN")


# ── CALL tool ────────────────────────────────────────────────────────────────

def test_call_tool_simple() -> None:
    result = parse('CALL "run_sql" { "query": "SELECT 1;" }')
    c = result.steps[0]
    assert isinstance(c, CallTool)
    assert c.name == "run_sql"
    assert c.arguments == {"query": "SELECT 1;"}


def test_call_tool_multiline_json() -> None:
    result = parse("""CALL "run_sql" {
  "query": "SELECT 1;",
  "timeout_ms": 1000
}""")
    c = result.steps[0]
    assert c.name == "run_sql"
    assert c.arguments == {"query": "SELECT 1;", "timeout_ms": 1000}


def test_call_tool_json_across_lines() -> None:
    result = parse('CALL "run_sql"\n{ "query": "SELECT 1;" }')
    c = result.steps[0]
    assert c.name == "run_sql"
    assert c.arguments == {"query": "SELECT 1;"}


def test_call_tool_invalid_json() -> None:
    with pytest.raises(McphParseError, match="Invalid JSON"):
        parse('CALL "t" { not valid json }')


def test_call_tool_array_body() -> None:
    with pytest.raises(McphParseError, match="JSON object"):
        parse('CALL "t" [1, 2, 3]')


# ── READ resource ────────────────────────────────────────────────────────────

def test_read_resource() -> None:
    result = parse('READ "file:///project/src/main.rs"')
    r = result.steps[0]
    assert isinstance(r, ReadResource)
    assert r.uri == "file:///project/src/main.rs"


# ── GET prompt ───────────────────────────────────────────────────────────────

def test_get_prompt() -> None:
    result = parse('GET prompt "code_review" { "language": "rust" }')
    gp = result.steps[0]
    assert isinstance(gp, GetPrompt)
    assert gp.name == "code_review"
    assert gp.arguments == {"language": "rust"}


def test_get_prompt_no_args() -> None:
    result = parse('GET prompt "simple"')
    gp = result.steps[0]
    assert gp.arguments == {}


# ── SUBSCRIBE ────────────────────────────────────────────────────────────────

def test_subscribe() -> None:
    result = parse('SUBSCRIBE "file:///project/src/main.rs"')
    s = result.steps[0]
    assert isinstance(s, Subscribe)
    assert s.uri == "file:///project/src/main.rs"


# ── LISTEN ───────────────────────────────────────────────────────────────────

def test_listen() -> None:
    result = parse('LISTEN "notifications/tools/list_changed" TIMEOUT 5000')
    ln = result.steps[0]
    assert isinstance(ln, Listen)
    assert ln.notification == "notifications/tools/list_changed"
    assert ln.timeout_ms == 5000


def test_listen_default_timeout() -> None:
    result = parse('LISTEN "notifications/test"')
    ln = result.steps[0]
    assert ln.timeout_ms == 5000


# ── SHUTDOWN ─────────────────────────────────────────────────────────────────

def test_shutdown() -> None:
    result = parse("SHUTDOWN")
    assert isinstance(result.steps[0], Shutdown)


# ── REQUIRE_CAPABILITY ──────────────────────────────────────────────────────

def test_require_capability() -> None:
    result = parse("REQUIRE_CAPABILITY prompts")
    rc = result.steps[0]
    assert isinstance(rc, RequireCapability)
    assert rc.capability == "prompts"


# ── ASSERT with various predicates ───────────────────────────────────────────

def test_assert_status_equals() -> None:
    result = parse("ASSERT STATUS == 200")
    a = result.steps[0]
    assert isinstance(a, Assert)
    assert a.query == "STATUS"
    assert a.predicate == "=="
    assert a.expected_value == 200


def test_assert_error_code_negative() -> None:
    result = parse("ASSERT STATUS == -32602")
    a = result.steps[0]
    assert a.expected_value == -32602


def test_assert_contains() -> None:
    result = parse('ASSERT result.content.text CONTAINS "critical"')
    a = result.steps[0]
    assert a.predicate == "CONTAINS"
    assert a.expected_value == "critical"


def test_assert_matches_regex() -> None:
    result = parse("ASSERT serverInfo.version MATCHES /^[0-9]+\\.[0-9]+\\.[0-9]+$/")
    a = result.steps[0]
    assert a.predicate == "MATCHES"
    assert a.expected_value == r"^[0-9]+\.[0-9]+\.[0-9]+$"


def test_assert_exists() -> None:
    result = parse('ASSERT tools[*] EXISTS name == "run_sql"')
    a = result.steps[0]
    assert a.predicate == "EXISTS"
    assert a.expected_value == 'name == "run_sql"'


def test_assert_count() -> None:
    result = parse("ASSERT tools COUNT >= 1")
    a = result.steps[0]
    assert a.predicate == "COUNT"
    assert a.expected_value == ">= 1"


def test_assert_boolean_true() -> None:
    result = parse("ASSERT isError == false")
    a = result.steps[0]
    assert a.expected_value is False


def test_assert_boolean_false() -> None:
    result = parse("ASSERT capabilities.tools.listChanged == true")
    a = result.steps[0]
    assert a.expected_value is True


def test_assert_null() -> None:
    result = parse("ASSERT error == null")
    a = result.steps[0]
    assert a.expected_value is None


# ── Fuzzy type matchers ──────────────────────────────────────────────────────

@pytest.mark.parametrize("fuzzy_str,type_name,optional", [
    ("#string", "string", False),
    ("#number", "number", False),
    ("#boolean", "boolean", False),
    ("#array", "array", False),
    ("#object", "object", False),
    ("##string", "string", True),
    ("##number", "number", True),
])
def test_fuzzy_type_matcher(fuzzy_str: str, type_name: str, optional: bool) -> None:
    result = parse(f"ASSERT result.x == {fuzzy_str}")
    a = result.steps[0]
    assert isinstance(a.expected_value, FuzzyType)
    assert a.expected_value.type_name == type_name
    assert a.expected_value.optional == optional


# ── Structural equality ──────────────────────────────────────────────────────

def test_assert_structural_equality() -> None:
    result = parse("""ASSERT result == {
  "type": "object",
  "properties": {
    "sql_query": { "type": "string" }
  }
}""")
    a = result.steps[0]
    assert a.predicate == "=="
    assert isinstance(a.expected_value, dict)
    assert a.expected_value["type"] == "object"


# ── CAPTURE ──────────────────────────────────────────────────────────────────

def test_capture_jsonpath() -> None:
    result = parse("CAPTURE next_cursor: result.nextCursor")
    c = result.steps[0]
    assert isinstance(c, Capture)
    assert c.variable == "next_cursor"
    assert c.query == "result.nextCursor"
    assert c.regex_pattern is None


def test_capture_with_regex() -> None:
    result = parse('CAPTURE item_id: result.content.text regex /"id":\\s*([0-9]+)/ 1')
    c = result.steps[0]
    assert c.variable == "item_id"
    assert c.query == "result.content.text"
    assert c.regex_pattern == '"id":\\s*([0-9]+)'
    assert c.regex_group == 1


def test_capture_with_regex_group_zero() -> None:
    result = parse('CAPTURE x: result.text regex /hello/')
    c = result.steps[0]
    assert c.regex_pattern == "hello"
    assert c.regex_group == 0


# ── Template strings ─────────────────────────────────────────────────────────

def test_template_in_string_value() -> None:
    result = parse('SET url = "https://{{host}}/api"')
    sv = result.steps[0]
    assert isinstance(sv, SetVar)
    assert isinstance(sv.value, TemplateString)
    assert sv.value.parts == [
        "https://",
        ("var", "host"),
        "/api",
    ]


def test_template_in_json_body() -> None:
    result = parse('CALL "t" { "id": "{{item_id}}" }')
    c = result.steps[0]
    # JSON body values that contain {{}} are parsed as TemplateStrings
    val = c.arguments["id"]
    assert isinstance(val, TemplateString)


# ── Comments and blank lines ─────────────────────────────────────────────────

def test_comments_ignored() -> None:
    result = parse("""# This is a comment
CONNECT stdio "server"
# Another comment
INITIALIZE protocolVersion="2025-03-26"
SHUTDOWN""")
    assert len(result.steps) == 3


def test_blank_lines_ignored() -> None:
    result = parse("""
CONNECT stdio "server"

INITIALIZE protocolVersion="2025-03-26"

SHUTDOWN
""")
    assert len(result.steps) == 3


# ── Error cases ──────────────────────────────────────────────────────────────

def test_missing_connect() -> None:
    # INITIALIZE without CONNECT is syntactically valid (validation at runtime)
    result = parse('INITIALIZE protocolVersion="2025-03-26"')
    assert len(result.steps) == 1
    assert isinstance(result.steps[0], Initialize)


def test_unknown_keyword() -> None:
    with pytest.raises(McphParseError, match="Unknown keyword"):
        parse("CONNECT stdio x\nFOOBAR\nSHUTDOWN")


def test_client_outside_initialize() -> None:
    with pytest.raises(McphParseError, match="CLIENT must appear inside"):
        parse('CONNECT stdio x\nCLIENT name="X" version="1"')


def test_capabilities_outside_client() -> None:
    with pytest.raises(McphParseError, match="CAPABILITIES must appear inside"):
        parse("CONNECT stdio x\nCAPABILITIES roots=true")


def test_empty_file() -> None:
    result = parse("")
    assert len(result.steps) == 0


def test_only_comments() -> None:
    result = parse("# just a comment\n# another one")
    assert len(result.steps) == 0


# ── Full conformance suite from the design doc ───────────────────────────────

FULL_CONFORMANCE_SUITE = """# ==============================================================================
# MCP-HURL (MCPH) CONFORMANCE TEST SUITE
# Target: Enterprise Logistics and Query Resolution Engine
# ==============================================================================

# ------------------------------------------------------------------------------
# Phase 1: Establish Transport and Execute Stateful Handshake
# ------------------------------------------------------------------------------
CONNECT stdio "python -m logistics_server --db-path /data/prod.db"
INITIALIZE protocolVersion="2025-03-26"
  CLIENT name="SystemComplianceSuite" version="4.2.0"
  CAPABILITIES roots=true sampling=true

ASSERT STATUS == 200
ASSERT protocolVersion == "2025-03-26"
ASSERT serverInfo.name == "LogisticsPro"
ASSERT serverInfo.version MATCHES /^[0-9]+\\.[0-9]+\\.[0-9]+$/
ASSERT capabilities.tools.listChanged == true
ASSERT capabilities.resources.subscribe == true

# ------------------------------------------------------------------------------
# Phase 2: Tool Discovery and Input Schema Verification
# ------------------------------------------------------------------------------
LIST tools
ASSERT STATUS == 200
ASSERT tools COUNT >= 1
ASSERT tools[*] EXISTS name == "execute_sql"
CAPTURE sql_tool_schema: tools[?(@.name=="execute_sql")].inputSchema

# ------------------------------------------------------------------------------
# Phase 3: Positive Tool Invocation and State Capture
# ------------------------------------------------------------------------------
CALL "execute_sql" {
  "sql_query": "SELECT id, warehouse_code, status FROM inventory WHERE status = 'critical';",
  "timeout_ms": 1000
}
ASSERT STATUS == 200
ASSERT isError == false
ASSERT result.content.type == "text"
ASSERT result.content.text CONTAINS "critical"

CAPTURE critical_item_id: result.content.text regex /"id":\\s*([0-9]+)/ 1

# ------------------------------------------------------------------------------
# Phase 4: Negative Boundary and Parameter Type Testing
# ------------------------------------------------------------------------------
CALL "execute_sql" {
  "sql_query": 99999,
  "timeout_ms": "one-second"
}
ASSERT STATUS == -32602
ASSERT error.message CONTAINS "Invalid params"

# ------------------------------------------------------------------------------
# Phase 5: Resource Listing, Validation, and Unauthorized Traversal Tests
# ------------------------------------------------------------------------------
REQUIRE_CAPABILITY resources
LIST resources
ASSERT STATUS == 200
ASSERT resources[*] EXISTS uri == "file:///logistics/configs/inventory_schema.json"

READ "file:///logistics/configs/inventory_schema.json"
ASSERT STATUS == 200
ASSERT result.contents.mimeType == "application/json"
ASSERT result.contents.text CONTAINS "inventory_items"

READ "file:///etc/passwd"
ASSERT STATUS == -32602

# ------------------------------------------------------------------------------
# Phase 6: Verify Prompts Management and Rendering
# ------------------------------------------------------------------------------
REQUIRE_CAPABILITY prompts
LIST prompts
ASSERT STATUS == 200
ASSERT prompts[*] EXISTS name == "audit_warehouse"

# ------------------------------------------------------------------------------
# Phase 7: Clean Teardown
# ------------------------------------------------------------------------------
SHUTDOWN
ASSERT STATUS == 200"""


def test_full_conformance_suite_parses() -> None:
    """The canonical conformance suite from the design doc must parse without errors."""
    result = parse(FULL_CONFORMANCE_SUITE)

    # Verify key structural properties
    assert len(result.steps) > 0

    # First step must be CONNECT
    assert isinstance(result.steps[0], Connect)

    # Must have INITIALIZE
    assert count_steps(result.steps, Initialize) >= 1

    # Must have LIST tools
    assert count_steps(result.steps, ListTools) >= 1

    # Must have LIST resources
    assert count_steps(result.steps, ListResources) >= 1

    # Must have LIST prompts
    assert count_steps(result.steps, ListPrompts) >= 1

    # Must have CALL steps
    assert count_steps(result.steps, CallTool) >= 2

    # Must have READ steps
    assert count_steps(result.steps, ReadResource) >= 2

    # Must have SHUTDOWN
    assert count_steps(result.steps, Shutdown) >= 1

    # Must have REQUIRE_CAPABILITY
    assert count_steps(result.steps, RequireCapability) >= 2

    # Must have ASSERT steps
    assert count_steps(result.steps, Assert) >= 15

    # Must have CAPTURE steps
    assert count_steps(result.steps, Capture) >= 2

    # Verify specific AST properties
    init = find_step(result.steps, Initialize)
    assert init.protocol_version == "2025-03-26"
    assert init.client_name == "SystemComplianceSuite"
    assert init.client_version == "4.2.0"
    assert init.capabilities == {"roots": True, "sampling": True}


def test_full_suite_last_step_is_shutdown() -> None:
    result = parse(FULL_CONFORMANCE_SUITE)
    # The suite ends with: SHUTDOWN\nASSERT STATUS == 200
    # Last step is SHUTDOWN, second-to-last is the trailing ASSERT
    assert isinstance(result.steps[-2], Shutdown)
    assert isinstance(result.steps[-1], Assert)


def test_full_suite_produces_testfile() -> None:
    result = parse(FULL_CONFORMANCE_SUITE)
    assert isinstance(result, TestFile)
    assert len(result.steps) == result.steps.__len__()


# ── Multi-line JSON with nested braces ───────────────────────────────────────

def test_nested_json_in_call() -> None:
    result = parse("""CALL "validate" {
  "schema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" }
    }
  }
}""")
    c = result.steps[0]
    assert isinstance(c, CallTool)
    assert c.name == "validate"
    assert c.arguments["schema"]["type"] == "object"
    assert c.arguments["schema"]["properties"]["name"]["type"] == "string"


def test_nested_json_in_assert() -> None:
    result = parse("""ASSERT sql_tool_schema == {
  "type": "object",
  "properties": {
    "sql_query": { "type": "string" },
    "timeout_ms": { "type": "integer" }
  },
  "required": ["sql_query"]
}""")
    a = result.steps[0]
    assert isinstance(a.expected_value, dict)
    assert a.expected_value["required"] == ["sql_query"]
    props = a.expected_value["properties"]
    assert props["sql_query"]["type"] == "string"
    assert props["timeout_ms"]["type"] == "integer"


# ── Edge case: JSON with braces in strings ───────────────────────────────────

def test_json_with_braces_in_strings() -> None:
    result = parse('CALL "t" { "pattern": "a{b}c" }')
    c = result.steps[0]
    assert c.arguments == {"pattern": "a{b}c"}


def test_json_with_escaped_quotes() -> None:
    result = parse(r'CALL "t" { "msg": "hello \"world\"" }')
    c = result.steps[0]
    assert c.arguments == {"msg": 'hello "world"'}
