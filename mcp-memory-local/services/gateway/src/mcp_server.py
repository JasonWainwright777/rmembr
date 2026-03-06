"""MCP server entry point — Streamable HTTP + legacy SSE transports.

Gated by MCP_ENABLED env var (default: false). When enabled, mounts the MCP
server as an ASGI sub-app alongside the existing FastAPI HTTP server.

Streamable HTTP (POST/GET/DELETE /mcp) — used by Claude Code, modern clients.
Legacy SSE (GET /mcp/sse + POST /mcp/messages/) — preserved for backward compat.
"""

import os
import sys

sys.path.insert(0, "/app/shared/src")

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request

from structured_logging import setup_logging, new_request_id, request_id_var

logger = setup_logging("gateway-mcp")

MCP_ENABLED = os.environ.get("MCP_ENABLED", "false").lower() == "true"

# Module-level reference so server.py lifespan can start it.
_session_manager = None


def create_mcp_server() -> Server:
    """Create and configure the MCP server with all tool registrations."""
    server = Server("rmembr-context-gateway")

    from src.mcp_tools import register_tools
    register_tools(server)

    return server


def get_mcp_asgi_app():
    """Return an ASGI app for the MCP transport.

    Returns None if MCP_ENABLED is false.
    Provides both Streamable HTTP (/mcp) and legacy SSE (/mcp/sse) transports.

    The session manager lifecycle is handled by the main FastAPI lifespan
    (server.py), not by this sub-app, because mounted sub-app lifespans
    are not propagated by FastAPI.
    """
    global _session_manager

    if not MCP_ENABLED:
        logger.info("MCP server disabled (MCP_ENABLED=false)")
        return None

    server = create_mcp_server()

    # --- Streamable HTTP transport (new) ---
    _session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=False,
    )

    async def handle_streamable(request: Request):
        """Handle Streamable HTTP requests (POST/GET/DELETE) for MCP."""
        await _session_manager.handle_request(
            request.scope, request.receive, request._send
        )

    # --- Legacy SSE transport (preserved) ---
    sse = SseServerTransport("/mcp/messages/")

    async def handle_sse(request: Request):
        """Handle SSE connection for MCP client (legacy)."""
        rid = request.headers.get("X-Request-ID", "")
        if rid:
            request_id_var.set(rid)
        else:
            new_request_id()

        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    async def handle_messages(request: Request):
        """Handle POST messages from MCP client (legacy SSE)."""
        rid = request.headers.get("X-Request-ID", "")
        if rid:
            request_id_var.set(rid)
        else:
            new_request_id()

        await sse.handle_post_message(request.scope, request.receive, request._send)

    mcp_app = Starlette(
        routes=[
            Route("/mcp", endpoint=handle_streamable, methods=["GET", "POST", "DELETE"]),
            Route("/mcp/sse", endpoint=handle_sse),
            Route("/mcp/messages/", endpoint=handle_messages, methods=["POST"]),
        ],
    )

    logger.info("MCP SSE transport ready at /mcp/sse")
    logger.info("MCP Streamable HTTP transport ready at /mcp")
    return mcp_app
