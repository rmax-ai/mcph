<svelte:head>
  <title>Phases — MCP-Hurl</title>
</svelte:head>

<h1>Implementation Phases</h1>

<p>Mcph was built in 10 phases, tracked as GitHub issues with a state-machine
label system.</p>

<table><tbody>
  <tr><th>Phase</th><th>Component</th><th>Status</th></tr>
  <tr><td>0</td><td>Project Scaffold</td><td>✓</td></tr>
  <tr><td>1</td><td>Parser &amp; AST</td><td>✓</td></tr>
  <tr><td>2</td><td>Transport: stdio</td><td>✓</td></tr>
  <tr><td>3</td><td>Transport: Streamable HTTP</td><td>✓</td></tr>
  <tr><td>4</td><td>JSON-RPC Protocol Engine</td><td>✓</td></tr>
  <tr><td>5</td><td>Assertion Engine</td><td>✓</td></tr>
  <tr><td>6</td><td>Variable Capture &amp; Resolution</td><td>✓</td></tr>
  <tr><td>7</td><td>Session Manager &amp; Runtime</td><td>✓</td></tr>
  <tr><td>8</td><td>Reporting (JUnit, JSON, console)</td><td>✓</td></tr>
  <tr><td>9</td><td>CLI Polish &amp; Distribution</td><td>✓</td></tr>
  <tr><td>10</td><td>Integration Tests &amp; Example Suite</td><td>✓</td></tr>
</tbody></table>

<h2>Phase Details</h2>

<h3>Phase 0: Scaffold</h3>
<p>Project structure, pyproject.toml, CI pipeline (ruff, mypy, pytest), AGENTS.md.</p>

<h3>Phase 1: Parser &amp; AST</h3>
<p>Hand-written recursive descent parser producing an AST with 15 node types.
Supports all DSL keywords: CONNECT, INITIALIZE, LIST, CALL, READ, ASSERT,
CAPTURE, REQUIRE_CAPABILITY, SHUTDOWN.</p>

<h3>Phase 2-3: Transports</h3>
<p><strong>Stdio</strong> — async subprocess with newline-delimited JSON-RPC framing.
<strong>Streamable HTTP</strong> — httpx-based, Mcp-Session-Id header tracking.</p>

<h3>Phase 4: Protocol Engine</h3>
<p>JSON-RPC 2.0 envelopes, sequential request IDs, response validation,
initialize → notifications/initialized handshake.</p>

<h3>Phase 5: Assertion Engine</h3>
<p>JSONPath extraction, regex matching, fuzzy type matchers, structural dict
subset equality, clear error messages.</p>

<h3>Phase 6: Variable Capture</h3>
<p>JSONPath + regex extraction, recursive template resolution through dicts
and lists, nested variable path support.</p>

<h3>Phase 7: Runtime</h3>
<p>Full execution pipeline: parse → connect → initialize → execute → report.
Capability gating, soft/hard failure modes.</p>

<h3>Phase 8-9: Reporting &amp; CLI</h3>
<p>Console, JUnit XML, JSON reporters. Typer CLI with --transport, --command,
--url, --reporter, --env, --timeout flags.</p>

<h3>Phase 10: Integration</h3>
<p>E2E test against reference MCP echo server. Full conformance suite example.</p>

<h2>Test Suite</h2>

<p>139 tests across 8 test files:</p>

<ul>
  <li>64 parser tests (all keywords, edge cases, full conformance suite)</li>
  <li>12 stdio transport tests</li>
  <li>6 HTTP transport tests</li>
  <li>10 protocol engine tests</li>
  <li>17 assertion engine tests</li>
  <li>12 capture tests</li>
  <li>8 reporter tests</li>
  <li>5 runtime integration tests</li>
  <li>5 CLI + E2E tests</li>
</ul>

<p>Ruff clean, mypy strict, all passing.</p>
