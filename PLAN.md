# MCP-Hurl (Mcph) — Implementation Plan

> **For Hermes:** Use Codex CLI with git worktrees to implement this plan phase-by-phase.

**Goal:** Build a declarative CLI testing tool for MCP servers that uses a Hurl-inspired `.mcph` DSL, supports stdio and Streamable HTTP transports, and produces JUnit/JSON reports.

**Architecture:** Python async CLI (uv/typer) with six internal modules (parser, session, transport, protocol, assertion, reporting). Hurl-inspired syntax compiled to an AST, executed by a custom protocol-aware runner against stdio subprocesses or HTTP endpoints.

**Tech Stack:** Python 3.12+, uv, typer, anyio, jsonpath-ng, jsonschema, pytest, ruff, mypy

---

## Acceptance Criteria

- [ ] `CONNECT stdio "python -m my_server"` spawns subprocess and completes `initialize` → `initialized` handshake
- [ ] `CONNECT http "https://..."` negotiates Streamable HTTP session with Mcp-Session-Id header tracking
- [ ] `ASSERT STATUS == 200` on valid responses passes
- [ ] `ASSERT tools[*] EXISTS name == "run_sql"` JSONPath structural assertion passes
- [ ] `CAPTURE x: result.id` stores value and `{{x}}` resolves in subsequent requests
- [ ] `REQUIRE_CAPABILITY prompts` skips downstream assertions when capability absent
- [ ] `INITIALIZE protocolVersion="2025-03-26"` validates protocol version
- [ ] Invalid JSON-RPC response (missing jsonrpc field) fails with clear error
- [ ] Stdio server timeout kills subprocess and reports failure
- [ ] JUnit XML and JSON reports produced on `--reporter junit --reporter json`
- [ ] `mcph --help` shows all commands
- [ ] `mcph run suite.mcph` exits 0 on pass, 1 on failure
- [ ] All tests pass under `uv run pytest`

---

## Implementation Phases

### Phase 0: Project Scaffold

**Objective:** Create the repo, project structure, and CI pipeline.

**Files:**
- Create: `pyproject.toml`, `README.md`, `LICENSE`, `.gitignore`, `AGENTS.md`
- Create: `.github/workflows/ci.yml`
- Create: `src/mcph/__init__.py`, `src/mcph/cli.py`

**Acceptance:**
- [ ] `uv sync --dev` installs deps without errors
- [ ] `uv run ruff check src/` passes
- [ ] `uv run mcph --help` shows usage

---

### Phase 1: Parser & AST

**Objective:** Lex, parse, and compile a `.mcph` file into an AST. Support all keywords from the DSL spec: CONNECT, INITIALIZE, LIST, CALL, READ, GET prompt, SUBSCRIBE, LISTEN, SHUTDOWN, SET, ASSERT, CAPTURE, REQUIRE_CAPABILITY, HEADER.

**Files:**
- Create: `src/mcph/parser.py`, `src/mcph/ast.py`, `src/mcph/exceptions.py`
- Create: `tests/test_parser.py`

**Acceptance:**
- [ ] Parser produces valid AST for the full example suite from the design doc
- [ ] Parser rejects malformed syntax with clear line-numbered errors
- [ ] Variable interpolation `{{x}}` is parsed but not resolved (resolution happens at runtime)
- [ ] JSON bodies are parsed as Python dicts, not strings
- [ ] Regex captures (`CAPTURE x: result.content.text regex /pattern/ 1`) produce correct AST nodes
- [ ] Fuzzy types (`#string`, `#number`, `#boolean`, `#array`, `#object`, `##type`) parse correctly

---

### Phase 2: Transport Layer (stdio)

**Objective:** Spawn subprocesses, manage stdin/stdout/stderr, handle JSON-RPC newline-delimited framing.

**Files:**
- Create: `src/mcph/transport/__init__.py`, `src/mcph/transport/stdio.py`
- Create: `tests/test_transport_stdio.py`

**Acceptance:**
- [ ] `StdioTransport("python -m my_server")` spawns subprocess and connects stdin/stdout
- [ ] Stderr is captured to a separate buffer (not mixed with protocol stream)
- [ ] Send/receive JSON-RPC messages with newline-delimited framing
- [ ] Timeout kills subprocess cleanly (SIGTERM → SIGKILL escalation)
- [ ] Subprocess crash produces clear error, not silent hang

---

### Phase 3: Transport Layer (Streamable HTTP)

**Objective:** Connect to remote MCP servers via HTTP, handle Mcp-Session-Id, Accept headers, SSE streaming.

**Files:**
- Create: `src/mcph/transport/http_transport.py`
- Create: `tests/test_transport_http.py`

