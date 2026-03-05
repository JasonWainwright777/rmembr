"""Shared fixtures for MCP tests."""

import os
import re
import pytest
import httpx


GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")

# Patterns that must NOT appear in MCP error responses
INTERNAL_PATTERNS = [
    re.compile(r"http://index:\d+"),
    re.compile(r"http://standards:\d+"),
    re.compile(r"INTERNAL_SERVICE_TOKEN"),
    re.compile(r"/app/"),
]


class McpTestClient:
    """Helper for MCP JSON-RPC interactions over HTTP."""

    def __init__(self, gateway_url: str = GATEWAY_URL):
        self.gateway_url = gateway_url
        self.session_id: str | None = None
        self._next_id = 1

    def _next_request_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _headers(self) -> dict:
        headers = {}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _post(self, method: str, params: dict | None = None, timeout: float = 10.0) -> dict:
        """Send a JSON-RPC request to the MCP endpoint."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._next_request_id(),
            "params": params or {},
        }
        resp = httpx.post(
            f"{self.gateway_url}/mcp",
            json=payload,
            headers=self._headers(),
            timeout=timeout,
        )
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"MCP request failed with HTTP {resp.status_code}: {resp.text}")
        # Capture session ID from response headers
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        return resp.json()

    def initialize(self) -> dict:
        """Send initialize request, store session_id."""
        result = self._post("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "rmembr-smoke-test", "version": "0.1.0"},
        })
        return result

    def list_tools(self) -> list[dict]:
        """Send tools/list, return tool definitions."""
        result = self._post("tools/list", {})
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict, timeout: float = 30.0) -> dict:
        """Send tools/call, return full response (result or error)."""
        return self._post("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)


def gateway_reachable() -> bool:
    """Check if the gateway health endpoint responds."""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/health", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def mcp_enabled() -> bool:
    """Check if MCP endpoint is available."""
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            }},
            timeout=5.0,
        )
        return resp.status_code in (200, 202)
    except Exception:
        return False


skip_no_gateway = pytest.mark.skipif(
    not gateway_reachable(),
    reason="Gateway not reachable (run docker compose up)",
)

skip_no_mcp = pytest.mark.skipif(
    not gateway_reachable() or not mcp_enabled(),
    reason="MCP endpoint not available (set MCP_ENABLED=true)",
)


def assert_no_internal_leaks(text: str):
    """Assert no internal URLs/tokens/paths appear in response text."""
    for pattern in INTERNAL_PATTERNS:
        assert not pattern.search(text), f"Internal pattern leaked: {pattern.pattern} in: {text}"


@pytest.fixture
def mcp_client() -> McpTestClient:
    """Provide an initialized MCP test client."""
    client = McpTestClient()
    client.initialize()
    return client
