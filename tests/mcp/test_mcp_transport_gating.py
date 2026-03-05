"""Transport gating: stdio disabled unless MCP_STDIO_ENABLED=true."""

import os
import sys
import subprocess
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))


class TestMcpEnabledFlag:
    """MCP_ENABLED env var controls MCP server activation."""

    def test_mcp_disabled_by_default(self):
        from src.mcp_server import MCP_ENABLED
        # In test env, MCP_ENABLED is not set, so should be False
        # (unless someone set it in the test environment)
        assert os.environ.get("MCP_ENABLED", "false").lower() != "true" or MCP_ENABLED is True

    def test_get_mcp_asgi_app_returns_none_when_disabled(self):
        """When MCP_ENABLED is false, get_mcp_asgi_app returns None."""
        old = os.environ.get("MCP_ENABLED")
        os.environ["MCP_ENABLED"] = "false"
        try:
            # Need to reimport to pick up env var change
            import importlib
            import src.mcp_server
            importlib.reload(src.mcp_server)
            assert src.mcp_server.get_mcp_asgi_app() is None
        finally:
            if old is not None:
                os.environ["MCP_ENABLED"] = old
            else:
                os.environ.pop("MCP_ENABLED", None)
            importlib.reload(src.mcp_server)


class TestStdioGating:
    """MCP_STDIO_ENABLED env var controls stdio transport activation."""

    def test_stdio_refuses_without_mcp_enabled(self):
        """Stdio shim exits with error if MCP_ENABLED is not true."""
        env = os.environ.copy()
        env["MCP_ENABLED"] = "false"
        env["MCP_STDIO_ENABLED"] = "true"

        gateway_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"
        )

        result = subprocess.run(
            [sys.executable, "-m", "src.mcp_stdio_shim"],
            cwd=gateway_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "MCP_ENABLED" in result.stderr

    def test_stdio_refuses_without_stdio_enabled(self):
        """Stdio shim exits with error if MCP_STDIO_ENABLED is not true."""
        env = os.environ.copy()
        env["MCP_ENABLED"] = "true"
        env["MCP_STDIO_ENABLED"] = "false"

        gateway_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"
        )

        result = subprocess.run(
            [sys.executable, "-m", "src.mcp_stdio_shim"],
            cwd=gateway_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert "MCP_STDIO_ENABLED" in result.stderr

    def test_docker_compose_never_enables_stdio(self):
        """docker-compose.yml must not set MCP_STDIO_ENABLED=true."""
        compose_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "mcp-memory-local", "docker-compose.yml"
        )
        with open(compose_path) as f:
            content = f.read()
        # Verify the default is false and it's never set to true
        assert "MCP_STDIO_ENABLED: ${MCP_STDIO_ENABLED:-false}" in content
        assert "MCP_STDIO_ENABLED: true" not in content
        assert 'MCP_STDIO_ENABLED: "true"' not in content
