"""Integration tests: MCP client fixture discovers and calls tools.

These tests require running services (docker compose up). They are skipped
if the gateway is not reachable.
"""

import json
import os
import sys
import re
import pytest
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")

# Patterns that must NOT appear in MCP error responses
INTERNAL_PATTERNS = [
    re.compile(r"http://index:\d+"),
    re.compile(r"http://standards:\d+"),
    re.compile(r"INTERNAL_SERVICE_TOKEN"),
    re.compile(r"/app/"),
]


def _gateway_reachable() -> bool:
    try:
        resp = httpx.get(f"{GATEWAY_URL}/health", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _mcp_enabled() -> bool:
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
    not _gateway_reachable(),
    reason="Gateway not reachable (run docker compose up)",
)

skip_no_mcp = pytest.mark.skipif(
    not _gateway_reachable() or not _mcp_enabled(),
    reason="MCP endpoint not available (set MCP_ENABLED=true)",
)


def _assert_no_internal_leaks(text: str):
    """Assert no internal URLs/tokens/paths appear in response text."""
    for pattern in INTERNAL_PATTERNS:
        assert not pattern.search(text), f"Internal pattern leaked: {pattern.pattern} in: {text}"


@skip_no_gateway
class TestHttpEndpointsStillWork:
    """Verify existing HTTP endpoints are unaffected by MCP changes."""

    def test_health(self):
        resp = httpx.get(f"{GATEWAY_URL}/health", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "gateway"

    def test_get_context_bundle_validation(self):
        resp = httpx.post(
            f"{GATEWAY_URL}/tools/get_context_bundle",
            json={"repo": "", "task": "test"},
            timeout=5.0,
        )
        assert resp.status_code == 400
        _assert_no_internal_leaks(resp.text)

    def test_explain_context_bundle_missing_id(self):
        resp = httpx.post(
            f"{GATEWAY_URL}/tools/explain_context_bundle",
            json={"bundle_id": ""},
            timeout=5.0,
        )
        assert resp.status_code == 400

    def test_validate_pack_validation(self):
        resp = httpx.post(
            f"{GATEWAY_URL}/tools/validate_pack",
            json={"repo": ""},
            timeout=5.0,
        )
        assert resp.status_code == 400


@skip_no_mcp
class TestMcpToolDiscovery:
    """Verify MCP client can discover tools."""

    def test_list_tools_returns_nine(self):
        # Initialize MCP session
        init_resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            }},
            timeout=5.0,
        )
        assert init_resp.status_code in (200, 202)
        session_id = init_resp.headers.get("Mcp-Session-Id")

        headers = {}
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        # List tools
        list_resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}},
            headers=headers,
            timeout=5.0,
        )
        assert list_resp.status_code in (200, 202)
        data = list_resp.json()
        tools = data.get("result", {}).get("tools", [])
        assert len(tools) == 9


@skip_no_mcp
class TestMcpToolInvocation:
    """Verify MCP tool invocation works end-to-end."""

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Helper: initialize + call tool via MCP protocol."""
        init_resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"},
            }},
            timeout=5.0,
        )
        session_id = init_resp.headers.get("Mcp-Session-Id")
        headers = {}
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "tools/call", "id": 2, "params": {
                "name": tool_name,
                "arguments": arguments,
            }},
            headers=headers,
            timeout=30.0,
        )
        return resp.json()

    def test_validate_pack_via_mcp(self):
        result = self._call_tool("validate_pack", {"repo": "sample-repo-a"})
        # Should succeed or return a structured MCP error
        assert "result" in result or "error" in result

    def test_error_responses_sanitized(self):
        """Trigger an error and verify no internal details leak."""
        result = self._call_tool("get_context_bundle", {"repo": "", "task": "test"})
        full_text = json.dumps(result)
        _assert_no_internal_leaks(full_text)
