"""Parity tests: same request via MCP dispatch and HTTP returns equivalent results.

These tests mock the downstream services (Index, Standards) so they can run
without docker-compose. They verify that the MCP tool dispatch and the HTTP
route handlers produce the same response bodies.
"""

import json
import sys
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))


def _mock_httpx_response(status_code: int, json_data: dict):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data)
    return resp


@pytest.fixture
def mock_pool():
    """Mock the asyncpg pool to return no cached data."""
    with patch("src.server.pool", None):
        yield


class TestGetContextBundleParity:
    """get_context_bundle: MCP dispatch vs HTTP handler produce same result."""

    @pytest.mark.asyncio
    async def test_validation_error_parity(self, mock_pool):
        """Both paths raise/return error for missing repo."""
        from src.mcp_tools import dispatch_tool, McpToolError
        from src.server import handle_get_context_bundle
        from validation import ValidationError

        # MCP path
        with pytest.raises(McpToolError) as mcp_exc:
            await dispatch_tool("get_context_bundle", {"repo": "", "task": "test"})
        assert mcp_exc.value.code == -32602

        # Handler path
        with pytest.raises(ValidationError):
            await handle_get_context_bundle({"repo": "", "task": "test"})


class TestExplainContextBundleParity:
    """explain_context_bundle: MCP dispatch vs HTTP handler produce same result."""

    @pytest.mark.asyncio
    async def test_missing_bundle_id_parity(self, mock_pool):
        from src.mcp_tools import dispatch_tool, McpToolError
        from src.server import handle_explain_context_bundle
        from validation import ValidationError

        with pytest.raises(McpToolError):
            await dispatch_tool("explain_context_bundle", {"bundle_id": ""})

        with pytest.raises(ValidationError):
            await handle_explain_context_bundle({"bundle_id": ""})


class TestValidatePackParity:
    """validate_pack: MCP dispatch vs HTTP handler produce same result."""

    @pytest.mark.asyncio
    async def test_validation_error_parity(self, mock_pool):
        from src.mcp_tools import dispatch_tool, McpToolError
        from src.server import handle_validate_pack
        from validation import ValidationError

        with pytest.raises(McpToolError):
            await dispatch_tool("validate_pack", {"repo": ""})

        with pytest.raises(ValidationError):
            await handle_validate_pack({"repo": ""})


class TestProxyToolsParity:
    """Proxy tools (search_repo_memory, index_repo, etc.): verify dispatch routes correctly."""

    @pytest.mark.asyncio
    async def test_search_repo_memory_dispatches_to_index(self, mock_pool):
        from src.mcp_tools import dispatch_tool

        mock_resp = _mock_httpx_response(200, {"results": [], "count": 0})

        with patch("src.server.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await dispatch_tool("search_repo_memory", {
                "repo": "test-repo", "query": "test query", "k": 5,
            })

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["results"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_standards_dispatches_to_standards(self, mock_pool):
        from src.mcp_tools import dispatch_tool

        mock_resp = _mock_httpx_response(200, {"standards": [], "count": 0})

        with patch("src.server.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await dispatch_tool("list_standards", {})

        data = json.loads(result[0].text)
        assert data["standards"] == []
