# Phase 8: Reporting

## Context

You are in `~/src/rmax-ai/mcph`. Phases 0-6 done, Phase 7 (session/runner) done. Read AGENTS.md.

Existing:
- `src/mcph/session.py` — `Session`, `StepResult(passed, message, duration_ms, error)`
- `src/mcph/runner.py` — `run_file()`, `run_file_sync()`

## What to Build

### `src/mcph/reporter.py`

Reporters that consume `list[StepResult]` and produce output.

```python
class ConsoleReporter:
    """Prints ✓/✗ per step with timing to stdout."""
    def report(self, results: list[StepResult]) -> str: ...

class JUnitReporter:
    """Produces JUnit XML string."""
    def report(self, results: list[StepResult], suite_name: str = "mcph") -> str: ...

class JsonReporter:
    """Produces structured JSON string."""
    def report(self, results: list[StepResult]) -> str: ...

def write_reports(results: list[StepResult], reporters: list[str], output_dir: str = ".") -> None:
    """Write reports to files: mcph-report.junit.xml, mcph-report.json, console output."""
```

### Console output format

```
mcph v0.1.0 — conformance.mcph
──────────────────────────────────────
  ✓ CONNECT stdio "echo-server"         (12ms)
  ✓ INITIALIZE protocolVersion="2025-03-26" (45ms)
  ✓ LIST tools                          (8ms)
  ✗ ASSERT tools COUNT >= 5             (1ms)
    Expected: >= 5, Actual: 3
  ✓ SHUTDOWN                             (3ms)
──────────────────────────────────────
4 passed, 1 failed, 0 skipped (69ms)
```

### JUnit XML format

Standard JUnit `<testsuite>` with `<testcase>` elements. Each step is a test case:
```xml
<testsuite name="mcph" tests="5" failures="1" time="0.069">
  <testcase name="CONNECT stdio echo-server" time="0.012"/>
  <testcase name="INITIALIZE protocolVersion=2025-03-26" time="0.045"/>
  ...
  <testcase name="ASSERT tools COUNT &gt;= 5" time="0.001">
    <failure message="Expected: >= 5, Actual: 3"/>
  </testcase>
</testsuite>
```

Escaping: use `xml.sax.saxutils.escape()` for special chars in names/messages.

### JSON format

```json
{
  "version": "0.1.0",
  "file": "conformance.mcph",
  "summary": {"passed": 4, "failed": 1, "skipped": 0, "duration_ms": 69},
  "steps": [
    {"step": "CONNECT", "detail": "stdio echo-server", "passed": true, "duration_ms": 12},
    {"step": "ASSERT", "detail": "tools COUNT >= 5", "passed": false, "duration_ms": 1,
     "error": "Expected: >= 5, Actual: 3"}
  ]
}
```

### `tests/test_reporter.py`

Tests:
- `test_console_reporter_all_pass` — ✓ for each step
- `test_console_reporter_mixed` — mix of ✓ and ✗
- `test_junit_reporter_structure` — valid XML with correct test counts
- `test_junit_reporter_failure` — failure element present
- `test_json_reporter_structure` — valid JSON with summary counts
- `test_json_reporter_failure` — error field present on failed steps
- `test_write_reports_creates_files` — junit.xml and json files created
- `test_empty_results` — zero steps handled gracefully

### Update `src/mcph/cli.py`

Wire the runner + reporters into the CLI:
```python
@app.command()
def run(
    file: str = typer.Argument(...),
    transport: str = typer.Option("stdio", help="Transport: stdio or http"),
    command: str = typer.Option(None, help="Server command (stdio)"),
    url: str = typer.Option(None, help="Server URL (http)"),
    reporter: list[str] = typer.Option(["console"], help="Reporters: console, junit, json"),
    timeout: float = typer.Option(30.0, help="Timeout in seconds"),
    continue_on_failure: bool = typer.Option(False, help="Continue after failures"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Run a .mcph conformance test suite."""
    ...
```

The CLI should:
1. Parse the .mcph file
2. Override CONNECT target from --command or --url flags if provided
3. Create SessionConfig from CLI flags
4. Run the session
5. Write reports
6. Exit 0 on all pass, 1 on any failure

## Key Design Decisions

1. **Reporters are plain functions** — no async needed for string generation
2. **JUnit uses stdlib xml.etree** — no external XML dependency
3. **Exit code** — `sys.exit(0 if all passed else 1)`
4. **Step naming in reports** — format as `KEYWORD detail`, e.g.
   `ASSERT tools COUNT >= 5`, `CALL run_sql`, `CONNECT stdio echo`

## Verification

```bash
uv run ruff check src/ tests/ && uv run ruff format src/ tests/
uv run mypy src/
uv run pytest tests/test_reporter.py -v
uv run pytest tests/ -v          # full suite
uv run mcph --help               # CLI works
```
