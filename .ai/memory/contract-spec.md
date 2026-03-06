---
title: Contract Spec
priority: must-follow
---

# Contract Spec (Gateway Tools + Compatibility)

Canonical references:

- `docs/contracts/gateway-mcp-tools.md`
- `docs/contracts/adr-001-transport-auth-tenancy.md`
- `mcp-memory-local/services/gateway/src/mcp_tools.py`

## Canonical Tool Set

Gateway MCP surface is 9 tools:

- `search_repo_memory`
- `get_context_bundle`
- `explain_context_bundle`
- `validate_pack`
- `index_repo`
- `index_all`
- `list_standards`
- `get_standard`
- `get_schema`

`mcp_tools.py` is the executable schema registration point. Contract docs are normative for API behavior and versioning policy.

## Request Validation Rules (High Impact)

- Required fields:
  - `search_repo_memory`: `repo`, `query`
  - `get_context_bundle`: `repo`, `task`
  - `explain_context_bundle`: `bundle_id`
  - `validate_pack`: `repo`
  - `index_repo`: `repo`
  - `get_standard`: `id`
  - `get_schema`: `id`
- `k` constrained to `1..100`.
- `persona` constrained to `human | agent | external`.
- Unknown top-level fields are rejected (`additionalProperties: false` on tool schemas).

## Compatibility and Deprecation Policy

From ADR/contract:

- Breaking changes require compatibility window.
- Window is "2 releases or 6 months", whichever is longer.
- Deprecated aliases must emit `X-Deprecated-Tool`.
- Deprecation alias usage should emit telemetry.

Non-breaking examples:

- adding optional request fields
- adding response fields
- adding new tools

Breaking examples:

- removing/renaming a tool
- removing required fields
- tightening validation constraints

## Implementation Notes

- Gateway executes local handlers for:
  - `get_context_bundle`
  - `explain_context_bundle`
  - `validate_pack`
- Gateway proxies:
  - Index: `search_repo_memory`, `index_repo`, `index_all`
  - Standards: `list_standards`, `get_standard`, `get_schema`

When contract docs and implementation diverge, update docs and tests in the same change.
