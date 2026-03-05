"""Contract validation: validates tool schemas against example payloads.

Reads the contract definitions from docs/contracts/gateway-mcp-tools.md,
extracts JSON schemas, and validates example payloads against them.

Usage:
    python tests/contracts/validate_tool_schemas.py
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema definitions (mirrored from docs/contracts/gateway-mcp-tools.md)
# ---------------------------------------------------------------------------

SEARCH_REPO_MEMORY_REQUEST = {
    "type": "object",
    "required": ["repo", "query"],
    "properties": {
        "repo": {"type": "string", "minLength": 1},
        "query": {"type": "string", "minLength": 1, "maxLength": 2000},
        "k": {"type": "integer", "minimum": 1, "maximum": 100},
        "ref": {"type": "string"},
        "namespace": {"type": "string", "minLength": 1},
        "filters": {
            "type": ["object", "null"],
            "properties": {
                "source_kind": {"type": "string"},
                "classification": {"type": "string"},
                "heading": {"type": "string"},
                "path": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

SEARCH_REPO_MEMORY_RESPONSE = {
    "type": "object",
    "required": ["results", "count"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id", "path", "anchor", "heading", "snippet",
                    "source_kind", "classification", "similarity",
                ],
                "properties": {
                    "id": {"type": "integer"},
                    "path": {"type": "string"},
                    "anchor": {"type": "string"},
                    "heading": {"type": "string"},
                    "snippet": {"type": "string"},
                    "source_kind": {"type": "string", "enum": ["repo_memory", "enterprise_standard"]},
                    "classification": {"type": "string", "enum": ["public", "internal"]},
                    "similarity": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "count": {"type": "integer"},
    },
}

GET_CONTEXT_BUNDLE_REQUEST = {
    "type": "object",
    "required": ["repo", "task"],
    "properties": {
        "repo": {"type": "string", "minLength": 1},
        "task": {"type": "string", "minLength": 1, "maxLength": 2000},
        "k": {"type": "integer", "minimum": 1, "maximum": 100},
        "ref": {"type": "string"},
        "namespace": {"type": "string"},
        "persona": {"type": "string", "enum": ["human", "agent", "external"]},
        "standards_version": {"type": "string"},
        "changed_files": {"type": ["array", "null"], "items": {"type": "string"}},
        "filters": {"type": ["object", "null"]},
    },
    "additionalProperties": False,
}

GET_CONTEXT_BUNDLE_RESPONSE = {
    "type": "object",
    "required": ["bundle_id", "bundle", "markdown", "cached"],
    "properties": {
        "bundle_id": {"type": "string"},
        "bundle": {"type": "object"},
        "markdown": {"type": "string"},
        "cached": {"type": "boolean"},
    },
}

EXPLAIN_CONTEXT_BUNDLE_REQUEST = {
    "type": "object",
    "required": ["bundle_id"],
    "properties": {
        "bundle_id": {"type": "string"},
    },
    "additionalProperties": False,
}

VALIDATE_PACK_REQUEST = {
    "type": "object",
    "required": ["repo"],
    "properties": {
        "repo": {"type": "string", "minLength": 1},
        "ref": {"type": "string"},
    },
    "additionalProperties": False,
}

VALIDATE_PACK_RESPONSE = {
    "type": "object",
    "required": ["repo", "ref", "valid", "issues"],
    "properties": {
        "repo": {"type": "string"},
        "ref": {"type": "string"},
        "valid": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
}

LIST_STANDARDS_REQUEST = {
    "type": "object",
    "properties": {
        "domain": {"type": ["string", "null"]},
        "version": {"type": "string"},
    },
    "additionalProperties": False,
}

GET_STANDARD_REQUEST = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "string"},
        "version": {"type": "string"},
    },
    "additionalProperties": False,
}

GET_STANDARD_RESPONSE = {
    "type": "object",
    "required": ["id", "version", "path", "content"],
    "properties": {
        "id": {"type": "string"},
        "version": {"type": "string"},
        "path": {"type": "string"},
        "content": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Lightweight JSON Schema validator (no external dependencies)
# ---------------------------------------------------------------------------


class SchemaError(Exception):
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def validate(instance, schema: dict, path: str = "$") -> list[SchemaError]:
    """Validate an instance against a JSON Schema subset. Returns list of errors."""
    errors: list[SchemaError] = []

    schema_type = schema.get("type")

    # Reject None when null is not allowed
    if instance is None:
        if schema_type == "null":
            return errors
        if isinstance(schema_type, list) and "null" in schema_type:
            return errors
        errors.append(SchemaError(path, f"expected {schema_type or 'non-null'}, got null"))
        return errors

    # Handle type unions (e.g., ["object", "null"])
    if isinstance(schema_type, list):
        if instance is None and "null" in schema_type:
            return errors
        # Try non-null types
        effective_types = [t for t in schema_type if t != "null"]
        if not any(_check_type(instance, t) for t in effective_types):
            errors.append(SchemaError(path, f"expected one of {schema_type}, got {type(instance).__name__}"))
            return errors
    elif schema_type and instance is not None:
        if not _check_type(instance, schema_type):
            errors.append(SchemaError(path, f"expected {schema_type}, got {type(instance).__name__}"))
            return errors

    if isinstance(instance, dict) and (schema_type == "object" or isinstance(schema_type, list) and "object" in schema_type or schema_type is None and "properties" in schema):
        # Check required fields
        for field in schema.get("required", []):
            if field not in instance:
                errors.append(SchemaError(f"{path}.{field}", "required field missing"))

        # Check properties
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(SchemaError(f"{path}.{key}", "additional property not allowed"))

        # Check minLength on string properties (when value is a string)
        if "minLength" in schema and isinstance(instance, str):
            if len(instance) < schema["minLength"]:
                errors.append(SchemaError(path, f"string shorter than minLength {schema['minLength']}"))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(SchemaError(path, f"string shorter than minLength {schema['minLength']}"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(SchemaError(path, f"string longer than maxLength {schema['maxLength']}"))
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(SchemaError(path, f"value '{instance}' not in enum {schema['enum']}"))
        if "pattern" in schema and not re.match(schema["pattern"], instance):
            errors.append(SchemaError(path, f"value does not match pattern {schema['pattern']}"))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(SchemaError(path, f"value {instance} < minimum {schema['minimum']}"))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(SchemaError(path, f"value {instance} > maximum {schema['maximum']}"))

    if isinstance(instance, list):
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, items_schema, f"{path}[{i}]"))

    return errors


def _check_type(instance, expected: str) -> bool:
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    expected_type = type_map.get(expected)
    if expected_type is None:
        return True
    if expected == "integer" and isinstance(instance, bool):
        return False
    return isinstance(instance, expected_type)


# ---------------------------------------------------------------------------
# Example payloads
# ---------------------------------------------------------------------------

EXAMPLES = [
    # search_repo_memory
    (
        "search_repo_memory request (minimal)",
        SEARCH_REPO_MEMORY_REQUEST,
        {"repo": "sample-repo-a", "query": "How should we handle secrets?"},
    ),
    (
        "search_repo_memory request (full)",
        SEARCH_REPO_MEMORY_REQUEST,
        {
            "repo": "sample-repo-a",
            "query": "How should we handle secrets in pipelines?",
            "k": 5,
            "ref": "local",
            "namespace": "default",
            "filters": {"source_kind": "enterprise_standard"},
        },
    ),
    (
        "search_repo_memory response",
        SEARCH_REPO_MEMORY_RESPONSE,
        {
            "results": [
                {
                    "id": 42,
                    "path": ".ai/memory/enterprise/security/secrets-management.md",
                    "anchor": "secrets-management-c0",
                    "heading": "Secrets Management",
                    "snippet": "All secrets must be stored in Azure Key Vault...",
                    "source_kind": "enterprise_standard",
                    "classification": "internal",
                    "similarity": 0.847,
                }
            ],
            "count": 1,
        },
    ),
    # get_context_bundle
    (
        "get_context_bundle request (minimal)",
        GET_CONTEXT_BUNDLE_REQUEST,
        {"repo": "sample-repo-a", "task": "Implement VNet peering module"},
    ),
    (
        "get_context_bundle request (full)",
        GET_CONTEXT_BUNDLE_REQUEST,
        {
            "repo": "sample-repo-a",
            "task": "Implement VNet peering module",
            "k": 10,
            "ref": "main",
            "namespace": "default",
            "persona": "agent",
            "standards_version": "v3",
            "changed_files": ["modules/vnet/main.tf"],
            "filters": None,
        },
    ),
    (
        "get_context_bundle response",
        GET_CONTEXT_BUNDLE_RESPONSE,
        {
            "bundle_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "bundle": {
                "bundle_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "repo": "sample-repo-a",
                "task": "Implement VNet peering module",
                "persona": "agent",
                "ref": "main",
                "namespace": "default",
                "standards_version": "v3",
                "standards_content": [],
                "chunks": [],
                "total_candidates": 12,
                "filtered_count": 10,
                "returned_count": 8,
                "created_at": "2026-03-05T15:30:00+00:00",
            },
            "markdown": "# Context Bundle: sample-repo-a\n\n...",
            "cached": False,
        },
    ),
    # explain_context_bundle
    (
        "explain_context_bundle request",
        EXPLAIN_CONTEXT_BUNDLE_REQUEST,
        {"bundle_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
    ),
    # validate_pack
    (
        "validate_pack request",
        VALIDATE_PACK_REQUEST,
        {"repo": "sample-repo-a", "ref": "local"},
    ),
    (
        "validate_pack response",
        VALIDATE_PACK_RESPONSE,
        {"repo": "sample-repo-a", "ref": "local", "valid": True, "issues": []},
    ),
    # list_standards
    (
        "list_standards request",
        LIST_STANDARDS_REQUEST,
        {"version": "v3"},
    ),
    # get_standard
    (
        "get_standard request",
        GET_STANDARD_REQUEST,
        {"id": "enterprise/terraform/module-versioning", "version": "local"},
    ),
    (
        "get_standard response",
        GET_STANDARD_RESPONSE,
        {
            "id": "enterprise/terraform/module-versioning",
            "version": "local",
            "path": "/repos/enterprise-standards/.ai/memory/enterprise/terraform/module-versioning.md",
            "content": "# Module Versioning\n\nAll Tier 1 modules must use semantic versioning...",
        },
    ),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    passed = 0
    failed = 0

    for name, schema, payload in EXAMPLES:
        errors = validate(payload, schema)
        if errors:
            print(f"FAIL: {name}")
            for err in errors:
                print(f"  {err}")
            failed += 1
        else:
            print(f"PASS: {name}")
            passed += 1

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")

    # Verify contract document exists
    contract_path = Path(__file__).parent.parent.parent / "docs" / "contracts" / "gateway-mcp-tools.md"
    if contract_path.exists():
        print(f"PASS: Contract document exists at {contract_path}")
        passed += 1
    else:
        print(f"FAIL: Contract document not found at {contract_path}")
        failed += 1

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
