# STREAMABLE_HTTP_TRANSPORT_v0 — Execution Plan

Date: 2026-03-06
Builder: Claude Opus 4.6

---

## Problem Statement

Claude Code's `--transport http` speaks the **Streamable HTTP** protocol (MCP spec 2025-03-26),
which uses a single endpoint handling GET, POST, and DELETE. The gateway currently only exposes
the **legacy SSE transport** (two endpoints: `GET /mcp/sse` + `POST /mcp/messages/`). When
Claude Code connects via `--transport http`, it POSTs JSON-RPC to the SSE endpoint, which
doesn't understand it, causing the `rmembr` MCP server to show `failed` in `/mcp`.

The gateway already has `mcp==1.26.0` installed, which includes both `StreamableHTTPServerTransport`
and `StreamableHTTPSessionManager`. **No dependency changes are needed.**

---

## Pre-conditions

- Gateway container is running (`docker compose up -d gateway`)
- `MCP_ENABLED=true` is set in `docker-compose.yml` (done in MCP_CLIENT_WIRING_v0)
- `mcp>=1.26.0` is installed in the gateway image (confirmed: `1.26.0`)
- `curl -N http://localhost:8080/mcp/sse` returns SSE stream (V1 from wiring plan — confirmed passing)

---

## Scope of Changes

| File | Action |
|------|--------|
| `mcp-memory-local/services/gateway/src/mcp_server.py` | Rewrite — add Streamable HTTP transport alongside existing SSE |
| Claude Code MCP registration | Update — change URL from `/mcp/sse` to `/mcp` |
| `.vscode/mcp.json` | Update — change URL from `/mcp/sse` to `/mcp` |

No other files change. The `server.py` mount point (`app.mount("/", mcp_app)`) stays the same.

---

## Architecture After Fix

```
Client (Claude Code, VSCode, etc.)
  |
  |  POST/GET/DELETE  http://localhost:8080/mcp    <-- NEW: Streamable HTTP
  |  GET              http://localhost:8080/mcp/sse        <-- PRESERVED: Legacy SSE
  |  POST             http://localhost:8080/mcp/messages/  <-- PRESERVED: Legacy SSE
  |
  v
Starlette sub-app (mounted at "/" on FastAPI gateway)
  |
  +-- Route("/mcp")           -> StreamableHTTPSessionManager.handle_request
  +-- Route("/mcp/sse")       -> SseServerTransport (existing)
  +-- Route("/mcp/messages/") -> SseServerTransport (existing)
```

Both transports share the same `Server` instance and tool registrations.

---

## Phase 1 — Update `mcp_server.py`

**Goal:** Add the Streamable HTTP transport at `/mcp` while keeping the SSE transport at `/mcp/sse` and `/mcp/messages/` for backward compatibility.

**What changes:**

1. Import `StreamableHTTPSessionManager` from `mcp.server.streamable_http_manager`
2. Create a single `Server` instance shared by both transports
3. Create a `StreamableHTTPSessionManager` wrapping that server
4. Add a Starlette `lifespan` context manager that runs `session_manager.run()` (this initializes the internal task group the session manager needs)
5. Add a catch-all route at `/mcp` (GET + POST + DELETE) that delegates to `session_manager.handle_request()`
6. Keep the existing SSE routes unchanged

**Key implementation detail — lifespan:**

The `StreamableHTTPSessionManager.run()` method is an async context manager that must be active for the lifetime of the app. Starlette's `lifespan` parameter is the correct place for this:

```python
@asynccontextmanager
async def mcp_lifespan(app):
    async with session_manager.run():
        yield
```

**Key implementation detail — route handler:**

The streamable HTTP handler must forward the raw ASGI scope/receive/send to the session manager:

```python
async def handle_streamable(request: Request):
    await session_manager.handle_request(
        request.scope, request.receive, request._send
    )
```

The route must accept GET, POST, and DELETE methods on `/mcp`.

### Success Criteria (P1)

- [ ] Gateway starts without errors when `MCP_ENABLED=true`
- [ ] `GET /mcp/sse` still returns SSE stream (legacy transport preserved)
- [ ] `POST /mcp` with a valid JSON-RPC `initialize` request returns a valid JSON-RPC response with `protocolVersion` and `capabilities`
- [ ] Gateway logs show both `MCP SSE transport ready at /mcp/sse` and `MCP Streamable HTTP transport ready at /mcp`

### Verification (P1)

