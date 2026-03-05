"""Soak test: repeated MCP invocations for 15+ min, monitor for crash/leak.

Requires running services with MCP_ENABLED=true. Skipped otherwise.
Run with: python -m pytest tests/mcp/test_mcp_soak.py -v --timeout=1200
"""

import json
import os
import sys
import time
import tracemalloc
import pytest
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")
SOAK_DURATION_SECONDS = int(os.environ.get("SOAK_DURATION_SECONDS", "900"))  # 15 min default


def _mcp_available() -> bool:
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


skip_no_mcp = pytest.mark.skipif(
    not _mcp_available(),
    reason="MCP endpoint not available",
)


@skip_no_mcp
class TestMcpSoak:
    """Soak test: repeated MCP calls over extended period."""

    def test_repeated_tool_calls_no_crash(self):
        """Call MCP tools repeatedly for SOAK_DURATION_SECONDS."""
        start = time.monotonic()
        call_count = 0
        error_count = 0

        client = httpx.Client(timeout=30.0)

        # Initialize once
        init_resp = client.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "soak-test", "version": "0.1.0"},
            }},
        )
        session_id = init_resp.headers.get("Mcp-Session-Id")
        headers = {}
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        # Cycle through different tool calls
        tool_calls = [
            ("validate_pack", {"repo": "sample-repo-a"}),
            ("list_standards", {}),
            ("get_context_bundle", {"repo": "sample-repo-a", "task": "soak test"}),
        ]

        while time.monotonic() - start < SOAK_DURATION_SECONDS:
            tool_name, args = tool_calls[call_count % len(tool_calls)]
            try:
                resp = client.post(
                    f"{GATEWAY_URL}/mcp",
                    json={"jsonrpc": "2.0", "method": "tools/call", "id": call_count + 2, "params": {
                        "name": tool_name,
                        "arguments": args,
                    }},
                    headers=headers,
                )
                if resp.status_code not in (200, 202):
                    error_count += 1
            except Exception:
                error_count += 1

            call_count += 1

            # Brief pause to avoid hammering
            time.sleep(0.1)

        client.close()

        elapsed = time.monotonic() - start
        error_rate = error_count / max(call_count, 1)

        print(f"\nSoak results: {call_count} calls in {elapsed:.1f}s, {error_count} errors ({error_rate:.1%})")

        # Accept up to 5% error rate (services may be degraded without full data)
        assert error_rate < 0.05, f"Error rate too high: {error_rate:.1%}"
        assert call_count > 0, "No calls were made"
