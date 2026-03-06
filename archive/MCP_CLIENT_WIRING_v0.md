# MCP_CLIENT_WIRING_v0 — Execution Plan

Date: 2026-03-06
Builder: Claude Sonnet 4.6

---

## Pre-conditions

Before executing any phase, verify:
- Docker Desktop is running and the gateway image has been built at least once (`docker compose build gateway`)
- `localhost:8080` is not occupied by another process (`curl -I http://localhost:8080/health`)
- You are in the `mcp-memory-local/` directory (or pass `-f` to `docker compose` commands)

---

## Current State

The gateway already has a full MCP server implementation:
- 9 tools registered: `search_repo_memory`, `get_context_bundle`, `explain_context_bundle`,
  `validate_pack`, `index_repo`, `index_all`, `list_standards`, `get_standard`, `get_schema`
- SSE transport at `/mcp/sse` + `/mcp/messages/` (`mcp_server.py`)
- Stdio transport via `mcp_stdio_shim.py` (runs inside the gateway container)
- Both gated by `MCP_ENABLED=true` env var (default: `false`)
- Gateway exposes port `8080` to host — no auth required on gateway-facing routes

**Nothing new needs to be built. This plan is purely configuration.**

---

## Transport Decision

| Client | Transport | Reason |
|--------|-----------|--------|
| Claude Code | SSE | Native SSE support; gateway already on localhost:8080 |
| VSCode + GitHub Copilot | SSE | VSCode MCP (1.99+) supports SSE natively |
| OpenAI Codex CLI | SSE | Simplest; one URL, no wrapper script needed |

Stdio is available for all clients via a wrapper script but is not needed since the SSE
endpoint is already exposed on `localhost:8080`.

---

## Scope of Changes

| File | Action |
|------|--------|
| `mcp-memory-local/docker-compose.yml` | Edit — set `MCP_ENABLED=true` |
| `mcp-memory-local/.env.example` | Edit — document `MCP_ENABLED` |
| `.claude/settings.json` | Edit — add rmembr MCP server (SSE) |
| `.vscode/mcp.json` | New — workspace MCP config for Copilot |
| `mcp-memory-local/scripts/mcp-stdio-wrapper.sh` | New — optional stdio bridge script |

---

## Phase 1 — Enable MCP in the gateway

**Goal:** Set `MCP_ENABLED=true` as the default in the gateway so the SSE endpoint is active on every `docker compose up` without manual env-var overrides.

**Success criteria (V1):** `curl -N http://localhost:8080/mcp/sse` returns HTTP 200 with `Content-Type: text/event-stream` and keeps the connection open.

### 1.1 docker-compose.yml
Add to the `gateway` service environment block:
```yaml
MCP_ENABLED: ${MCP_ENABLED:-true}
MCP_STDIO_ENABLED: ${MCP_STDIO_ENABLED:-false}
```

Change the default from `false` to `true` so the SSE endpoint is active on every
`docker compose up` without manual env var setting.

### 1.2 .env.example
Add to the MCP Protocol section:
```
MCP_ENABLED=true
MCP_STDIO_ENABLED=false
```

### 1.3 Restart + verify
```bash
docker compose up -d gateway          # restarts with updated env; image already built
curl -N http://localhost:8080/mcp/sse  # V1: should open SSE stream (Ctrl-C to exit)
```
If the curl returns 404 or a connection-refused error, check `docker compose logs gateway | grep MCP` to confirm the env var was picked up.

**Rollback:** Revert the `MCP_ENABLED` line in `docker-compose.yml` to `${MCP_ENABLED:-false}` and restart the gateway.

---

## Phase 2 — Claude Code

**Goal:** Register the rmembr SSE endpoint as an MCP server in the project's Claude Code config so all 9 tools are available in every Claude Code session for this repo.

**Success criteria (V2, V3):** `/mcp` lists `rmembr` as connected with 9 tools; a natural-language query about "provider framework" returns chunked memory results via `search_repo_memory`.

Claude Code reads MCP config from `.claude/settings.json` (project-level, committed)
or `~/.claude/settings.json` (user-level, not committed).

Use the **project-level** file (`.claude/settings.json`) so the server is available
to anyone who clones the repo and runs `docker compose up`.

### Config to add
```json
{
  "mcpServers": {
    "rmembr": {
      "type": "sse",
      "url": "http://localhost:8080/mcp/sse"
    }
  }
}
```

### Verification (V2 + V3)
In Claude Code, run:
```
/mcp
```
The `rmembr` server should appear as connected with all 9 tools listed.

Then ask: *"Search rmembr for provider framework"* — expect a tool call to `search_repo_memory` and chunked results.

**Rollback:** Remove the `"rmembr"` block from `.claude/settings.json` and restart Claude Code.

---

## Phase 3 — VSCode + GitHub Copilot

**Goal:** Make all 9 rmembr tools available to GitHub Copilot agent mode for any contributor who opens this repo in VSCode ≥ 1.99.

**Success criteria (V4, V5):** rmembr tools appear in the `#` tool picker in Copilot Chat agent mode; a query about "github provider" executes `search_repo_memory` and returns results.

VSCode 1.99+ (April 2025) added native MCP support in GitHub Copilot agent mode.
MCP servers are configured via `.vscode/mcp.json` (workspace) or user settings.

Use workspace-level `.vscode/mcp.json` so it works for any contributor.

### .vscode/mcp.json
```json
{
  "servers": {
    "rmembr": {
      "type": "sse",
      "url": "http://localhost:8080/mcp/sse"
    }
  }
}
```

