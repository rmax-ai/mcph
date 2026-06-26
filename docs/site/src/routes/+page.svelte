<script>
  import { base } from "$app/paths";

  const heroExample = `CONNECT stdio "python -m my_mcp_server"
INITIALIZE protocolVersion="2025-03-26"
CLIENT name="Mcph" version="1.0.0"
  CAPABILITIES roots=true

ASSERT STATUS == 200
ASSERT serverInfo.name == "MyServer"

LIST tools
ASSERT STATUS == 200
ASSERT tools COUNT >= 1

CALL "run_sql" { "query": "SELECT 1;" }
ASSERT STATUS == 200
ASSERT isError == false

SHUTDOWN`;

  const quickStart = `pip install mcph
mcph run conformance.mcph`;
</script>

<svelte:head>
  <title>MCP-Hurl (Mcph)</title>
</svelte:head>

<h1>MCP-Hurl (Mcph)</h1>

<p>MCP-Hurl is a declarative testing DSL for MCP servers. Hurl-inspired <code>.mcph</code>
syntax with a custom Python async runner. Transport-agnostic — stdio and
Streamable HTTP.</p>

<pre><code>{heroExample}</code></pre>

<h2>Quick Start</h2>
<pre><code>{quickStart}</code></pre>

<h2>Why Mcph?</h2>

<p>The Model Context Protocol is the standard interface between LLMs and tools. But
as organizations deploy MCP servers, verifying protocol compliance remains a gap.
Existing API testing tools are optimized for stateless HTTP — they can't handle
stdio subprocesses, JSON-RPC multiplexing, or the MCP capability handshake.</p>

<p>Mcph solves this with:</p>

<ul>
  <li><strong>Hurl-inspired syntax</strong> — readable, self-documenting, executable</li>
  <li><strong>First-class JSON-RPC</strong> — request IDs, error codes, notifications</li>
  <li><strong>Transport-agnostic</strong> — stdio subprocesses and Streamable HTTP</li>
  <li><strong>Structural assertions</strong> — JSONPath, regex, fuzzy types, schema validation</li>
  <li><strong>Capability-aware</strong> — skip tests for features the server doesn't support</li>
  <li><strong>CI-native</strong> — JUnit XML, JSON reports, exit codes</li>
</ul>

<h2>Features</h2>

<table><tbody>
  <tr><th>Feature</th><th>Description</th></tr>
  <tr><td><code>CONNECT</code></td><td>stdio subprocess or HTTP endpoint</td></tr>
  <tr><td><code>INITIALIZE</code></td><td>Stateful MCP handshake</td></tr>
  <tr><td><code>LIST</code></td><td>Discover tools, prompts, resources</td></tr>
  <tr><td><code>CALL</code></td><td>Invoke tools with JSON arguments</td></tr>
  <tr><td><code>READ</code></td><td>Read resources by URI</td></tr>
  <tr><td><code>ASSERT</code></td><td>JSONPath, regex, fuzzy type, structural equality</td></tr>
  <tr><td><code>CAPTURE</code></td><td>Extract values into variables</td></tr>
  <tr><td><code>{'{{'}var{'}}'}</code></td><td>Template interpolation</td></tr>
  <tr><td><code>REQUIRE_CAPABILITY</code></td><td>Skip tests for unsupported features</td></tr>
</tbody></table>

<p><a href={base + "/architecture/"}>Get started →</a></p>
