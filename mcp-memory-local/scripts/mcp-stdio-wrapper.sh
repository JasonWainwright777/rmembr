#!/usr/bin/env bash
# Bridges stdio MCP transport to the running gateway container.
# Usage: set this script as the `command` in a stdio-type MCP server config.
set -euo pipefail
COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
exec docker compose -f "$COMPOSE_FILE" exec -T gateway \
  env MCP_ENABLED=true MCP_STDIO_ENABLED=true \
  python -m src.mcp_stdio_shim