### Enabling in VSCode (V4 + V5)
1. Install GitHub Copilot extension (v1.x or later, with agent mode)
2. Open Command Palette → `GitHub Copilot: Open Chat`
3. Switch to **Agent mode** (dropdown in chat input, select `@agent` or agent icon)
4. The `rmembr` MCP tools will be available automatically
5. Verify (V4): type `#` in Copilot Chat — rmembr tools (`search_repo_memory`, etc.) should appear
6. Verify (V5): ask *"Search rmembr for github provider"* — tool call should execute and return results

**Rollback:** Delete `.vscode/mcp.json` (or remove the `rmembr` entry) and reload the VSCode window.

### Requirements
- VSCode ≥ 1.99
- GitHub Copilot extension with Chat + agent mode enabled
- `chat.mcp.enabled: true` in VSCode user settings (may be on by default in 1.99+)

---

## Phase 4 — OpenAI Codex CLI

**Goal:** Add rmembr as an MCP server in the user-level Codex CLI config so tools are available in all `codex` sessions on this machine.

**Success criteria (V6):** A `codex` session can list or call `search_repo_memory` without errors.

OpenAI Codex CLI (`codex`) supports MCP via `~/.codex/config.toml` (Streamable HTTP servers).
See: https://developers.openai.com/codex/mcp

### ~/.codex/config.toml (user-level, not committed)
Add the following section:
```toml
[mcp_servers.rmembr]
url = "http://localhost:8080/mcp"
```

Or via CLI:
```bash
codex mcp add rmembr --url http://localhost:8080/mcp
```

### Verification (V6)
```bash
# In the Codex TUI, use /mcp to view active servers
codex "use the rmembr search_repo_memory tool to find provider framework"
# rmembr tools should be available; expect a search_repo_memory call
```

**Rollback:** Remove the `[mcp_servers.rmembr]` section from `~/.codex/config.toml`.

---

## Phase 5 — Stdio wrapper script (optional)

**Goal:** Provide a stdio bridge for clients that cannot use SSE (e.g., older Claude Code versions, CI scripts, or custom integrations).

**Success criteria (V7):** Running the wrapper script manually produces a valid MCP `initialize` handshake response on stdout before the gateway processes tool calls.

Some clients or debugging scenarios may prefer stdio transport over SSE. The stdio shim
runs inside the gateway container and communicates via stdin/stdout.

### mcp-memory-local/scripts/mcp-stdio-wrapper.sh
```bash
#!/usr/bin/env bash
# Bridges stdio MCP transport to the running gateway container.
# Usage: set this script as the `command` in a stdio-type MCP server config.
set -euo pipefail
COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
exec docker compose -f "$COMPOSE_FILE" exec -T gateway \
  env MCP_ENABLED=true MCP_STDIO_ENABLED=true \
  python -m src.mcp_stdio_shim
```

To use with Claude Code (stdio):
```json
{
  "mcpServers": {
    "rmembr-stdio": {
      "type": "stdio",
      "command": "/absolute/path/to/mcp-memory-local/scripts/mcp-stdio-wrapper.sh"
    }
  }
}
```

### Verification (V7)
```bash
# Send a minimal MCP initialize request and check for a valid JSON response
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' \
  | bash mcp-memory-local/scripts/mcp-stdio-wrapper.sh
# Expected: a JSON object with "result" containing "protocolVersion" and "capabilities"
```

**Rollback:** The script is additive — simply do not configure it in any client config. Delete the file if desired.

---

## Validation Steps

| Step | Command / Action | Expected |
|------|-----------------|----------|
| V1 | `curl -N http://localhost:8080/mcp/sse` | SSE stream opens, no 404/401 |
| V2 | Claude Code `/mcp` | `rmembr` server listed, 9 tools |
| V3 | Claude Code: ask about "provider framework" in rmembr | Returns chunked memory results |
| V4 | VSCode Copilot agent mode, type `#` | rmembr tools visible |
| V5 | VSCode Copilot agent: "search rmembr for github provider" | Tool call executes |
| V6 | Codex CLI session with rmembr query | Tool listed and callable |
| V7 | Pipe MCP `initialize` JSON into stdio wrapper script | Valid JSON `result` with `protocolVersion` on stdout |

---

## Risk Surface

| Risk | Severity | Mitigation |
|------|----------|------------|
| MCP_ENABLED=true exposes tools on localhost:8080 with no auth | LOW | localhost only; no gateway auth required by design (it's the external-facing service); Docker network isolates Index/Standards |
| VSCode extension version too old to support MCP | LOW | Minimum version documented; easy to upgrade |
| SSE connection drops during long tool calls | LOW | MCP SDK handles reconnection; index_all is the only long operation |
| Codex CLI config path differs by OS | LOW | Windows: `%APPDATA%\Codex\config.yaml`; Mac/Linux: `~/.codex/config.yaml` |
| MCP_ENABLED default change breaks existing deploys | NONE | `${MCP_ENABLED:-true}` — existing deploys can still override with `MCP_ENABLED=false` |

---

## Order of Operations

1. Phase 1 (docker-compose.yml) — 5 minutes
2. Verify V1 (curl test) — 2 minutes
3. Phase 2 (Claude Code) — 5 minutes, verify V2+V3
4. Phase 3 (VSCode) — 10 minutes (extension check + config), verify V4+V5
5. Phase 4 (Codex CLI) — 5 minutes, verify V6
6. Phase 5 (stdio wrapper) — optional, only if a client needs it; verify V7

Total: ~30 minutes to wire all four clients.