```bash
# Rebuild and restart
docker compose build gateway && docker compose up -d gateway

# V1-legacy: SSE still works
curl -N http://localhost:8080/mcp/sse
# Expected: event: endpoint, data: /mcp/messages/?session_id=...

# V1-streamable: Streamable HTTP responds to POST
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'
# Expected: JSON response with "result" containing "protocolVersion", "capabilities", "serverInfo"

# V1-logs: Check startup logs
docker compose logs gateway | grep "MCP"
# Expected: both "SSE transport ready" and "Streamable HTTP transport ready"
```

**Rollback:** Revert `mcp_server.py` to the previous version (SSE-only), rebuild, and restart.

---

## Phase 2 — Update Claude Code Registration

**Goal:** Point Claude Code at the new `/mcp` endpoint so it connects via Streamable HTTP.

**What changes:**

```bash
claude mcp remove rmembr
claude mcp add --transport http rmembr http://localhost:8080/mcp
```

### Success Criteria (P2)

- [ ] `/mcp` in Claude Code shows `rmembr` as `connected` (green checkmark)
- [ ] All 9 tools are listed when selecting the `rmembr` server
- [ ] A natural-language query like "search rmembr for provider framework" triggers `search_repo_memory` and returns results

### Verification (P2)

1. Restart Claude Code after re-registering
2. Run `/mcp` — expect `rmembr` with green checkmark
3. Ask: *"Search rmembr for provider framework"* — expect tool call and chunked results

**Rollback:** `claude mcp remove rmembr` — removes the registration entirely.

---

## Phase 3 — Update `.vscode/mcp.json`

**Goal:** Point VSCode Copilot at `/mcp` instead of `/mcp/sse`.

**What changes:**

```json
{
  "servers": {
    "rmembr": {
      "type": "sse",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

Note: VSCode may still use the SSE-style transport internally. If `/mcp` doesn't work for VSCode,
fall back to keeping `/mcp/sse` for this client. Both endpoints will remain available.

### Success Criteria (P3)

- [ ] rmembr tools appear in Copilot Chat agent mode `#` picker
- [ ] A tool call executes successfully

### Verification (P3)

1. Reload VSCode window
2. Open Copilot Chat in agent mode
3. Type `#` — expect rmembr tools listed
4. Ask about "github provider" — expect `search_repo_memory` tool call

**Rollback:** Change `.vscode/mcp.json` URL back to `http://localhost:8080/mcp/sse`.

---

## Validation Summary

| ID | Phase | Test | Expected |
|----|-------|------|----------|
| V1a | P1 | `curl -N http://localhost:8080/mcp/sse` | SSE stream opens (legacy preserved) |
| V1b | P1 | `curl -X POST http://localhost:8080/mcp` with initialize JSON | JSON-RPC response with `protocolVersion` |
| V1c | P1 | `docker compose logs gateway \| grep MCP` | Both transport ready messages |
| V2a | P2 | Claude Code `/mcp` | `rmembr` shows `connected` |
| V2b | P2 | Claude Code tool call | `search_repo_memory` executes, returns results |
| V3a | P3 | VSCode Copilot `#` picker | rmembr tools visible |
| V3b | P3 | VSCode Copilot tool call | Executes and returns results |

---

## Risk Surface

| Risk | Severity | Mitigation |
|------|----------|------------|
| Streamable HTTP handler conflicts with FastAPI routes | LOW | MCP sub-app is mounted at `/` but Starlette routes are checked in order; `/mcp` is specific and won't shadow `/health`, `/tools/*`, etc. |
| Session manager task group not initialized | MED | Starlette `lifespan` ensures `run()` context is active before any requests are served; startup logs confirm initialization |
| Legacy SSE clients break | NONE | SSE routes are preserved unchanged at their existing paths |
| `mcp` SDK upgrade needed | NONE | Already on 1.26.0 which has all required classes |
| Multiple `Server` instances cause tool duplication | LOW | Single `Server` instance shared by both transports; `create_mcp_server()` called once |

---

## Order of Operations

1. Phase 1 — Edit `mcp_server.py`, rebuild gateway image, restart container
2. Verify V1a + V1b + V1c (curl tests + logs)
3. Phase 2 — Re-register Claude Code MCP server, restart Claude Code
4. Verify V2a + V2b (Claude Code connected + tool call)
5. Phase 3 — Update `.vscode/mcp.json`, reload VSCode
6. Verify V3a + V3b (Copilot tool visibility + call)

Total: Single file edit + two config updates. The gateway image rebuild is the only step requiring `docker compose build`.
