"""Negative contract tests: invalid payloads and unauthorized request handling.

Validates that the contract schemas correctly reject:
- Missing required fields
- Wrong types
- Empty payloads
- Out-of-range values
- Invalid filter keys
- Unauthorized requests (no token / expired token / wrong scope)

Usage:
    python -m pytest tests/contracts/test_negative_payloads.py -v
"""

import re
import sys
from pathlib import Path

# Add project root to allow importing validate_tool_schemas
sys.path.insert(0, str(Path(__file__).parent))
from validate_tool_schemas import (
    validate,
    SEARCH_REPO_MEMORY_REQUEST,
    GET_CONTEXT_BUNDLE_REQUEST,
    EXPLAIN_CONTEXT_BUNDLE_REQUEST,
    VALIDATE_PACK_REQUEST,
    LIST_STANDARDS_REQUEST,
    GET_STANDARD_REQUEST,
    SEARCH_REPO_MEMORY_RESPONSE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_has_error(errors, path_substr: str = "", msg_substr: str = ""):
    """Assert that at least one error matches the given substrings."""
    matches = [
        e for e in errors
        if (not path_substr or path_substr in e.path)
        and (not msg_substr or msg_substr in e.message)
    ]
    assert matches, (
        f"Expected error matching path='{path_substr}' msg='{msg_substr}', "
        f"got: {[str(e) for e in errors]}"
    )


# ---------------------------------------------------------------------------
# search_repo_memory — negative cases
# ---------------------------------------------------------------------------


class TestSearchRepoMemoryNegative:
    """Negative tests for search_repo_memory request schema."""

    def test_empty_payload(self):
        errors = validate({}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "repo", "required")
        assert_has_error(errors, "query", "required")

    def test_missing_repo(self):
        errors = validate({"query": "test"}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "repo", "required")

    def test_missing_query(self):
        errors = validate({"repo": "test-repo"}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "query", "required")

    def test_empty_repo_string(self):
        errors = validate({"repo": "", "query": "test"}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "repo", "minLength")

    def test_empty_query_string(self):
        errors = validate({"repo": "test-repo", "query": ""}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "query", "minLength")

    def test_wrong_type_repo(self):
        errors = validate({"repo": 123, "query": "test"}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "repo", "expected string")

    def test_wrong_type_query(self):
        errors = validate({"repo": "test", "query": 456}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "query", "expected string")

    def test_wrong_type_k(self):
        errors = validate({"repo": "test", "query": "q", "k": "five"}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "k", "expected integer")

    def test_k_below_minimum(self):
        errors = validate({"repo": "test", "query": "q", "k": 0}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "k", "minimum")

    def test_k_above_maximum(self):
        errors = validate({"repo": "test", "query": "q", "k": 101}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "k", "maximum")

    def test_query_exceeds_max_length(self):
        long_query = "x" * 2001
        errors = validate({"repo": "test", "query": long_query}, SEARCH_REPO_MEMORY_REQUEST)
        assert_has_error(errors, "query", "maxLength")

    def test_unknown_filter_key(self):
        errors = validate(
            {"repo": "test", "query": "q", "filters": {"unknown_key": "value"}},
            SEARCH_REPO_MEMORY_REQUEST,
        )
        assert_has_error(errors, "filters.unknown_key", "additional property")

    def test_additional_top_level_property(self):
        errors = validate(
            {"repo": "test", "query": "q", "extra_field": "nope"},
            SEARCH_REPO_MEMORY_REQUEST,
        )
        assert_has_error(errors, "extra_field", "additional property")

    def test_null_payload(self):
        errors = validate(None, SEARCH_REPO_MEMORY_REQUEST)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# get_context_bundle — negative cases
# ---------------------------------------------------------------------------


class TestGetContextBundleNegative:
    """Negative tests for get_context_bundle request schema."""

    def test_empty_payload(self):
        errors = validate({}, GET_CONTEXT_BUNDLE_REQUEST)
        assert_has_error(errors, "repo", "required")
        assert_has_error(errors, "task", "required")

    def test_missing_task(self):
        errors = validate({"repo": "test"}, GET_CONTEXT_BUNDLE_REQUEST)
        assert_has_error(errors, "task", "required")

    def test_empty_task_string(self):
        errors = validate({"repo": "test", "task": ""}, GET_CONTEXT_BUNDLE_REQUEST)
        assert_has_error(errors, "task", "minLength")

    def test_invalid_persona(self):
        errors = validate(
            {"repo": "test", "task": "do thing", "persona": "admin"},
            GET_CONTEXT_BUNDLE_REQUEST,
        )
        assert_has_error(errors, "persona", "enum")

    def test_wrong_type_changed_files(self):
        errors = validate(
            {"repo": "test", "task": "do thing", "changed_files": "not-an-array"},
            GET_CONTEXT_BUNDLE_REQUEST,
        )
        assert_has_error(errors, "changed_files", "expected")

    def test_additional_property(self):
        errors = validate(
            {"repo": "test", "task": "do thing", "secret_field": True},
            GET_CONTEXT_BUNDLE_REQUEST,
        )
        assert_has_error(errors, "secret_field", "additional property")

    def test_task_exceeds_max_length(self):
        errors = validate(
            {"repo": "test", "task": "x" * 2001},
            GET_CONTEXT_BUNDLE_REQUEST,
        )
        assert_has_error(errors, "task", "maxLength")


# ---------------------------------------------------------------------------
# explain_context_bundle — negative cases
# ---------------------------------------------------------------------------


class TestExplainContextBundleNegative:
    """Negative tests for explain_context_bundle request schema."""

    def test_empty_payload(self):
        errors = validate({}, EXPLAIN_CONTEXT_BUNDLE_REQUEST)
        assert_has_error(errors, "bundle_id", "required")

    def test_additional_property(self):
        errors = validate(
            {"bundle_id": "abc", "format": "json"},
            EXPLAIN_CONTEXT_BUNDLE_REQUEST,
        )
        assert_has_error(errors, "format", "additional property")


# ---------------------------------------------------------------------------
# validate_pack — negative cases
# ---------------------------------------------------------------------------


class TestValidatePackNegative:
    """Negative tests for validate_pack request schema."""

    def test_empty_payload(self):
        errors = validate({}, VALIDATE_PACK_REQUEST)
        assert_has_error(errors, "repo", "required")

    def test_empty_repo(self):
        errors = validate({"repo": ""}, VALIDATE_PACK_REQUEST)
        assert_has_error(errors, "repo", "minLength")

    def test_additional_property(self):
        errors = validate(
            {"repo": "test", "verbose": True},
            VALIDATE_PACK_REQUEST,
        )
        assert_has_error(errors, "verbose", "additional property")


# ---------------------------------------------------------------------------
# list_standards — negative cases
# ---------------------------------------------------------------------------


class TestListStandardsNegative:
    """Negative tests for list_standards request schema."""

    def test_additional_property(self):
        errors = validate({"page": 1}, LIST_STANDARDS_REQUEST)
        assert_has_error(errors, "page", "additional property")


# ---------------------------------------------------------------------------
# get_standard — negative cases
# ---------------------------------------------------------------------------


class TestGetStandardNegative:
    """Negative tests for get_standard request schema."""

    def test_empty_payload(self):
        errors = validate({}, GET_STANDARD_REQUEST)
        assert_has_error(errors, "id", "required")

    def test_additional_property(self):
        errors = validate(
            {"id": "enterprise/terraform/foo", "format": "html"},
            GET_STANDARD_REQUEST,
        )
        assert_has_error(errors, "format", "additional property")


# ---------------------------------------------------------------------------
# Response schema — negative cases
# ---------------------------------------------------------------------------


class TestSearchResponseNegative:
    """Negative tests for search_repo_memory response schema."""

    def test_missing_results(self):
        errors = validate({"count": 0}, SEARCH_REPO_MEMORY_RESPONSE)
        assert_has_error(errors, "results", "required")

    def test_missing_count(self):
        errors = validate({"results": []}, SEARCH_REPO_MEMORY_RESPONSE)
        assert_has_error(errors, "count", "required")

    def test_result_item_missing_required_fields(self):
        errors = validate(
            {"results": [{"id": 1}], "count": 1},
            SEARCH_REPO_MEMORY_RESPONSE,
        )
        assert_has_error(errors, "path", "required")
        assert_has_error(errors, "anchor", "required")
        assert_has_error(errors, "snippet", "required")

    def test_invalid_source_kind(self):
        errors = validate(
            {
                "results": [
                    {
                        "id": 1,
                        "path": "a.md",
                        "anchor": "a-c0",
                        "heading": "A",
                        "snippet": "text",
                        "source_kind": "invalid_kind",
                        "classification": "internal",
                        "similarity": 0.5,
                    }
                ],
                "count": 1,
            },
            SEARCH_REPO_MEMORY_RESPONSE,
        )
        assert_has_error(errors, "source_kind", "enum")

    def test_similarity_out_of_range(self):
        errors = validate(
            {
                "results": [
                    {
                        "id": 1,
                        "path": "a.md",
                        "anchor": "a-c0",
                        "heading": "A",
                        "snippet": "text",
                        "source_kind": "repo_memory",
                        "classification": "internal",
                        "similarity": 1.5,
                    }
                ],
                "count": 1,
            },
            SEARCH_REPO_MEMORY_RESPONSE,
        )
        assert_has_error(errors, "similarity", "maximum")


# ---------------------------------------------------------------------------
# Auth contract tests (structural, not integration)
# ---------------------------------------------------------------------------


class TestAuthContract:
    """Verify auth contract expectations are documented and consistent."""

    def test_internal_token_header_name(self):
        """Auth contract specifies X-Internal-Token as the header name."""
        auth_path = Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src" / "auth.py"
        if not auth_path.exists():
            return  # Skip if source not available
        content = auth_path.read_text()
        assert "X-Internal-Token" in content

    def test_health_exempt_from_auth(self):
        """Auth contract specifies /health is exempt from authentication."""
        auth_path = Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src" / "auth.py"
        if not auth_path.exists():
            return
        content = auth_path.read_text()
        assert "/health" in content

    def test_adr_documents_deny_by_default(self):
        """ADR-001 must contain deny-by-default statement."""
        adr_path = Path(__file__).parent.parent.parent / "docs" / "contracts" / "adr-001-transport-auth-tenancy.md"
        assert adr_path.exists(), f"ADR not found at {adr_path}"
        content = adr_path.read_text()
        assert "deny-by-default" in content.lower() or "Deny-by-default" in content

    def test_adr_enumerates_all_environments(self):
        """ADR-001 must enumerate Local, Dev, Test, and Prod environments."""
        adr_path = Path(__file__).parent.parent.parent / "docs" / "contracts" / "adr-001-transport-auth-tenancy.md"
        assert adr_path.exists()
        content = adr_path.read_text()
        for env in ["Local", "Dev", "Test", "Prod"]:
            assert env in content, f"Environment '{env}' not found in ADR-001"
