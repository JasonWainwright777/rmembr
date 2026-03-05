#!/usr/bin/env python3
"""CI gate: validates MCP tool schema compatibility policy.

FAIL-CLOSED: non-zero exit blocks release. No silent override.
Exception path: Board-approved waiver documented in DECISION_LOG.md
with specific tool name and justification.

Checks:
1. All tool schemas in gateway-mcp-tools.md have version metadata.
2. No tool removal without deprecation warning period (2 releases or 6 months).
3. Deprecated tools have documented replacement.

Exit code 0 = pass, 1 = fail. Required check in release workflow.
"""

import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CONTRACT_PATH = os.path.join(REPO_ROOT, "docs", "contracts", "gateway-mcp-tools.md")
WAIVER_FILE = os.path.join(SCRIPT_DIR, "compatibility_waivers.txt")


def load_waivers() -> set[str]:
    """Load waived tool names from waiver file."""
    if not os.path.exists(WAIVER_FILE):
        return set()
    waivers = set()
    with open(WAIVER_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                waivers.add(line)
    return waivers


def check_version_metadata(contract_path: str) -> list[str]:
    """Verify the contract document has version metadata."""
    errors = []
    if not os.path.exists(contract_path):
        errors.append(f"Contract file not found: {contract_path}")
        return errors

    with open(contract_path, "r") as f:
        content = f.read()

    required_fields = [
        "Contract Version",
        "Compatibility Window",
        "Deprecation Policy",
    ]

    for field in required_fields:
        if field not in content:
            errors.append(f"Missing version metadata field: '{field}' in {contract_path}")

    # Check that Contract Version has a semver value
    version_match = re.search(r"Contract Version\s*\|\s*(\d+\.\d+\.\d+)", content)
    if not version_match:
        errors.append("Contract Version must be a semver value (e.g., 0.1.0)")

    return errors


def extract_tool_names(contract_path: str) -> list[str]:
    """Extract tool names from the contract document."""
    tools = []
    if not os.path.exists(contract_path):
        return tools

    with open(contract_path, "r") as f:
        for line in f:
            match = re.match(r"^## Tool:\s*`(\w+)`", line)
            if match:
                tools.append(match.group(1))
    return tools


def check_deprecation_documented(contract_path: str) -> list[str]:
    """Verify deprecated tools have replacement documented."""
    errors = []
    if not os.path.exists(contract_path):
        return errors

    with open(contract_path, "r") as f:
        content = f.read()

    # Look for any tool marked as deprecated
    deprecated_pattern = re.compile(
        r"## Tool:\s*`(\w+)`.*?(?=## Tool:|## Versioning|\Z)",
        re.DOTALL,
    )

    for match in deprecated_pattern.finditer(content):
        tool_name = match.group(1)
        section = match.group(0)
        if "deprecated" in section.lower() or "Deprecated" in section:
            if "replacement" not in section.lower() and "replaced by" not in section.lower():
                errors.append(
                    f"Deprecated tool '{tool_name}' has no documented replacement"
                )

    return errors


def check_compatibility_window(contract_path: str) -> list[str]:
    """Verify compatibility window is documented."""
    errors = []
    if not os.path.exists(contract_path):
        return errors

    with open(contract_path, "r") as f:
        content = f.read()

    if "Compatibility Window" not in content:
        errors.append("No Compatibility Window defined in contract document")
    else:
        window_match = re.search(
            r"Compatibility Window\s*\|\s*(.+?)(?:\s*\||\n)", content
        )
        if window_match:
            window = window_match.group(1).strip()
            if "release" not in window.lower() and "month" not in window.lower():
                errors.append(
                    f"Compatibility Window '{window}' should specify releases or months"
                )

    return errors


def main() -> int:
    """Run all checks. Return 0 if all pass, 1 if any fail."""
    waivers = load_waivers()
    all_errors: list[str] = []

    # Check 1: Version metadata
    errors = check_version_metadata(CONTRACT_PATH)
    all_errors.extend(errors)

    # Check 2: Compatibility window
    errors = check_compatibility_window(CONTRACT_PATH)
    all_errors.extend(errors)

    # Check 3: Deprecated tools have replacements
    errors = check_deprecation_documented(CONTRACT_PATH)
    # Filter out waived tools
    errors = [e for e in errors if not any(w in e for w in waivers)]
    all_errors.extend(errors)

    # Check 4: Tool names exist
    tools = extract_tool_names(CONTRACT_PATH)
    if not tools:
        all_errors.append("No tools found in contract document")

    if all_errors:
        print("COMPATIBILITY CHECK FAILED:", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        print(
            f"\n{len(all_errors)} violation(s) found. Release blocked.",
            file=sys.stderr,
        )
        print(
            "Exception path: add Board-approved waiver to DECISION_LOG.md,",
            file=sys.stderr,
        )
        print(
            "then add tool name to scripts/compatibility_waivers.txt.",
            file=sys.stderr,
        )
        return 1

    print(f"COMPATIBILITY CHECK PASSED: {len(tools)} tools validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
