# Phase 5: Assertion Engine

## Context

You are in `~/src/rmax-ai/mcph`. Phases 0-4 done (92 tests). Read AGENTS.md.

Existing:
- `src/mcph/ast.py` — `Assert(query, predicate, expected_value)`, `FuzzyType(type_name, optional)`, `TemplateString`
- `src/mcph/protocol.py` — `ProtocolEngine` returns JSON-RPC response dicts

## What to Build

### `src/mcph/assertion.py`

An assertion engine that evaluates `Assert` AST nodes against a JSON-RPC response
dict (the full message envelope: `{"jsonrpc": "2.0", "id": 1, "result": {...}}`).

```python
class AssertionEngine:
    def evaluate(self, assertion: Assert, response: dict[str, Any]) -> bool:
        """Evaluate a single assertion against a response dict.
        Returns True if assertion passes, raises AssertionError if it fails.
        """

class AssertionError(Exception):
    """Raised when an assertion fails, with details about expected vs actual."""
    def __init__(self, message: str, query: str, expected: Any, actual: Any): ...
```

### Query types

- `STATUS` — special query that checks the response envelope:
  - `STATUS == 200` → response has `"result"` key (success)
  - `STATUS == -32602` → response has `"error"` key with code -32602
  - `STATUS == <code>` → response `error.code` matches
- `jsonrpc` — checks the `"jsonrpc"` field
- `id` — checks the `"id"` field
- `serverInfo.name` — JSONPath into the result object
- `capabilities.tools.listChanged` — nested JSONPath
- `tools[*]` — array wildcard JSONPath
- `tools[?(@.name=="x")].inputSchema` — filter JSONPath
- `result.content.text` — nested JSONPath into result
- `result.content.type` — JSONPath
- `error.message` — JSONPath into error
- `isError` — checks `result.isError`
- `messages.role` — JSONPath
- `messages.content.text` — JSONPath

Use `jsonpath-ng` (already in deps) for JSONPath evaluation. For STATUS and
a few simple fields (isError, protocolVersion, serverInfo.name), do direct dict
lookup for speed.

### Predicates

- `==` — equality (handles int, str, bool, dict, list, FuzzyType)
- `!=` — inequality
- `>`, `>=`, `<`, `<=` — numeric comparison (convert both sides to float/int)
- `CONTAINS` — substring check (both sides must be strings)
- `MATCHES` — regex match (pattern is the expected_value string)
- `EXISTS` — JSONPath existence: the query returns a non-empty result
  where the query is like `tools[*]` and expected_value is `name == "run_sql"`
  Parsing: split expected_value on space-predicate-space, evaluate each
- `COUNT` — count of JSONPath matches. expected_value is `>= 1` or `== 5`
  Parsing: split expected_value on space, first word is count predicate

### Fuzzy type matching

When `expected_value` is a `FuzzyType`:
- `#string` — actual must be a `str`
- `#number` — actual must be `int` or `float`
- `#boolean` — actual must be `bool`
- `#array` — actual must be `list`
- `#object` — actual must be `dict`
- `##string` (optional) — if key exists, must be `str`; if key absent, passes

### Structural equality

When `expected_value` is a `dict`, compare recursively against the actual dict.
Allow extra keys in actual (subset match). For nested dicts, do the same.

When `expected_value` is a `TemplateString`, compare against the string
representation (template resolution happens in Phase 6 — here just treat
TemplateString as a plain string for equality).

### Error messages

Failed assertions produce clear messages:
```
ASSERT tools[*] EXISTS name == "run_sql": FAILED
  Expected: name == "run_sql" found in tools array
  Actual: no matching element found in [{"name": "other"}, ...]
```

### `tests/test_assertion.py`

Test with a MockTransport response dicts (no real servers needed).

Tests:
- `test_status_200` — response with "result" key passes
- `test_status_error_code` — response with error.code == -32602 passes
- `test_equality_string` — serverInfo.name == "expected"
- `test_equality_int` — numeric comparison
- `test_contains` — substring in response field
- `test_matches_regex` — regex match on response field
- `test_exists` — JSONPath existence check
- `test_count` — JSONPath count check
- `test_fuzzy_string` — #string matcher
- `test_fuzzy_optional` — ##string (present and correct, or absent)
- `test_fuzzy_wrong_type` — #string fails on int actual
- `test_structural_equality_dict` — dict subset match
- `test_inequality` — != predicate
- `test_numeric_greater_than` — > predicate
- `test_assertion_error_message` — verify error message format
- `test_jsonpath_nested` — deep JSONPath extraction
- `test_template_string_equality` — TemplateString compares as plain string

## Key Design Decisions

1. **jsonpath-ng** — use `jsonpath_ng.ext.parse(query).find(response)` for
   JSONPath queries. It returns `[DatumInContext]` matches.
2. **STATUS is special** — not a JSONPath query. Look at response dict directly
   for "result" vs "error" keys.
3. **CONTAINS/MATCHES** — the query extracts a string from the response, then
   check against expected_value.
4. **EXISTS** — two JSONPath queries: one to find the array, then check each
   element against the condition (e.g., `name == "run_sql"`).

## Verification

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_assertion.py -v
uv run pytest tests/ -v          # full suite — no regressions
```
