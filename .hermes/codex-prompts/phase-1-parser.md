# Phase 1: Parser & AST for MCP-Hurl (Mcph)

## Context

You are working in `~/src/rmax-ai/mcph`. This is Phase 1 of 10. Phase 0 is
done — the project scaffold (pyproject.toml, CLI stub, CI) is in place.

Read AGENTS.md for project conventions before starting.

## Architecture

The parser is a hand-written recursive descent parser (no parser generators).
The DSL is line-oriented with Hurl-like syntax. Multi-line JSON bodies are
delimited by braces `{ ... }`.

**Pipeline:** Raw text → Lexer (tokens) → Parser (AST) → Executor (later phases)

## What to Build

### 1. `src/mcph/ast.py` — AST Node Definitions

Define dataclasses for every AST node. Use Python 3.12 dataclasses with type hints.

Nodes required:

```
Connect(transport: str, target: str, timeout: int | None, retry: int | None)
Initialize(protocol_version: str, client_name: str | None, client_version: str | None, capabilities: dict | None)
Set(variable: str, value: str)
Header(name: str, value: str)
ListTools()
ListPrompts()
ListResources()
CallTool(name: str, arguments: dict)
ReadResource(uri: str)
GetPrompt(name: str, arguments: dict)
Subscribe(uri: str)
Listen(notification: str, timeout_ms: int)
Shutdown()
RequireCapability(capability: str)
Assert(query: str, predicate: str, expected_value: Any)
Capture(variable: str, query: str, regex_pattern: str | None, regex_group: int | None)
TestFile(steps: list)  # top-level container
```

Every node should have a `line_number: int` field for error reporting.

### 2. `src/mcph/exceptions.py` — Parse Errors

```python
class McphParseError(Exception):
    def __init__(self, message: str, line_number: int | None = None, source_line: str | None = None):
        ...
```

Format: `Error at line N: <message>\n  <source_line>\n  ^---`

### 3. `src/mcph/parser.py` — Lexer + Parser

The parser should handle:

**Connection:**
```
CONNECT stdio "python -m my_server"
CONNECT http "https://api.internal/mcp"
```

**Initialization block:**
```
INITIALIZE protocolVersion="2025-03-26"
CLIENT name="Mcph" version="1.0.0"
  CAPABILITIES roots=true sampling=true
```

The CLIENT block is optional. CAPABILITIES is a sub-block of CLIENT (indented).

**Variables and headers:**
```
SET myvar = "value"
SET _meta.protocolVersion = "DRAFT-2026-v1"
HEADER "Authorization" = "Bearer {{TOKEN}}"
```

**Discovery commands:**
```
LIST tools
LIST prompts
LIST resources
```

**Action commands:**
```
CALL "run_sql" { "query": "SELECT 1;", "timeout_ms": 1000 }
READ "file:///project/src/main.rs"
GET prompt "code_review" { "language": "rust" }
SUBSCRIBE "file:///project/src/main.rs"
```

Multi-line JSON bodies: the parser must collect lines between `{` and the matching `}`.

**Notification listening:**
```
LISTEN "notifications/tools/list_changed" TIMEOUT 5000
```

**Shutdown:**
```
SHUTDOWN
```

**Capability gates:**
```
REQUIRE_CAPABILITY prompts
REQUIRE_CAPABILITY resources
```

**Assertions:**
```
ASSERT STATUS == 200
ASSERT STATUS == -32602
ASSERT protocolVersion == "2025-03-26"
ASSERT serverInfo.name == "MyServer"
ASSERT serverInfo.version MATCHES /^[0-9]+\.[0-9]+\.[0-9]+$/
ASSERT capabilities.tools.listChanged == true
ASSERT tools[*] EXISTS name == "run_sql"
ASSERT tools COUNT >= 1
ASSERT isError == false
ASSERT result.content.text CONTAINS "critical"
ASSERT error.message CONTAINS "Invalid params"
ASSERT messages.role == "user"
ASSERT messages.content.text CONTAINS "{{critical_item_id}}"
```

Predicate types: `==`, `!=`, `>`, `>=`, `<`, `<=`, `CONTAINS`, `MATCHES`, `EXISTS`, `COUNT`.
Fuzzy type values (can appear as the expected value in assertions):
- `#string`, `#number`, `#boolean`, `#array`, `#object`
- `##string`, `##number` etc. (optional — matches if absent OR correct type)

Regex values: `/pattern/` — delimited by forward slashes.

**Captures:**
```
CAPTURE next_cursor: result.nextCursor
CAPTURE item_id: result.content.text regex /"id":\s*([0-9]+)/ 1
```

**Variable interpolation:** `{{variable_name}}` appears inside JSON bodies and
string values. The parser should NOT resolve these — just preserve them as-is
for runtime resolution. Tokenize them as `TemplateString` nodes.

**Comments:** Lines starting with `#` are comments. Skip them. Empty lines are
also skipped.

**JSON body parsing:** Use Python's `json.loads()` for JSON validation after
collecting the body text. Store as a dict in the AST node.

### 4. `tests/test_parser.py` — Tests

Test the full example suite from the design doc (this is the canonical
conformance test). Write tests for:

- Parsing a minimal valid `.mcph` file (CONNECT + INITIALIZE + SHUTDOWN)
- Parsing all assertion predicate types
- Parsing variable captures (JSONPath and regex)
- Parsing REQUIRE_CAPABILITY
- Parsing SET, HEADER directives
- Parsing multi-line JSON bodies in CALL and GET prompt
- Parsing fuzzy type matchers
- Error cases: missing CONNECT, malformed JSON, unknown keyword, unmatched brace
- Comment and blank line handling

## Key Design Decisions

1. **Hand-written parser, not a generator.** The DSL is simple enough (line-oriented
   with 15-ish keywords) that a recursive descent parser is clearer and produces
   better error messages than a generated parser.

2. **Line-numbered errors.** Every AST node carries a line_number. Parse errors
   reference the line where the error occurred. This is critical for DX — users
   debug .mcph files like code.

3. **JSON bodies via stdlib json.** After collecting the text between `{` and `}`,
   run it through `json.loads()` to validate. Embed the parsed dict in the AST node.

4. **Variable interpolation is lexical, not semantic.** The parser recognizes
   `{{x}}` as a template string. The capture registry resolves it at runtime.

## Don't Do

- Don't try to resolve variables — just parse `{{x}}` as a template marker
- Don't validate that LISTEN refers to a real notification — that's runtime
- Don't implement any transport or protocol code — that's Phase 2-4
- Don't add a CLI for the parser — the existing `mcph run` stub is enough

## Verification

After implementation:
```bash
uv sync --dev
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_parser.py -v
```

All tests must pass. Ruff and mypy must be clean.
