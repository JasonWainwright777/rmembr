"""Stdio transport entry point for MCP (dev-only).

Gated by MCP_STDIO_ENABLED env var (default: false). Only activates when
BOTH MCP_ENABLED=true AND MCP_STDIO_ENABLED=true.

Usage: python -m src.mcp_stdio_shim
"""

import asyncio
import os
import sys

sys.path.insert(0, "/app/shared/src")


def main():
    mcp_enabled = os.environ.get("MCP_ENABLED", "false").lower() == "true"
    stdio_enabled = os.environ.get("MCP_STDIO_ENABLED", "false").lower() == "true"

    if not mcp_enabled:
        print("ERROR: MCP_ENABLED must be 'true' to use stdio transport.", file=sys.stderr)
        sys.exit(1)

    if not stdio_enabled:
        print("ERROR: MCP_STDIO_ENABLED must be 'true' to use stdio transport.", file=sys.stderr)
        sys.exit(1)

    from mcp.server.stdio import stdio_server
    from structured_logging import setup_logging
    from src.mcp_server import create_mcp_server

    logger = setup_logging("gateway-mcp-stdio")
    logger.info("Starting MCP stdio transport")

    server = create_mcp_server()

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
