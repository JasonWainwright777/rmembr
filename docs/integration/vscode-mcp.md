# VS Code MCP Integration Guide

## Compatibility

**Primary target:** VS Code 1.102+
**Best-effort support:** Current stable release (N) and previous stable release (N-1).
Older versions that predate MCP support are not supported.

## Prerequisites

1. **Docker Compose services running:**
   ```bash
   cd mcp-memory-local
   docker compose up -d
   ```

2. **Embedding model pulled:**
   ```bash
   docker compose exec ollama ollama pull nomic-embed-text
   ```

3. **At least one repository indexed:**
   ```bash
   python scripts/mcp-cli.py index-repo <your-repo>
   ```

4. **MCP enabled on the gateway:**
   Set `MCP_ENABLED=true` in your `.env` file or directly in `docker-compose.yml` under the gateway service, then restart:
   ```bash
   docker compose restart gateway
   ```

## Configuration

### 1. Add `.vscode/mcp.json` to your workspace

Create `.vscode/mcp.json` in the root of your workspace (a sample is included in this repo):

```json
{
  "servers": {
    "rmembr": {
      "type": "sse",
      "url": "http://localhost:8080/mcp/sse",
      "headers": {}
    }
  }
}
```

### 2. Verify server discovery

1. Open VS Code (1.102+).
2. Open the MCP panel (Command Palette > "MCP: List Servers" or check the MCP sidebar).
3. The **rmembr** server should appear as connected.
4. Tool list should show 9 tools.

### 3. Invoke a tool

Use the MCP panel or Copilot Chat to invoke a tool. For example:
- `search_repo_memory` with `{"repo": "my-repo", "query": "authentication"}`
- `get_context_bundle` with `{"repo": "my-repo", "task": "implement OAuth login"}`

## Available Tools

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `search_repo_memory` | Semantic search over indexed memory chunks | `repo`, `query` |
| `get_context_bundle` | Assemble a complete context bundle | `repo`, `task` |
| `explain_context_bundle` | Explain how a bundle was constructed | `bundle_id` |
| `validate_pack` | Validate a repo's memory pack | `repo` |
| `index_repo` | Trigger indexing for a repo (requires writer role) | `repo` |
| `index_all` | Trigger indexing for all repos (requires writer role) | |
| `list_standards` | List enterprise standard IDs | |
| `get_standard` | Retrieve a specific standard | `id` |
| `get_schema` | Retrieve a schema file for a standard | `id` |

## Configuration Reference

### Environment Variables (gateway)

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_ENABLED` | `false` | Must be `true` for MCP server to be active |
| `MCP_STDIO_ENABLED` | `false` | Enable stdio transport (not used by VS Code) |

### Endpoint

| Path | Method | Description |
|------|--------|-------------|
| `/mcp/sse` | GET | SSE connection endpoint for MCP clients |
| `/mcp/messages/` | POST | Message endpoint for MCP client requests |

### Port

The gateway listens on port **8080** by default. If you change `GATEWAY_PORT`, update the URL in `.vscode/mcp.json` accordingly.

## Troubleshooting

### Server not appearing in MCP panel

1. **Check VS Code version.** MCP support requires 1.102+. Run `code --version` to verify.
2. **Check services are running:** `docker compose ps` — gateway should be healthy.
3. **Check MCP is enabled:** Look for `MCP SSE transport ready at /mcp/sse` in gateway logs:
   ```bash
   docker compose logs gateway | grep "MCP SSE"
   ```
4. **Check the endpoint is reachable:**
   ```bash
   curl -s http://localhost:8080/health
   ```

### Tools not loading

1. **Verify `.vscode/mcp.json` is in the workspace root** (not a subdirectory).
2. **Check the URL** matches the gateway port (`http://localhost:8080/mcp/sse`).
3. **Reload VS Code window** (Command Palette > "Developer: Reload Window").

### Tool invocation returns errors

1. **"Unauthorized" errors:** Default role is `reader`, which allows all read-only tools. `index_repo` and `index_all` require `writer` role.
2. **"Internal server error":** Check gateway logs for details:
   ```bash
   docker compose logs gateway --tail 50
   ```
3. **Timeout errors:** Large repos may exceed default timeouts. See `docs/TUNING.md` for tuning guidance.

### Connection drops

SSE connections may drop on network interruptions. VS Code should auto-reconnect. If not, reload the window.

## Production Notes

- The sample `.vscode/mcp.json` uses `localhost:8080` with no authentication. For production deployments behind a reverse proxy or with auth, update the `url` and `headers` fields accordingly.
- Do not commit credentials in `.vscode/mcp.json`. Use environment variable substitution or a gitignored config overlay.
