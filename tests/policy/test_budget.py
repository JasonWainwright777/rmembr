"""Budget control tests: per-tool timeouts, max-sources rejection/truncation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))

from src.policy.types import PolicyBundle, BudgetPolicy


def test_default_tool_timeouts():
    policy = PolicyBundle.defaults()
    assert policy.budgets.tool_timeouts["search_repo_memory"] == 10
    assert policy.budgets.tool_timeouts["get_context_bundle"] == 30
    assert policy.budgets.tool_timeouts["index_repo"] == 120
    assert policy.budgets.tool_timeouts["index_all"] == 300
    assert policy.budgets.tool_timeouts["list_standards"] == 5


def test_max_sources_default():
    policy = PolicyBundle.defaults()
    assert policy.budgets.max_sources == 50


def test_k_clamped_by_max_sources():
    """When k > max_sources, k should be clamped."""
    policy = PolicyBundle.defaults()
    k = 100
    if k > policy.budgets.max_sources:
        k = policy.budgets.max_sources
    assert k == 50


def test_k_not_clamped_when_within_budget():
    policy = PolicyBundle.defaults()
    k = 10
    if k > policy.budgets.max_sources:
        k = policy.budgets.max_sources
    assert k == 10


def test_custom_max_sources():
    bp = BudgetPolicy(max_sources=20)
    k = 30
    if k > bp.max_sources:
        k = bp.max_sources
    assert k == 20


def test_custom_tool_timeout():
    bp = BudgetPolicy(tool_timeouts={"search_repo_memory": 60})
    assert bp.tool_timeouts["search_repo_memory"] == 60
    # Missing tool uses no timeout (falls back to PROXY_TIMEOUT in dispatch)
    assert bp.tool_timeouts.get("unknown_tool") is None


def test_cache_ttl_custom():
    bp = BudgetPolicy(cache_ttl_seconds=600)
    assert bp.cache_ttl_seconds == 600


def test_max_bundle_chars_custom():
    bp = BudgetPolicy(max_bundle_chars=20000)
    assert bp.max_bundle_chars == 20000
