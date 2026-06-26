<script>
  const diagram = `┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   .mcph file │ →  │    Parser    │ →  │     AST      │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                                               ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Reporter   │ ←  │   Runtime    │ ←  │   Session    │
│ JUnit, JSON  │    │  (runner)    │    │  (executor)  │
└──────────────┘    └──────────────┘    └──────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Protocol │ │ Assertion│ │ Capture  │
        │  Engine  │ │  Engine  │ │ Registry │
        └──────────┘ └──────────┘ └──────────┘
              │
              ▼
        ┌──────────┐
        │Transport │
        │ stdio/HTTP│
        └──────────┘`;
</script>

<svelte:head>
  <title>Architecture — MCP-Hurl</title>
</svelte:head>

<h1>Architecture</h1>

<p>Mcph is a Python async CLI built on six modular components:</p>

<h2>Component Overview</h2>
<pre><code>{diagram}</code></pre>

<h2>Modules</h2>

<h3>Parser (<code>src/mcph/parser.py</code>)</h3>
<p>Hand-written recursive descent parser. Line-oriented, Hurl-inspired syntax.
Produces an AST of 15 node types from <code>.mcph</code> source text.</p>

<h3>Transport (<code>src/mcph/transport/</code>)</h3>
<ul>
  <li><strong>StdioTransport</strong> — spawns MCP server as async subprocess,
  newline-delimited JSON-RPC framing, stderr isolation</li>
  <li><strong>HttpTransport</strong> — httpx-based, Mcp-Session-Id header tracking,
  POST to single MCP endpoint</li>
</ul>

<h3>Protocol Engine (<code>src/mcph/protocol.py</code>)</h3>
<p>Transport-agnostic JSON-RPC 2.0 layer. Sequential request IDs, response
validation, initialize → initialized handshake, method mapping.</p>

<h3>Assertion Engine (<code>src/mcph/assertion.py</code>)</h3>
<p>Evaluates assertions against protocol responses. JSONPath via
<code>jsonpath-ng</code>, regex matching, fuzzy type matchers
(<code>#string</code>, <code>#number</code>, <code>##object</code>),
structural dict subset equality.</p>

<h3>Capture Registry (<code>src/mcph/capture.py</code>)</h3>
<p>JSONPath + regex extraction from responses. Recursive
<code>{'{{'}var{'}}'}</code> template resolution through dicts and lists.
Nested variable path support.</p>

<h3>Runtime (<code>src/mcph/session.py</code>, <code>src/mcph/runner.py</code>)</h3>
<p>Orchestrates the full execution pipeline: parse → connect → initialize →
execute steps → report. <code>REQUIRE_CAPABILITY</code> gating, soft/hard failure
modes, transport cleanup.</p>

<h2>Design Decisions</h2>

<table><tbody>
  <tr><th>Decision</th><th>Rationale</th></tr>
  <tr><td>Python + uv</td><td>Strong JSON Schema ecosystem, async I/O, single-binary via PyInstaller</td></tr>
  <tr><td>Custom runner</td><td>Stdio lifecycle + JSON-RPC multiplexing fundamentally different from HTTP</td></tr>
  <tr><td>Hand-written parser</td><td>Clear error messages, no parser generator dependency</td></tr>
  <tr><td>Hurl-inspired syntax</td><td>Proven readability, familiar to developers</td></tr>
  <tr><td>Transport-agnostic</td><td>Same code tests local and remote servers</td></tr>
  <tr><td>AST-first</td><td>Enables future validation passes and compilation</td></tr>
</tbody></table>
