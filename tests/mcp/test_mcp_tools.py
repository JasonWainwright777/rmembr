"""Unit tests: MCP tool registration, payload coercion, error mapping."""

import json
import sys
import os
import re
import pytest

# Set up paths to match container layout for local testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))


class TestToolRegistration:
    """Verify all 9 tools are registered with correct schemas."""

    def test_all_nine_tools_defined(self):
        from src.mcp_tools import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) == 9

    def test_tool_names_match_contract(self):
        from src.mcp_tools import TOOL_DEFINITIONS
        expected = {
            "search_repo_memory", "get_context_bundle", "explain_context_bundle",
            "validate_pack", "index_repo", "index_all",
            "list_standards", "get_standard", "get_schema",
        }
        actual = {t.name for t in TOOL_DEFINITIONS}
        assert actual == expected

    def test_all_tools_have_input_schema(self):
        from src.mcp_tools import TOOL_DEFINITIONS
        for tool in TOOL_DEFINITIONS:
            assert tool.inputSchema is not None
            assert tool.inputSchema["type"] == "object"

    def test_required_fields_present(self):
        from src.mcp_tools import TOOL_DEFINITIONS
        tool_map = {t.name: t for t in TOOL_DEFINITIONS}

        assert "repo" in tool_map["search_repo_memory"].inputSchema["required"]
        assert "query" in tool_map["search_repo_memory"].inputSchema["required"]
        assert "repo" in tool_map["get_context_bundle"].inputSchema["required"]
        assert "task" in tool_map["get_context_bundle"].inputSchema["required"]
        assert "bundle_id" in tool_map["explain_context_bundle"].inputSchema["required"]
        assert "repo" in tool_map["validate_pack"].inputSchema["required"]
        assert "repo" in tool_map["index_repo"].inputSchema["required"]
        assert "id" in tool_map["get_standard"].inputSchema["required"]
        assert "id" in tool_map["get_schema"].inputSchema["required"]

    def test_dispatch_map_covers_all_tools(self):
        from src.mcp_tools import TOOL_DEFINITIONS, _TOOL_DISPATCH
        for tool in TOOL_DEFINITIONS:
            assert tool.name in _TOOL_DISPATCH, f"{tool.name} missing from dispatch"


class TestErrorMapping:
    """Verify error mapping and sanitization."""

    def test_validation_error_maps_to_invalid_params(self):
        from src.mcp_errors import map_validation_error
        from validation import ValidationError
        from mcp.types import INVALID_PARAMS

        exc = ValidationError("repo", "must not be empty")
        code, msg = map_validation_error(exc)
        assert code == INVALID_PARAMS
        assert "must not be empty" in msg

    def test_runtime_error_maps_to_internal_error(self):
        from src.mcp_errors import map_runtime_error
        from mcp.types import INTERNAL_ERROR

        exc = RuntimeError("Something broke")
        code, msg = map_runtime_error(exc)
        assert code == INTERNAL_ERROR

    def test_generic_exception_maps_to_internal_error(self):
        from src.mcp_errors import map_exception
        from mcp.types import INTERNAL_ERROR

        code, msg = map_exception(Exception("unexpected"))
        assert code == INTERNAL_ERROR
        assert msg == "Internal server error"


class TestErrorSanitization:
    """Verify internal details are stripped from error messages."""

    def test_internal_urls_redacted(self):
        from src.mcp_errors import sanitize_message

        msg = "Failed to connect to http://index:8081/tools/search"
        sanitized = sanitize_message(msg)
        assert "http://index:8081" not in sanitized
        assert "[redacted]" in sanitized

    def test_standards_url_redacted(self):
        from src.mcp_errors import sanitize_message

        msg = "Error from http://standards:8082/tools/list_standards"
        sanitized = sanitize_message(msg)
        assert "http://standards:8082" not in sanitized

    def test_token_references_redacted(self):
        from src.mcp_errors import sanitize_message

        msg = "INTERNAL_SERVICE_TOKEN=abc123 was rejected"
        sanitized = sanitize_message(msg)
        assert "INTERNAL_SERVICE_TOKEN" not in sanitized

    def test_container_paths_redacted(self):
        from src.mcp_errors import sanitize_message

        msg = "FileNotFoundError: /app/shared/src/validation/validators.py"
        sanitized = sanitize_message(msg)
        assert "/app/" not in sanitized

    def test_stack_traces_redacted(self):
        from src.mcp_errors import sanitize_message

        msg = 'Traceback (most recent call last)\n  File "/app/server.py", line 42\nRuntimeError: fail'
        sanitized = sanitize_message(msg)
        assert "Traceback" not in sanitized

    def test_clean_message_passes_through(self):
        from src.mcp_errors import sanitize_message

        msg = "Validation error on 'repo': must not be empty"
        assert sanitize_message(msg) == msg


class TestMcpToolError:
    """Verify McpToolError wrapping."""

    def test_carries_code_and_message(self):
        from src.mcp_tools import McpToolError

        err = McpToolError(-32602, "bad input")
        assert err.code == -32602
        assert err.message == "bad input"
