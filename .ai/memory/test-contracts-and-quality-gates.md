---
title: Test Contracts and Quality Gates
priority: must-follow
---

# Test Contracts and Quality Gates

Primary references:

- `tests/contracts/validate_tool_schemas.py`
- `tests/contracts/test_negative_payloads.py`
- `tests/contracts/test_deprecation_warnings.py`
- `tests/mcp/test_mcp_transport_gating.py`
- `tests/mcp/test_slo_validation.py`

## Contract Validation Gate

`validate_tool_schemas.py` checks request/response contract alignment for core tools.

Treat this as a required gate for tool schema changes.

## Negative Payload Gate

`test_negative_payloads.py` verifies schema rejection behavior:

- missing required fields
- wrong types
- invalid bounds/enums
- disallowed additional properties

## Compatibility/Deprecation Gate

`test_deprecation_warnings.py` validates that compatibility policy language remains present in contract artifacts (window, header, telemetry expectations).

## Transport Gating Gate

`test_mcp_transport_gating.py` enforces environment flags for MCP server and stdio behavior.

## Latency/SLO Gate

`test_slo_validation.py` validates measured latencies against `docs/contracts/slo-targets.md`.

If these tests fail, either:

- runtime performance regressed, or
- SLO targets/docs require explicit re-baselining.
