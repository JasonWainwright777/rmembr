"""Unit tests for policy DTOs."""

import json
import sys
import os

# Add the gateway src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))

from src.policy.types import PolicyBundle, PersonaPolicy, ToolPolicy, BudgetPolicy


def test_persona_policy_creation():
    p = PersonaPolicy(allowed_classifications={"human": ["public", "internal"]})
    assert p.allowed_classifications["human"] == ["public", "internal"]


def test_persona_policy_frozen():
    p = PersonaPolicy(allowed_classifications={"human": ["public"]})
    try:
        p.allowed_classifications = {}
        assert False, "Should be frozen"
    except AttributeError:
        pass


def test_tool_policy_creation():
    tp = ToolPolicy(
        default_action="deny",
        roles={"reader": ["search_repo_memory"]},
        default_role="reader",
    )
    assert tp.default_action == "deny"
    assert tp.default_role == "reader"
    assert "search_repo_memory" in tp.roles["reader"]


def test_budget_policy_defaults():
    bp = BudgetPolicy()
    assert bp.max_bundle_chars == 40000
    assert bp.max_sources == 50
    assert bp.default_k == 12
    assert bp.tool_timeouts == {}
    assert bp.cache_ttl_seconds == 300


def test_budget_policy_custom():
    bp = BudgetPolicy(max_bundle_chars=20000, max_sources=25, default_k=5)
    assert bp.max_bundle_chars == 20000
    assert bp.max_sources == 25
    assert bp.default_k == 5


def test_policy_bundle_defaults():
    pb = PolicyBundle.defaults()
    assert pb.version == "1.0"
    assert pb.persona.allowed_classifications["human"] == ["public", "internal"]
    assert pb.persona.allowed_classifications["external"] == ["public"]
    assert pb.tool_auth.default_action == "deny"
    assert pb.tool_auth.default_role == "reader"
    assert "search_repo_memory" in pb.tool_auth.roles["reader"]
    assert "index_repo" in pb.tool_auth.roles["writer"]
    assert pb.budgets.max_bundle_chars == 40000
    assert pb.budgets.tool_timeouts["search_repo_memory"] == 10
    assert pb.budgets.tool_timeouts["index_repo"] == 120


def test_policy_bundle_from_dict():
    data = {
        "version": "2.0",
        "persona_classification": {
            "human": ["public", "internal", "confidential"],
            "external": ["public"],
        },
        "tool_authorization": {
            "default_action": "deny",
            "roles": {
                "admin": {"allowed_tools": ["index_repo", "index_all", "search_repo_memory"]},
            },
            "default_role": "admin",
        },
        "budgets": {
            "max_bundle_chars": 20000,
            "max_sources": 30,
            "default_k": 8,
            "tool_timeouts": {"search_repo_memory": 15},
            "cache_ttl_seconds": 600,
        },
    }
    pb = PolicyBundle.from_dict(data)
    assert pb.version == "2.0"
    assert "confidential" in pb.persona.allowed_classifications["human"]
    assert pb.tool_auth.default_role == "admin"
    assert "index_repo" in pb.tool_auth.roles["admin"]
    assert pb.budgets.max_bundle_chars == 20000
    assert pb.budgets.max_sources == 30
    assert pb.budgets.tool_timeouts["search_repo_memory"] == 15


def test_policy_bundle_from_dict_minimal():
    """from_dict with empty dict should produce sensible defaults."""
    pb = PolicyBundle.from_dict({})
    assert pb.version == "1.0"
    assert pb.tool_auth.default_action == "deny"
    assert pb.budgets.max_bundle_chars == 40000


def test_from_dict_roundtrip_with_default_policy_file():
    """Verify default_policy.json parses correctly."""
    policy_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "mcp-memory-local", "policy", "default_policy.json"
    )
    with open(policy_path) as f:
        data = json.load(f)
    pb = PolicyBundle.from_dict(data)
    assert pb.version == "1.0"
    assert pb.tool_auth.default_action == "deny"
    assert len(pb.tool_auth.roles["reader"]) == 7
    assert len(pb.tool_auth.roles["writer"]) == 2
    assert pb.budgets.tool_timeouts["index_all"] == 300
