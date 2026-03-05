"""MCP tool definitions — registers 9 tools from gateway-mcp-tools.md contract.

Each tool maps to an extracted handler in server.py or a proxy call to
Index/Standards services.
"""

import json

from mcp.server import Server
from mcp.types import Tool, TextContent

from src.mcp_errors import map_exception
from src.server import (
    handle_get_context_bundle,
    handle_explain_context_bundle,
    handle_validate_pack,
    handle_proxy,
    INDEX_URL,
    STANDARDS_URL,
)


# --- Tool schema definitions (from docs/contracts/gateway-mcp-tools.md) ---

TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="search_repo_memory",
        description="Semantic search over a repository's indexed memory chunks.",
        inputSchema={
            "type": "object",
            "required": ["repo", "query"],
            "properties": {
                "repo": {"type": "string", "description": "Repository name.", "minLength": 1},
                "query": {"type": "string", "description": "Semantic search query.", "minLength": 1, "maxLength": 2000},
                "k": {"type": "integer", "description": "Number of results to return.", "minimum": 1, "maximum": 100, "default": 8},
                "ref": {"type": "string", "description": "Git ref or 'local'.", "default": "local"},
                "namespace": {"type": "string", "description": "Tenant namespace.", "default": "default"},
                "filters": {"type": ["object", "null"], "description": "Optional filters.", "default": None},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_context_bundle",
        description="Assemble a complete context bundle by orchestrating Index and Standards services.",
        inputSchema={
            "type": "object",
            "required": ["repo", "task"],
            "properties": {
                "repo": {"type": "string", "description": "Repository name.", "minLength": 1},
                "task": {"type": "string", "description": "Task description.", "minLength": 1, "maxLength": 2000},
                "k": {"type": "integer", "description": "Number of context chunks.", "minimum": 1, "maximum": 100, "default": 12},
                "ref": {"type": "string", "default": "local"},
                "namespace": {"type": "string", "default": "default"},
                "persona": {"type": "string", "enum": ["human", "agent", "external"], "default": "human"},
                "standards_version": {"type": "string", "default": "local"},
                "changed_files": {"type": ["array", "null"], "items": {"type": "string"}, "default": None},
                "filters": {"type": ["object", "null"], "default": None},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="explain_context_bundle",
        description="Explain how a previously assembled bundle was constructed.",
        inputSchema={
            "type": "object",
            "required": ["bundle_id"],
            "properties": {
                "bundle_id": {"type": "string", "description": "ID of a previously returned bundle."},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="validate_pack",
        description="Validate that a repository's memory pack is indexed and queryable.",
        inputSchema={
            "type": "object",
            "required": ["repo"],
            "properties": {
                "repo": {"type": "string", "minLength": 1},
                "ref": {"type": "string", "default": "local"},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="index_repo",
        description="Trigger indexing for a single repository's memory pack.",
        inputSchema={
            "type": "object",
            "required": ["repo"],
            "properties": {
                "repo": {"type": "string", "minLength": 1},
                "ref": {"type": "string", "default": "local"},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="index_all",
        description="Trigger indexing for all discovered repositories.",
        inputSchema={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "default": "local"},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="list_standards",
        description="List available enterprise standard IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {"type": ["string", "null"], "description": "Filter by domain prefix."},
                "version": {"type": "string", "default": "local"},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_standard",
        description="Retrieve the content of a specific enterprise standard.",
        inputSchema={
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "description": "Standard ID.", "pattern": "^[a-z0-9\\-]+(/[a-z0-9\\-]+)*$"},
                "version": {"type": "string", "default": "local"},
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_schema",
        description="Retrieve a JSON/YAML schema file associated with a standard.",
        inputSchema={
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z0-9\\-]+(/[a-z0-9\\-]+)*$"},
                "version": {"type": "string", "default": "local"},
            },
            "additionalProperties": False,
        },
    ),
]


# --- Tool dispatch ---

# Maps tool name -> (handler_type, handler_or_config)
# "gateway" tools call extracted handlers directly
# "proxy_index" tools proxy to Index service
# "proxy_standards" tools proxy to Standards service

_TOOL_DISPATCH = {
    "search_repo_memory":      ("proxy_index", "search_repo_memory"),
    "get_context_bundle":      ("gateway", handle_get_context_bundle),
    "explain_context_bundle":  ("gateway", handle_explain_context_bundle),
    "validate_pack":           ("gateway", handle_validate_pack),
    "index_repo":              ("proxy_index", "index_repo"),
    "index_all":               ("proxy_index", "index_all"),
    "list_standards":          ("proxy_standards", "list_standards"),
    "get_standard":            ("proxy_standards", "get_standard"),
    "get_schema":              ("proxy_standards", "get_schema"),
}


async def dispatch_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch an MCP tool call to the appropriate handler.

    Returns list of TextContent with JSON result on success.
    Raises tuple (error_code, message) on failure.
    """
    entry = _TOOL_DISPATCH.get(name)
    if not entry:
        raise ValueError(f"Unknown tool: {name}")

    kind, target = entry
    try:
        if kind == "gateway":
            result = await target(arguments)
        elif kind == "proxy_index":
            result = await handle_proxy(INDEX_URL, f"/tools/{target}", arguments)
        elif kind == "proxy_standards":
            result = await handle_proxy(STANDARDS_URL, f"/tools/{target}", arguments)
        else:
            raise ValueError(f"Unknown dispatch kind: {kind}")
    except Exception as exc:
        error_code, error_msg = map_exception(exc)
        raise McpToolError(error_code, error_msg) from exc

    return [TextContent(type="text", text=json.dumps(result))]


class McpToolError(Exception):
    """Wraps an MCP error code + sanitized message for the MCP server to return."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def register_tools(server: Server) -> None:
    """Register all 9 MCP tools on the given MCP Server instance."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        return await dispatch_tool(name, arguments or {})
