"""Unit tests for PolicyLoader."""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "gateway"))

from src.policy.loader import PolicyLoader
from src.policy.types import PolicyBundle


def test_load_defaults_when_no_file():
    loader = PolicyLoader(policy_file=None)
    policy = loader.load()
    assert policy.version == "1.0"
    assert policy.tool_auth.default_action == "deny"
    defaults = PolicyBundle.defaults()
    assert policy.persona.allowed_classifications == defaults.persona.allowed_classifications


def test_load_from_file():
    data = {
        "version": "2.0",
        "persona_classification": {"human": ["public"]},
        "tool_authorization": {
            "default_action": "allow",
            "roles": {"admin": {"allowed_tools": ["index_repo"]}},
            "default_role": "admin",
        },
        "budgets": {"max_bundle_chars": 10000},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        path = f.name

    try:
        loader = PolicyLoader(policy_file=path)
        policy = loader.load()
        assert policy.version == "2.0"
        assert policy.tool_auth.default_action == "allow"
        assert policy.budgets.max_bundle_chars == 10000
    finally:
        os.unlink(path)


def test_load_falls_back_on_missing_file():
    loader = PolicyLoader(policy_file="/nonexistent/path/policy.json")
    policy = loader.load()
    # Should fall back to defaults
    assert policy.version == "1.0"
    assert policy.tool_auth.default_action == "deny"


def test_load_falls_back_on_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json {{{")
        f.flush()
        path = f.name

    try:
        loader = PolicyLoader(policy_file=path)
        policy = loader.load()
        assert policy.version == "1.0"  # defaults
    finally:
        os.unlink(path)


def test_policy_property_lazy_loads():
    loader = PolicyLoader(policy_file=None)
    # No explicit load() call
    policy = loader.policy
    assert policy is not None
    assert policy.version == "1.0"


def test_hot_reload_detects_change():
    data_v1 = {"version": "1.0", "budgets": {"max_bundle_chars": 10000}}
    data_v2 = {"version": "2.0", "budgets": {"max_bundle_chars": 20000}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data_v1, f)
        f.flush()
        path = f.name

    try:
        loader = PolicyLoader(policy_file=path, hot_reload=True)
        policy1 = loader.policy
        assert policy1.budgets.max_bundle_chars == 10000

        # Wait briefly then update file
        time.sleep(0.1)
        with open(path, "w") as f:
            json.dump(data_v2, f)

        policy2 = loader.policy
        assert policy2.budgets.max_bundle_chars == 20000
    finally:
        os.unlink(path)


def test_no_reload_when_disabled():
    data_v1 = {"version": "1.0", "budgets": {"max_bundle_chars": 10000}}
    data_v2 = {"version": "2.0", "budgets": {"max_bundle_chars": 20000}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data_v1, f)
        f.flush()
        path = f.name

    try:
        loader = PolicyLoader(policy_file=path, hot_reload=False)
        policy1 = loader.policy
        assert policy1.budgets.max_bundle_chars == 10000

        time.sleep(0.1)
        with open(path, "w") as f:
            json.dump(data_v2, f)

        # Should NOT reload since hot_reload=False
        policy2 = loader.policy
        assert policy2.budgets.max_bundle_chars == 10000
    finally:
        os.unlink(path)


def test_retains_last_good_on_parse_error():
    data_v1 = {"version": "1.0", "budgets": {"max_bundle_chars": 10000}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data_v1, f)
        f.flush()
        path = f.name

    try:
        loader = PolicyLoader(policy_file=path, hot_reload=True)
        policy1 = loader.policy
        assert policy1.budgets.max_bundle_chars == 10000

        # Write invalid JSON
        time.sleep(0.1)
        with open(path, "w") as f:
            f.write("invalid json")

        # Should retain last-good policy
        policy2 = loader.policy
        assert policy2.budgets.max_bundle_chars == 10000
    finally:
        os.unlink(path)
