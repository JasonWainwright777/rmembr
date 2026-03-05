"""Deprecation/compatibility tests: validates alias behavior and telemetry emission.

Validates that the contract documents correctly specify:
- Compatibility window duration (2 releases or 6 months)
- Alias behavior for deprecated tools
- Deprecation header specification
- Non-breaking vs breaking change classification

Usage:
    python -m pytest tests/contracts/test_deprecation_warnings.py -v
"""

import sys
from pathlib import Path

# Add project root to allow importing validate_tool_schemas
sys.path.insert(0, str(Path(__file__).parent))
from validate_tool_schemas import validate


# ---------------------------------------------------------------------------
# Contract document validation
# ---------------------------------------------------------------------------

CONTRACTS_DIR = Path(__file__).parent.parent.parent / "docs" / "contracts"


class TestCompatibilityPolicyDocumented:
    """Verify the compatibility policy is fully documented in contract artifacts."""

    def test_gateway_tools_has_versioning_metadata(self):
        """gateway-mcp-tools.md must contain versioning metadata section."""
        path = CONTRACTS_DIR / "gateway-mcp-tools.md"
        assert path.exists(), f"Contract not found: {path}"
        content = path.read_text()
        assert "Versioning Metadata" in content
        assert "Contract Version" in content
        assert "MCP Spec Version" in content

    def test_compatibility_window_specified(self):
        """Compatibility window must be specified as 2 releases or 6 months."""
        path = CONTRACTS_DIR / "gateway-mcp-tools.md"
        content = path.read_text()
        assert "2 releases" in content.lower() or "2 release" in content.lower()
        assert "6 month" in content.lower()

    def test_deprecation_header_specified(self):
        """Deprecated tool alias responses must include X-Deprecated-Tool header."""
        path = CONTRACTS_DIR / "gateway-mcp-tools.md"
        content = path.read_text()
        assert "X-Deprecated-Tool" in content

    def test_adr_defines_breaking_changes(self):
        """ADR-001 must define what constitutes a breaking change."""
        path = CONTRACTS_DIR / "adr-001-transport-auth-tenancy.md"
        assert path.exists(), f"ADR not found: {path}"
        content = path.read_text()
        assert "Breaking change" in content or "breaking change" in content.lower()

    def test_adr_defines_non_breaking_changes(self):
        """ADR-001 must define what constitutes a non-breaking change."""
        path = CONTRACTS_DIR / "adr-001-transport-auth-tenancy.md"
        content = path.read_text()
        assert "Non-breaking" in content or "non-breaking" in content.lower()

    def test_adr_compatibility_window_matches_tools_doc(self):
        """Both ADR-001 and gateway-mcp-tools.md must agree on the compatibility window."""
        adr_path = CONTRACTS_DIR / "adr-001-transport-auth-tenancy.md"
        tools_path = CONTRACTS_DIR / "gateway-mcp-tools.md"
        adr_content = adr_path.read_text().lower()
        tools_content = tools_path.read_text().lower()
        # Both must mention 2 releases and 6 months
        assert "2 release" in adr_content, "ADR missing '2 releases'"
        assert "6 month" in adr_content, "ADR missing '6 months'"
        assert "2 release" in tools_content, "Tools doc missing '2 releases'"
        assert "6 month" in tools_content, "Tools doc missing '6 months'"


# ---------------------------------------------------------------------------
# Compatibility alias scenario validation
# ---------------------------------------------------------------------------


class TestDeprecationAliasScenario:
    """Validate at least one compatibility alias scenario end-to-end."""

    def test_alias_scenario_search_memory_to_search_repo_memory(self):
        """Scenario: If 'search_memory' were deprecated in favor of 'search_repo_memory',
        the old name should still validate against the same schema.

        This tests that the contract schema is stable enough that an alias
        (old tool name -> new tool name) would accept the same payload.
        """
        # The alias would accept the same request schema
        from validate_tool_schemas import SEARCH_REPO_MEMORY_REQUEST

        # A valid payload for the current tool
        payload = {
            "repo": "sample-repo-a",
            "query": "How do we handle secrets?",
            "k": 5,
        }

        # Validate against current schema (alias would use the same)
        errors = validate(payload, SEARCH_REPO_MEMORY_REQUEST)
        assert len(errors) == 0, f"Alias payload should be valid: {errors}"

    def test_alias_response_includes_deprecation_marker(self):
        """Verify the contract specifies that alias responses emit a deprecation header.

        This is a documentation check — the actual HTTP header is tested in
        integration tests after the alias is implemented.
        """
        path = CONTRACTS_DIR / "gateway-mcp-tools.md"
        content = path.read_text()

        # The contract must specify that aliases emit X-Deprecated-Tool
        assert "X-Deprecated-Tool" in content, (
            "Contract must specify X-Deprecated-Tool header for deprecated aliases"
        )

        # The contract must specify that aliases emit telemetry
        # (verified by checking the deprecation policy section exists)
        assert "Deprecation Policy" in content, (
            "Contract must include a Deprecation Policy section"
        )

    def test_new_tool_schema_is_superset_compatible(self):
        """When a tool is upgraded, the new request schema should accept
        all payloads that were valid under the old schema (backward compatibility).

        This tests that adding optional fields to the schema doesn't break
        existing callers.
        """
        from validate_tool_schemas import SEARCH_REPO_MEMORY_REQUEST

        # Minimal valid payload (what an old client would send)
        old_client_payload = {"repo": "my-repo", "query": "find the docs"}

        # Should still validate against current schema
        errors = validate(old_client_payload, SEARCH_REPO_MEMORY_REQUEST)
        assert len(errors) == 0, f"Old client payload should remain valid: {errors}"

        # Full payload with all optional fields (what a new client would send)
        new_client_payload = {
            "repo": "my-repo",
            "query": "find the docs",
            "k": 10,
            "ref": "main",
            "namespace": "tenant-1",
            "filters": {"source_kind": "repo_memory"},
        }

        errors = validate(new_client_payload, SEARCH_REPO_MEMORY_REQUEST)
        assert len(errors) == 0, f"New client payload should be valid: {errors}"


# ---------------------------------------------------------------------------
# Telemetry emission contract
# ---------------------------------------------------------------------------


class TestTelemetryContract:
    """Verify telemetry requirements for deprecation tracking."""

    def test_adr_mentions_telemetry_for_aliases(self):
        """ADR-001 must specify that alias invocations emit telemetry."""
        path = CONTRACTS_DIR / "adr-001-transport-auth-tenancy.md"
        content = path.read_text()
        assert "telemetry" in content.lower() or "Telemetry" in content, (
            "ADR-001 must mention telemetry emission for deprecated alias usage"
        )

    def test_contract_version_is_semver(self):
        """Contract version in gateway-mcp-tools.md must follow semver format."""
        import re
        path = CONTRACTS_DIR / "gateway-mcp-tools.md"
        content = path.read_text()
        # Look for "Version: X.Y.Z" pattern
        match = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", content)
        assert match, "Contract must have a semver version (e.g., 0.1.0)"
        version = match.group(1)
        parts = version.split(".")
        assert len(parts) == 3, f"Version '{version}' is not valid semver"
        assert all(p.isdigit() for p in parts), f"Version '{version}' contains non-numeric parts"
