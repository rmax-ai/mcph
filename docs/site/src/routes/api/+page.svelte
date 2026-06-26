<script>
  const cliExample = `mcph run [OPTIONS] FILE`;

  const connExample = `CONNECT stdio "python -m my_server"
CONNECT http "https://api.internal/mcp"`;

  const initExample = `INITIALIZE protocolVersion="2025-03-26"
CLIENT name="Mcph" version="1.0.0"
  CAPABILITIES roots=true sampling=true`;

  const discoveryExample = `LIST tools
LIST prompts
LIST resources`;

  const toolExample = `CALL "tool_name" { "arg": "value", "num": 42 }`;

  const resourceExample = `READ "file:///path/to/resource"
SUBSCRIBE "file:///path/to/resource"`;

  const promptExample = `GET prompt "prompt_name" { "language": "rust" }`;

  const listenExample = `LISTEN "notifications/tools/list_changed" TIMEOUT 5000`;

  const assertExample = `ASSERT STATUS == 200
ASSERT STATUS == -32602
ASSERT serverInfo.name == "Expected"
ASSERT serverInfo.version MATCHES /^[0-9]+\\.[0-9]+\\.[0-9]+$/
ASSERT tools COUNT >= 1
ASSERT tools[*] EXISTS name == "run_sql"
ASSERT result.content.text CONTAINS "expected"
ASSERT isError == false

# Fuzzy types
ASSERT result.x == #string
ASSERT result.y == ##number

# Structural equality
ASSERT schema == {
  "type": "object",
  "properties": {
    "name": { "type": "string" }
  }
}`;

  const captureExample = `CAPTURE var_name: result.field
CAPTURE var_name: result.text regex /pattern/ 1

CALL "tool" { "ref": "{{var_name}}" }`;

  const gatingExample = `REQUIRE_CAPABILITY prompts
LIST prompts

REQUIRE_CAPABILITY resources
LIST resources`;

  const injectExample = `SET _meta.protocolVersion = "DRAFT-2026-v1"
HEADER "Authorization" = "Bearer {{TOKEN}}"`;

  const shutdownExample = `SHUTDOWN`;
</script>

<svelte:head>
  <title>API Reference — MCP-Hurl</title>
</svelte:head>

<h1>API Reference</h1>

<h2>CLI</h2>
<pre><code>{cliExample}</code></pre>

<table><tbody>
  <tr><th>Flag</th><th>Description</th></tr>
  <tr><td><code>--transport stdio|http</code></td><td>Transport type (default: stdio)</td></tr>
  <tr><td><code>--command TEXT</code></td><td>Server command for stdio</td></tr>
  <tr><td><code>--url TEXT</code></td><td>Server URL for HTTP</td></tr>
  <tr><td><code>--reporter console|junit|json</code></td><td>Report format (repeatable)</td></tr>
  <tr><td><code>--timeout SECONDS</code></td><td>Request timeout (default: 30)</td></tr>
  <tr><td><code>--continue-on-failure</code></td><td>Run all steps even if some fail</td></tr>
  <tr><td><code>--verbose</code></td><td>Show transport trace</td></tr>
  <tr><td><code>--env KEY=VALUE</code></td><td>Pass variable (repeatable)</td></tr>
  <tr><td><code>--version</code></td><td>Show version</td></tr>
  <tr><td><code>--help</code></td><td>Show help</td></tr>
</tbody></table>

<h2>DSL Syntax</h2>

<h3>Connection</h3>
<pre><code>{connExample}</code></pre>

<h3>Initialization</h3>
<pre><code>{initExample}</code></pre>

<h3>Discovery</h3>
<pre><code>{discoveryExample}</code></pre>

<h3>Tool Execution</h3>
<pre><code>{toolExample}</code></pre>

<h3>Resource Access</h3>
<pre><code>{resourceExample}</code></pre>

<h3>Prompts</h3>
<pre><code>{promptExample}</code></pre>

<h3>Notifications</h3>
<pre><code>{listenExample}</code></pre>

<h3>Assertions</h3>
<pre><code>{assertExample}</code></pre>

<h3>Predicates</h3>
<table><tbody>
  <tr><th>Predicate</th><th>Description</th></tr>
  <tr><td><code>==</code></td><td>Equality</td></tr>
  <tr><td><code>!=</code></td><td>Inequality</td></tr>
  <tr><td><code>&gt;</code>, <code>&gt;=</code>, <code>&lt;</code>, <code>&lt;=</code></td><td>Numeric comparison</td></tr>
  <tr><td><code>CONTAINS</code></td><td>Substring check</td></tr>
  <tr><td><code>MATCHES /pattern/</code></td><td>Regex match</td></tr>
  <tr><td><code>EXISTS</code></td><td>JSONPath element existence</td></tr>
  <tr><td><code>COUNT</code></td><td>JSONPath match count</td></tr>
</tbody></table>

<h3>Fuzzy Types</h3>
<table><tbody>
  <tr><th>Type</th><th>Description</th></tr>
  <tr><td><code>#string</code></td><td>Must be a string</td></tr>
  <tr><td><code>#number</code></td><td>Must be int or float</td></tr>
  <tr><td><code>#boolean</code></td><td>Must be bool</td></tr>
  <tr><td><code>#array</code></td><td>Must be list</td></tr>
  <tr><td><code>#object</code></td><td>Must be dict</td></tr>
  <tr><td><code>##string</code></td><td>Optional: if present, must be string</td></tr>
</tbody></table>

<h3>Variable Capture</h3>
<pre><code>{captureExample}</code></pre>

<h3>Capability Gating</h3>
<pre><code>{gatingExample}</code></pre>

<h3>Variable Injection</h3>
<pre><code>{injectExample}</code></pre>

<h3>Teardown</h3>
<pre><code>{shutdownExample}</code></pre>