**Acceptance:**
- [ ] HTTP transport POSTs JSON-RPC to endpoint and reads response
- [ ] Mcp-Session-Id header tracked across requests
- [ ] Accept: application/json, text/event-stream header set
- [ ] Server connection refusal returns clean error

---

### Phase 4: JSON-RPC Protocol Engine

**Objective:** Wrap abstract test operations into compliant JSON-RPC envelopes, track request IDs, decode responses.

**Files:**
- Create: `src/mcph/protocol.py`
- Create: `tests/test_protocol.py`

**Acceptance:**
- [ ] `INITIALIZE protocolVersion="2025-03-26"` produces valid `initialize` request
- [ ] CLIENT block sets clientInfo and capabilities
- [ ] Response ID matches request ID
- [ ] Error responses (with `error` field) are distinguished from success responses
- [ ] `notifications/initialized` sent after successful initialize response
- [ ] Sequentially incremented request IDs

---

### Phase 5: Assertion Engine

**Objective:** Evaluate JSONPath extractions, regex matches, schema validations, fuzzy type matchers.

**Files:**
- Create: `src/mcph/assertion.py`
- Create: `tests/test_assertion.py`

**Acceptance:**
- [ ] `ASSERT STATUS == 200` works (translates to JSON-RPC result presence check)
- [ ] `ASSERT STATUS == -32602` validates error code
- [ ] `ASSERT tools[*] EXISTS name == "run_sql"` JSONPath structural match works
- [ ] `ASSERT result.content.text CONTAINS "critical"` substring match works
- [ ] `ASSERT error.message MATCHES /pattern/` regex match works
- [ ] `#string`, `#number`, `#boolean`, `#array`, `#object` fuzzy matchers work
- [ ] `##type` optional matcher works (present+correct or absent)
- [ ] Failed assertions produce clear error messages with expected vs actual

---

### Phase 6: Variable Capture & Resolution

**Objective:** Extract values from responses and inject them into subsequent requests.

**Files:**
- Create: `src/mcph/capture.py`
- Create: `tests/test_capture.py`

**Acceptance:**
- [ ] `CAPTURE x: result.id` extracts value and stores in registry
- [ ] `{{x}}` in subsequent request bodies resolves to captured value
- [ ] Regex captures (`CAPTURE x: result.text regex /pattern/ 1`) extract group
- [ ] Failed capture (missing path, no regex match) aborts run with clear error

---

### Phase 7: Session Manager & Runtime

**Objective:** Wire all modules together — parse .mcph, initialize transport, execute steps, run assertions, manage state.

**Files:**
- Create: `src/mcph/session.py`, `src/mcph/runner.py`
- Create: `tests/test_runner.py`

**Acceptance:**
- [ ] Full `.mcph` file executes from CONNECT through SHUTDOWN
- [ ] REQUIRE_CAPABILITY gates work (skip downstream steps if capability absent)
- [ ] Stateful handshake completes: initialize → response → initialized notification
- [ ] Soft-assertion mode (`--continue-on-failure`) collects all failures
- [ ] Hard-assertion mode (default) exits on first failure

---

### Phase 8: Reporting

**Objective:** JUnit XML, JSON, and console reporters.

**Files:**
- Create: `src/mcph/reporter.py`
- Create: `tests/test_reporter.py`

**Acceptance:**
- [ ] `--reporter junit` writes valid JUnit XML
- [ ] `--reporter json` writes structured JSON with pass/fail per assertion
- [ ] Console output shows ✓/✗ per step with timing
- [ ] Exit code 0 on all pass, 1 on any failure

---

### Phase 9: CLI Polish & Distribution

**Objective:** Clean CLI UX, `--help`, `--version`, single-binary packaging.

**Files:**
- Modify: `src/mcph/cli.py`
- Create: `scripts/build.sh`

**Acceptance:**
- [ ] `mcph --help` shows all subcommands
- [ ] `mcph run suite.mcph` is the main command
- [ ] `mcph run --transport stdio --command "python -m my_server" suite.mcph` works
- [ ] `mcph run --transport http --url "https://..." suite.mcph` works
- [ ] `--env KEY=VALUE` passes variables
- [ ] `--timeout 30` sets global timeout
- [ ] `--verbose` shows transport trace

---

### Phase 10: Integration Tests & Example Suite

**Objective:** End-to-end test against a reference MCP server.

**Files:**
- Create: `tests/integration/test_e2e_stdio.py`
- Create: `examples/echo-server.py` (minimal stdio MCP server)
- Create: `examples/conformance.mcph` (full conformance suite from design doc)

**Acceptance:**
- [ ] Echo server passes conformance suite
- [ ] Integration test runs in CI
- [ ] Example `.mcph` file is self-documenting with comments
