# Phase 6: Variable Capture & Resolution

## Context

You are in `~/src/rmax-ai/mcph`. Phases 0-5 done (109 tests). Read AGENTS.md.

Existing:
- `src/mcph/ast.py` — `Capture(variable, query, regex_pattern, regex_group)`, `TemplateString(parts)`
- `src/mcph/parser.py` — `{{var}}` parsed as TemplateString, regex captures parsed
- `src/mcph/assertion.py` — `AssertionEngine` with jsonpath-ng

## What to Build

### `src/mcph/capture.py`

A variable capture registry that extracts values from responses and resolves them
in subsequent requests.

```python
class CaptureRegistry:
    def __init__(self):
        self._vars: dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        """Set a variable directly (from SET directive)."""

    def capture(self, capture: Capture, response: dict[str, Any]) -> None:
        """Extract a value from a response using JSONPath (and optional regex).
        Raises CaptureError if extraction fails.
        """

    def resolve(self, value: Any) -> Any:
        """Recursively resolve TemplateStrings and strings with {{var}} patterns.
        Returns the resolved value (plain types).
        """

class CaptureError(Exception):
    """Raised when a capture extraction fails."""
```

Key behaviors:

- **JSONPath capture** — `CAPTURE x: result.id` → use jsonpath-ng to extract
  `result.id` from the response, store as `x`
- **Regex capture** — `CAPTURE x: result.text regex /pattern/ 1` → extract
  JSONPath first, then apply regex, capture group 1
- **SET directive** — `SET _meta.protocolVersion = "value"` → store directly
- **Template resolution** — `{{x}}` replaced with stored value. Support nested
  paths: `{{x.y.z}}` looks up dict keys recursively
- **Recursive resolution** — resolve templates inside dicts and lists:
  `{"id": "{{item_id}}", "data": {"ref": "{{ref_id}}"}}` → both resolved
- **Missing variable** — raise `CaptureError(f"Variable 'x' not found")` with
  available variables listed
- **re.search().group(n)** — for regex captures

### `tests/test_capture.py`

Tests:
- `test_capture_jsonpath` — extract simple field
- `test_capture_nested_jsonpath` — extract nested field
- `test_capture_regex` — extract via regex group
- `test_capture_regex_no_match` — raises CaptureError
- `test_set_variable` — direct set
- `test_resolve_simple` — {{x}} → stored value
- `test_resolve_nested` — {{x.y.z}} → nested dict lookup
- `test_resolve_in_dict` — recursive dict resolution
- `test_resolve_in_list` — recursive list resolution
- `test_resolve_missing_variable` — raises CaptureError
- `test_resolve_no_templates` — plain string passes through unchanged
- `test_capture_missing_path` — JSONPath returns empty → raises CaptureError

## Key Design Decisions

1. **jsonpath-ng** — same library as assertion engine. Use `jsonpath_ng.ext.parse()`.
2. **Resolution is recursive** — walk dicts, lists, TemplateStrings, strings.
   For plain strings, check for `{{...}}` patterns and resolve.
3. **Plain values pass through** — ints, bools, None, FuzzyType objects are
   returned as-is.

## Verification

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_capture.py -v
uv run pytest tests/ -v          # full suite — no regressions
```
