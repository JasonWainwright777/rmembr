---
title: Must Follow Change Checklist
priority: must-follow
---

# Must Follow Change Checklist

Use this before changing contracts, gateway/index behavior, policy, or retrieval.

## 1) Tool Contract Safety

- Keep the canonical 9-tool surface stable unless explicitly versioning a breaking change.
- Update `docs/contracts/gateway-mcp-tools.md` and `mcp_tools.py` together.
- Preserve required fields and validation bounds unless compatibility policy is applied.
- If deprecating/renaming, apply the "2 releases or 6 months" compatibility window and deprecation header behavior.

## 2) Required Test Gates

Run at minimum:

- `python tests/contracts/validate_tool_schemas.py`
- `python -m pytest tests/contracts/test_negative_payloads.py`
- `python -m pytest tests/contracts/test_deprecation_warnings.py`
- `python -m pytest tests/mcp/test_mcp_transport_gating.py`

For performance-sensitive or bundle changes also run:

- `python -m pytest tests/mcp/test_slo_validation.py`

## 3) Policy and Auth Safety

- Respect deny-by-default posture.
- Keep `reader` vs `writer` tool permissions intentional.
- Preserve persona classification filters:
  - `human`/`agent`: `public`, `internal`
  - `external`: `public`
- Do not weaken internal token enforcement on non-health endpoints.

## 4) Provider and Ingest Safety

- Maintain `.ai/memory/manifest.yaml` expectations.
- Keep provider provenance fields (`provider_name`, `external_id`) intact.
- If touching GitHub provider, preserve cache semantics and migration compatibility.

## 5) SLO/Observability Safety

- Keep latency metric names/labels stable (`mcp_tool_call_duration_seconds`, `cache_state`).
- Update dashboards/alerts when metric semantics change.
- Re-baseline SLO docs only with evidence from validation runs.

## 6) Documentation Sync Rule

If behavior changes in code, update related `.ai/memory` + `docs/` in the same PR.

Minimum sync targets for common changes:

- contract/tool changes: `contract-spec.md`, `docs/contracts/gateway-mcp-tools.md`
- policy/auth changes: `policy-and-authz.md`, `security.md`, ADR if architectural
- operational/SLO changes: `slo-observability.md`, `docs/contracts/slo-targets.md`, monitoring artifacts
- client/transport changes: `mcp-client-integration.md`, integration guides

## 7) Default Drift Watchlist

Keep these aligned across code, compose/env, and docs:

- `MCP_ENABLED`
- `MCP_STDIO_ENABLED`
- `GATEWAY_DEFAULT_K`
- `GATEWAY_MAX_BUNDLE_CHARS`
- `BUNDLE_CACHE_TTL_SECONDS`
