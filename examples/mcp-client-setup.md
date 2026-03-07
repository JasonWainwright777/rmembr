# rmembr MCP Client Setup & Usage

How to connect VS Code, Claude Code, and OpenAI Codex CLI to the rmembr MCP server. All three clients talk to the same gateway. Streamable HTTP on `/mcp` is the primary transport; legacy SSE remains available for compatibility.

---

## Prerequisites (all clients)

1. **Start the stack:**
   ```bash
   cd mcp-memory-local
   docker compose up -d
   ```

2. **Pull the embedding model:**
   ```bash
   docker compose exec ollama ollama pull nomic-embed-text
   ```

3. **Index at least one repo:**
   ```bash
   python scripts/mcp-cli.py index-repo <your-repo>
   ```

4. **Enable MCP on the gateway:**

   Set `MCP_ENABLED=true` in your `.env` (or `docker-compose.yml` under the gateway service), then restart:
   ```bash
   docker compose restart gateway
   ```

5. **Verify MCP is live:**
   ```bash
   docker compose logs gateway | grep "MCP"
   ```
   You should see:
   ```
   MCP SSE transport ready at /mcp/sse
   MCP Streamable HTTP transport ready at /mcp
   ```

---

## Transports

The gateway exposes two MCP transports on port **8080**:

| Transport | Endpoint | Used by |
|-----------|----------|---------|
| **Streamable HTTP** | `POST/GET/DELETE /mcp` | VS Code, Claude Code, modern clients |
| **Legacy SSE** | `GET /mcp/sse` + `POST /mcp/messages/` | Older or compatibility-only clients |

Both expose the same 9 tools — pick whichever your client supports.

---

## VS Code (Copilot Chat / MCP panel)

**Requires:** VS Code 1.102+

### 1. Create `.vscode/mcp.json` in your workspace root

```json
{
  "servers": {
    "rmembr": {
      "type": "http",
      "url": "http://localhost:8080/mcp",
      "headers": {}
    }
  }
}
```

### 2. Verify connection

1. Open Command Palette > **MCP: List Servers**
2. **rmembr** should appear as connected with 9 tools

### 3. Use it

From Copilot Chat or the MCP panel, invoke tools directly:

```
search_repo_memory  {"repo": "my-repo", "query": "authentication"}
```

```
get_context_bundle  {"repo": "my-repo", "task": "implement OAuth login"}
```

### Troubleshooting

- **Server not appearing:** Check VS Code version (`code --version`, need 1.102+), check `docker compose ps` shows gateway healthy.
- **Tools not loading:** Ensure `.vscode/mcp.json` is in the workspace root (not a subdirectory). Reload the window.
- **Connection drops:** Confirm the gateway still responds on `POST /mcp`, then reload the window if the client does not recover.

---

## Claude Code

### 1. Create `.mcp.json` in your project root

```json
{
  "mcpServers": {
    "rmembr": {
      "url": "http://localhost:8080/mcp",
      "transport": "http"
    }
  }
}
```

### 2. Verify connection

Start Claude Code in the project directory. It auto-discovers the server and lists 9 available tools.

### 3. Use it

Claude Code invokes tools through natural language:

- "Search my repo memory for authentication patterns"
- "Get a context bundle for implementing OAuth login in my-repo"
- "List all enterprise standards"

Or invoke tools directly by name (e.g. `mcp__rmembr__search_repo_memory`).

### Alternative: Claude Desktop App

Add to `~/.config/claude/claude_desktop_config.json` (Linux/Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "rmembr": {
      "url": "http://localhost:8080/mcp",
      "transport": "http"
    }
  }
}
```

### Troubleshooting

- **Server not discovered:** Check `.mcp.json` is in the project root (same directory where you run Claude Code).
- **Tool errors:** `index_repo` and `index_all` require `writer` role. All read-only tools work with the default `reader` role.
- **Connection errors:** Verify `curl -s http://localhost:8080/health` returns `"status": "healthy"`.

---

## OpenAI Codex CLI

Codex CLI should target the same Streamable HTTP endpoint.

### 1. Register the server

```bash
codex mcp add rmembr --url http://localhost:8080/mcp
```

Or configure the same URL in a user-level or project-level Codex MCP config.

### 2. Verify connection

Start Codex CLI in your project directory. It should discover the rmembr server and list the available tools.

### 3. Use it

Codex CLI can invoke the tools through natural language, the same way as Claude Code:

- "Search rmembr for how caching works"
- "Get a context bundle for adding rate limiting to sample-repo-a"

### Troubleshooting

- **Server not found:** Ensure the config file path is correct and the gateway is running.
- **Connection refused:** Verify `http://localhost:8080/health` is reachable.
- **Auth errors on write tools:** `index_repo` and `index_all` require `writer` role.

---

## Available Tools (all clients)

All clients see the same 9 tools:

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `search_repo_memory` | Semantic search over indexed memory chunks | `repo`, `query` |
| `get_context_bundle` | Assemble a complete context bundle | `repo`, `task` |
| `explain_context_bundle` | Explain how a bundle was constructed | `bundle_id` |
| `validate_pack` | Validate a repo's memory pack | `repo` |
| `index_repo` | Trigger indexing for a repo (writer role) | `repo` |
| `index_all` | Trigger indexing for all repos (writer role) | |
| `list_standards` | List enterprise standard IDs | |
| `get_standard` | Retrieve a specific standard | `id` |
| `get_schema` | Retrieve a schema file for a standard | `id` |

---

## Quick Smoke Test (any client)

Once connected, run through these steps to verify everything works end-to-end:

### 1. Health check

Call `search_repo_memory` with any indexed repo:
```json
{"repo": "sample-repo-a", "query": "architecture", "k": 3}
```

You should get back results with `similarity` scores and `snippet` text.

### 2. Bundle assembly

Call `get_context_bundle`:
```json
{
  "repo": "sample-repo-a",
  "task": "add OAuth2 login to the API layer",
  "persona": "agent"
}
```

You should get back a bundle with `standards_content`, `chunks`, and `bundle_id`.

### 3. Explain the bundle

Call `explain_context_bundle` with the `bundle_id` from step 2:
```json
{"bundle_id": "<bundle_id from step 2>"}
```

You should see `total_candidates`, `after_classification_filter`, `after_budget_trim`, and a `chunks_summary`.

---

## Production Notes

- The examples above use `localhost:8080` with no authentication. For production behind a reverse proxy or with auth, update the `url` and add auth headers.
- Do not commit credentials in config files. Use environment variable substitution or gitignored config overlays.
- If you change `GATEWAY_PORT`, update the URL in all client configs accordingly.
