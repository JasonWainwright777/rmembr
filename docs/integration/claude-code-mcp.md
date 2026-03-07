# Claude Code MCP Integration Guide

## Prerequisites

Same as the [VS Code integration](vscode-mcp.md#prerequisites):

1. Docker Compose services running with `MCP_ENABLED=true`.
2. Embedding model pulled.
3. At least one repository indexed.

## Configuration

Claude Code reads MCP server configs from `.mcp.json` in the project root.

### 1. Add `.mcp.json` to your project root

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

### 2. Verify server discovery

Start Claude Code in the project directory. It should auto-discover the rmembr MCP server and list 9 available tools.

### 3. Invoke a tool

Claude Code can invoke tools through natural language or direct tool calls. For example:
- "Search my repo memory for authentication patterns"
- "Get a context bundle for implementing OAuth login in my-repo"

## Available Tools

See the [VS Code integration guide](vscode-mcp.md#available-tools) for the full tool list. All 9 tools are available to both clients.

## Troubleshooting

### Server not discovered

1. **Check `.mcp.json` is in the project root** (same directory where you run Claude Code).
2. **Check services are running:** `docker compose ps` — gateway should be healthy.
3. **Check MCP is enabled:**
   ```bash
   docker compose logs gateway | grep "MCP"
   ```
4. **Verify the endpoint:**
   ```bash
   curl -s http://localhost:8080/health
   ```

### Tool errors

1. **"Unauthorized" errors:** `index_repo` and `index_all` require `writer` role. All read-only tools work with the default `reader` role.
2. **Connection errors:** Ensure the gateway is running and the port matches your config.
3. **Check gateway logs:**
   ```bash
   docker compose logs gateway --tail 50
   ```

## Alternative: `claude_desktop_config.json`

If you use the Claude desktop app, you can also configure the MCP server in your user-level config at `~/.config/claude/claude_desktop_config.json` (Linux/Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

## Production Notes

- The config uses `localhost:8080` with no authentication. For production, update the URL and add any required auth headers.
- Do not commit credentials in `.mcp.json`. Use gitignore or environment-specific overlays.
