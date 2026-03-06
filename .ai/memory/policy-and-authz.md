---
title: Policy and Authorization
priority: must-follow
---

# Policy and Authorization

Primary references:

- `mcp-memory-local/policy/default_policy.json`
- `mcp-memory-local/services/gateway/src/policy/`
- `docs/contracts/adr-001-transport-auth-tenancy.md`

## Core Model

- deny-by-default authorization
- role-based tool allowlists
- persona-to-classification visibility mapping
- request budgets and tool timeout policy

## Default Role and Tool Access

Default role: `reader`

`reader` allowed tools:

- `search_repo_memory`
- `get_context_bundle`
- `explain_context_bundle`
- `validate_pack`
- `list_standards`
- `get_standard`
- `get_schema`

`writer` allowed tools:

- `index_repo`
- `index_all`

## Persona Classification Mapping

- `human` -> `public`, `internal`
- `agent` -> `public`, `internal`
- `external` -> `public`

This governs which chunks are eligible for bundle output.

## Budget Policy Defaults

- `max_bundle_chars`: 40000
- `max_sources`: 50
- `default_k`: 12
- `cache_ttl_seconds`: 300
- per-tool timeout values defined in policy JSON

## Auth Boundaries

- Index/Standards require `X-Internal-Token` for non-health endpoints.
- Gateway injects internal token for service-to-service calls.
- ADR documents target auth posture across Local/Dev/Test/Prod.
