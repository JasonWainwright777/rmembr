# SLO Targets

**Version:** v1.0.0
**Status:** Instrumented (Phase 6)
**Last Updated:** 2026-03-05

---

## Status: Instrumented

These targets are now instrumented via Prometheus metrics (`mcp_tool_call_duration_seconds` histogram with `cache_state` label). Validation tests in `tests/mcp/test_slo_validation.py` capture p50/p95 latency by warm/cold cache state and assert against these thresholds. Grafana dashboard (`monitoring/dashboards/gateway-overview.json`) visualizes latency percentiles split by cache state with SLO threshold annotations.

**Metrics module:** `mcp-memory-local/services/shared/src/metrics.py`
**Dashboard:** `monitoring/dashboards/gateway-overview.json`
**Alert rules:** `monitoring/alerts/gateway-alerts.yaml`

**Re-evaluation trigger:** SLO validation test failures indicating thresholds need adjustment based on empirical measurement.

---

## Tool: `search_repo_memory`

Semantic search over indexed memory chunks.

### Latency Targets

| Metric | Warm Cache | Cold Start |
|--------|-----------|------------|
| p50 | 150 ms | 500 ms |
| p95 | 400 ms | 1500 ms |

**Warm cache** = Postgres connection pool established, HNSW index loaded into memory, embedding model warm in Ollama.

**Cold start** = First query after service startup. Includes connection pool creation, HNSW index load, and first embedding API call to Ollama.

### Measurement Methodology

- Latency measured from Gateway proxy receipt of request to response send (wall-clock, server-side)
- Embedding generation time (Ollama API call) is included in the measurement
- Network latency between client and Gateway is excluded
- Measurements recorded via `TimedOperation` structured logging

---

## Tool: `get_context_bundle`

Context bundle assembly (orchestrates Index + Standards).

### Latency Targets

| Metric | Warm Cache (bundle cache hit) | Warm Cache (bundle cache miss) | Cold Start |
|--------|-------------------------------|-------------------------------|------------|
| p50 | 10 ms | 500 ms | 2000 ms |
| p95 | 50 ms | 1200 ms | 4000 ms |

**Bundle cache hit** = Bundle found in `bundle_cache` table and not expired (TTL: 300s default).

**Bundle cache miss** = Requires Index search + Standards fetch + classification filtering + budget trimming.

**Cold start** = All downstream services (Index, Standards, Postgres) starting from cold.

### Measurement Methodology

- Same server-side wall-clock measurement as `search_repo_memory`
- Includes all internal service calls (Index `resolve_context`, Standards `list_standards` + `get_standard`)
- Bundle cache lookups are included in the measurement
- `cached: true/false` in response indicates whether cache was used

---

## Timeout Policy

| Operation | Timeout |
|-----------|---------|
| Client -> Gateway (per request) | 30 seconds |
| Gateway -> Index (internal call) | 30 seconds |
| Gateway -> Standards (internal call) | 10 seconds |
| Gateway -> Postgres (query) | 5 seconds |
| Proxy pass-through (CLI access) | 120 seconds |
| Health check (any service) | 5 seconds |

If a downstream service times out, the Gateway returns:
- `502 Bad Gateway` with an error message identifying the failing service
- Partial results are not returned (all-or-nothing for bundle assembly)

---

## Retry Policy

| Scenario | Retry | Details |
|----------|-------|---------|
| Index service 5xx | No | Fail fast. Client may retry at their discretion. |
| Standards service 5xx | No | Fail fast. Bundle returned without standards content is not supported. |
| Postgres connection error | No (at request level) | Connection pool handles reconnection transparently. If pool is exhausted, request fails immediately. |
| Embedding service (Ollama) timeout | No | Fail fast with clear error message. |

**Rationale:** At current scale (single-tenant, local/dev), retries add latency without meaningful resilience improvement. Retry logic will be re-evaluated for Prod deployment.

---

## Availability Target

| Environment | Target | Measurement |
|-------------|--------|-------------|
| Local | N/A | Not measured |
| Dev | 95% (during business hours) | Uptime of Gateway `/health` returning `healthy` |
| Prod | 99.5% | Uptime of Gateway `/health` returning `healthy` or `degraded` |

**Degraded mode:** Gateway continues to serve if Postgres is reachable but Index or Standards are down. In degraded mode:
- `search_repo_memory` returns `502` (Index unavailable)
- `get_context_bundle` returns `502` (Index unavailable)
- `validate_pack` returns `502` (Index unavailable)
- `list_standards` / `get_standard` returns `502` (Standards unavailable)
- Health endpoint reports `"status": "degraded"` with per-dependency status

---

## Size Budgets

| Parameter | Default | Configurable Via |
|-----------|---------|-----------------|
| Max bundle size | 40,000 characters | `GATEWAY_MAX_BUNDLE_CHARS` env var |
| Default result count (search) | 8 | Request parameter `k` |
| Default result count (bundle) | 12 | `GATEWAY_DEFAULT_K` env var |
| Max result count | 100 | Validation constraint on `k` |
| Bundle cache TTL | 300 seconds | `BUNDLE_CACHE_TTL_SECONDS` env var |
| Standards per bundle | 5 (max) | Hardcoded in Gateway (configurable in Phase 1) |
