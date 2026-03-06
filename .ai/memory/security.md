---
title: Security and Access Control
priority: must-follow
---

# Security and Access Control

## Internal Service Authentication

Index and Standards are protected by a shared secret:

- Header: `X-Internal-Token: <INTERNAL_SERVICE_TOKEN>`
- Enforced for all endpoints except `GET /health`
- Implemented in `mcp-memory-local/services/shared/src/auth.py`

The Gateway injects `X-Internal-Token` and propagates/creates `X-Request-ID` for internal calls.

## Persona-Based Classification Filtering (Gateway)

Gateway filters chunks included in bundles by persona:

- `human`: allows `public`, `internal`
- `agent`: allows `public`, `internal`
- `external`: allows `public` only

This mapping is defined in the policy system (`services/gateway/src/policy/types.py` via `PolicyLoader`), with defaults in `policy/default_policy.json`.

## Input Validation (Path Traversal Defense)

Tool inputs are validated in `mcp-memory-local/services/shared/src/validation/`:

- `repo` rejects `..` and path separators to prevent filesystem traversal
- `query` max length is 2000 chars
- `k` is limited to 1..100
- `filters` are allowlisted by key: `source_kind`, `classification`, `heading`, `path`

