---
title: SLO and Observability
---

# SLO and Observability

Primary references:

- `docs/contracts/slo-targets.md`
- `monitoring/dashboards/gateway-overview.json`
- `monitoring/alerts/gateway-alerts.yaml`
- `mcp-memory-local/services/shared/src/metrics.py`

## Latency SLOs

`search_repo_memory`:

- warm p50 <= 150 ms
- warm p95 <= 400 ms
- cold p50 <= 500 ms
- cold p95 <= 1500 ms

`get_context_bundle`:

- warm cache hit p50 <= 10 ms
- warm cache hit p95 <= 50 ms
- warm miss p50 <= 500 ms
- warm miss p95 <= 1200 ms
- cold p50 <= 2000 ms
- cold p95 <= 4000 ms

## Metrics To Know

- `mcp_tool_call_duration_seconds` (histogram, labels include `tool`, `cache_state`)
- `mcp_tool_call_total`
- `mcp_tool_call_errors_total`
- `mcp_dependency_health`
- `mcp_dependency_health_last_probe_timestamp`

## Alert Expectations

Alert rules include p95 thresholds for key tools and dependency-down scenarios.

Typical degraded behaviors:

- Gateway `/health` may report `degraded` if dependencies fail.
- Tool calls dependent on down services return `502`.

## Quality Gate

`tests/mcp/test_slo_validation.py` encodes measured latency checks against the documented targets.
