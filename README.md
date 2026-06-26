# MCP-Hurl (Mcph)

Declarative conformance testing DSL for [Model Context Protocol](https://modelcontextprotocol.io/) servers.

Hurl-inspired `.mcph` syntax. Custom Python async runner. Transport-agnostic (stdio + Streamable HTTP).

## Quick Start

```bash
pip install mcph
# or: uv tool install mcph
```

Write a test file:

```mcph
CONNECT stdio "python -m my_mcp_server"
INITIALIZE protocolVersion="2025-03-26"
CLIENT name="Mcph" version="1.0.0"
  CAPABILITIES roots=true

ASSERT STATUS == 200
ASSERT serverInfo.name == "MyServer"

LIST tools
ASSERT STATUS == 200
ASSERT tools[*] EXISTS name == "run_sql"

CALL "run_sql" { "query": "SELECT 1;" }
ASSERT STATUS == 200
ASSERT isError == false

SHUTDOWN
```

Run it:

```bash
mcph run conformance.mcph
```

## Features

- **Hurl-inspired syntax** — readable, self-documenting test files
- **Transport-agnostic** — stdio subprocesses and Streamable HTTP
- **JSON-RPC native** — first-class request/response/error handling
- **JSONPath, regex, fuzzy type assertions**
- **Variable capture** — extract values and inject into subsequent requests
- **Capability-aware** — skip tests for features the server doesn't support
- **JUnit/JSON reports** — CI-native output

## Status

Early development. See [PLAN.md](PLAN.md) for the implementation roadmap.
