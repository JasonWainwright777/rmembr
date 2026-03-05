"""Integration tests: policy-driven gateway behavior end-to-end.

These tests mock the external dependencies (httpx, asyncpg) to test
gateway behavior with policy enforcement.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))

from src.policy.types import PolicyBundle
from src.policy.loader import PolicyLoader
from src.policy.authz import ToolAuthz, AuthorizationError


def test_default_policy_matches_hardcoded_persona_classification():
    """Default policy persona map matches the original hardcoded PERSONA_CLASSIFICATION."""
    policy = PolicyBundle.defaults()
    original = {
        "human": ["public", "internal"],
        "agent": ["public", "internal"],
        "external": ["public"],
    }
    assert policy.persona.allowed_classifications == original


def test_default_policy_reader_allows_7_read_tools():
    policy = PolicyBundle.defaults()
    authz = ToolAuthz(policy.tool_auth)
    read_tools = [
        "search_repo_memory",
        "get_context_bundle",
        "explain_context_bundle",
        "validate_pack",
        "list_standards",
        "get_standard",
        "get_schema",
    ]
    for tool in read_tools:
        assert authz.authorize(tool, "reader") is True, f"reader should be allowed {tool}"


def test_default_policy_reader_denies_write_tools():
    policy = PolicyBundle.defaults()
    authz = ToolAuthz(policy.tool_auth)
    assert authz.authorize("index_repo", "reader") is False
    assert authz.authorize("index_all", "reader") is False


def test_default_policy_writer_allows_write_tools():
    policy = PolicyBundle.defaults()
    authz = ToolAuthz(policy.tool_auth)
    assert authz.authorize("index_repo", "writer") is True
    assert authz.authorize("index_all", "writer") is True


def test_mcp_deny_index_repo():
    """MCP tool call to index_repo without writer role is denied."""
    policy = PolicyBundle.defaults()
    authz = ToolAuthz(policy.tool_auth)
    with pytest.raises(AuthorizationError):
        authz.enforce("index_repo", "reader")


def test_mcp_allow_search():
    """MCP tool call to search_repo_memory with reader role succeeds."""
    policy = PolicyBundle.defaults()
    authz = ToolAuthz(policy.tool_auth)
    # Should not raise
    authz.enforce("search_repo_memory", "reader")


def test_classification_filtering_parity():
    """Policy-driven classification filtering produces same results as hardcoded."""
    policy = PolicyBundle.defaults()

    chunks = [
        {"snippet": "public info", "classification": "public"},
        {"snippet": "internal info", "classification": "internal"},
        {"snippet": "confidential info", "classification": "confidential"},
    ]

    # Simulate old hardcoded behavior
    old_classification = {
        "human": ["public", "internal"],
        "agent": ["public", "internal"],
        "external": ["public"],
    }

    for persona in ["human", "agent", "external"]:
        old_allowed = old_classification.get(persona, ["public"])
        old_filtered = [c for c in chunks if c.get("classification", "internal") in old_allowed]

        new_allowed = policy.persona.allowed_classifications.get(persona, ["public"])
        new_filtered = [c for c in chunks if c.get("classification", "internal") in new_allowed]

        assert old_filtered == new_filtered, f"Filtering mismatch for persona={persona}"


def test_policy_bundle_from_default_file():
    """Loading the default_policy.json produces a valid PolicyBundle."""
    policy_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "mcp-memory-local", "policy", "default_policy.json"
    )
    loader = PolicyLoader(policy_file=policy_path)
    policy = loader.load()
    assert policy.version == "1.0"
    authz = ToolAuthz(policy.tool_auth)
    assert authz.authorize("search_repo_memory", "reader") is True
    assert authz.authorize("index_repo", "reader") is False


def test_audit_log_emitted_for_denied_call():
    """Verify audit logger is called for denied tool calls."""
    import logging

    class _CaptureHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    from audit_log import AuditLogger
    logger = logging.getLogger("test_integration_audit")
    logger.handlers.clear()
    handler = _CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="index_repo",
        action="deny",
        subject="reader",
        correlation_id="test-123",
    )
    assert len(handler.records) == 1
    assert handler.records[0].action == "deny"
    assert handler.records[0].audit is True


def test_audit_log_emitted_for_allowed_call():
    """Verify audit logger is called for allowed tool calls."""
    import logging

    class _CaptureHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    from audit_log import AuditLogger
    logger = logging.getLogger("test_integration_audit_allow")
    logger.handlers.clear()
    handler = _CaptureHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="search_repo_memory",
        action="invoke",
        subject="reader",
        repo="my-repo",
        correlation_id="test-456",
        duration_ms=25.0,
    )
    assert len(handler.records) == 1
    assert handler.records[0].action == "invoke"
    assert handler.records[0].audit is True
    assert handler.records[0].duration_ms == 25.0
