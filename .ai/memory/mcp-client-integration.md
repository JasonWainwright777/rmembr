---
title: MCP Client Integration
---

# MCP Client Integration (VS Code, Claude, Codex)

Primary references:

- `examples/mcp-client-setup.md`
- `docs/integration/vscode-mcp.md`
- `docs/integration/claude-code-mcp.md`

## Server Preconditions

- local stack running (`docker compose up -d`)
- at least one indexed repo
- gateway reachable on `localhost:8080`
- `MCP_ENABLED=true` in runtime env

## Transport Mapping

- Streamable HTTP endpoint: `/mcp`
- Legacy SSE endpoint: `/mcp/sse` and `/mcp/messages/`

Use client-native transport support; both expose the same tool set.

## Client Config Patterns

VS Code:

- workspace `.vscode/mcp.json`
- should target `/mcp` as the primary endpoint using HTTP transport

Claude Code:

- project `.mcp.json`
- should target `/mcp` as the primary endpoint using HTTP transport; SSE remains available for compatibility

Codex CLI:

- `~/.codex/config.json` or project-level `.codex/config.json`
- config points to the same gateway MCP endpoint

## Operational Notes

- `index_repo` and `index_all` are writer-role tools.
- read-only tools remain available to default reader role.
- connection failures are usually one of:
  - gateway down
  - `MCP_ENABLED` disabled
  - wrong config file location
  - transport mismatch
