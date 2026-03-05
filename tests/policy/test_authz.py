"""Unit tests for ToolAuthz allow/deny matrix."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))

import pytest
from src.policy.authz import ToolAuthz, AuthorizationError
from src.policy.types import ToolPolicy, PolicyBundle


@pytest.fixture
def default_policy():
    return PolicyBundle.defaults()


@pytest.fixture
def authz(default_policy):
    return ToolAuthz(default_policy.tool_auth)


# Reader role: 7 read tools allowed
@pytest.mark.parametrize("tool", [
    "search_repo_memory",
    "get_context_bundle",
    "explain_context_bundle",
    "validate_pack",
    "list_standards",
    "get_standard",
    "get_schema",
])
def test_reader_allowed_tools(authz, tool):
    assert authz.authorize(tool, "reader") is True


# Reader role: write tools denied
@pytest.mark.parametrize("tool", ["index_repo", "index_all"])
def test_reader_denied_write_tools(authz, tool):
    assert authz.authorize(tool, "reader") is False


# Writer role: write tools allowed
@pytest.mark.parametrize("tool", ["index_repo", "index_all"])
def test_writer_allowed_tools(authz, tool):
    assert authz.authorize(tool, "writer") is True


# Writer role: read tools denied (writer is scoped)
@pytest.mark.parametrize("tool", [
    "search_repo_memory",
    "get_context_bundle",
    "explain_context_bundle",
    "validate_pack",
    "list_standards",
    "get_standard",
    "get_schema",
])
def test_writer_denied_read_tools(authz, tool):
    assert authz.authorize(tool, "writer") is False


def test_no_role_falls_back_to_default(authz):
    """No role -> uses default_role (reader)."""
    assert authz.authorize("search_repo_memory", None) is True
    assert authz.authorize("index_repo", None) is False


def test_unknown_role_falls_back_to_default(authz):
    """Unknown role with deny-by-default -> denied."""
    assert authz.authorize("search_repo_memory", "unknown_role") is False
    assert authz.authorize("index_repo", "unknown_role") is False


def test_unknown_tool_denied(authz):
    """Unknown tool name denied for any role."""
    assert authz.authorize("nonexistent_tool", "reader") is False
    assert authz.authorize("nonexistent_tool", "writer") is False


def test_enforce_raises_on_deny(authz):
    with pytest.raises(AuthorizationError) as exc_info:
        authz.enforce("index_repo", "reader")
    assert "index_repo" in str(exc_info.value)
    assert "reader" in str(exc_info.value)


def test_enforce_passes_on_allow(authz):
    # Should not raise
    authz.enforce("search_repo_memory", "reader")


def test_allow_default_action():
    """When default_action is 'allow', unknown tools are allowed."""
    policy = ToolPolicy(
        default_action="allow",
        roles={"reader": ["search_repo_memory"]},
        default_role="reader",
    )
    authz = ToolAuthz(policy)
    assert authz.authorize("unknown_tool", "reader") is True
    assert authz.authorize("index_repo", "reader") is True


def test_authorization_error_attributes():
    err = AuthorizationError("index_repo", "reader")
    assert err.tool_name == "index_repo"
    assert err.role == "reader"
    assert "index_repo" in str(err)
