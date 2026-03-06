# CG_MCP_v16 -- Phase 6: Operational Readiness

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md
prior_cycle: CG_MCP_v9 (Phase 5 -- VS Code / generic MCP client interoperability, CLOSED)
prior_version: CG_MCP_v15
implementation_repo: C:\gh_src\rmembr

---

## Audit Resolution Map

### v15 audit finding (AUDIT_CG_MCP_v15.md)

| # | Required Change (AUDIT_CG_MCP_v15.md) | How Addressed | Where in v15 |
|---|----------------------------------------|---------------|--------------|
| 1 | Reconcile behavioral-mode definitions to a single model: explicitly state whether `/metrics` exists in standard mode, and align Section A implementation scope, Section C closure artifacts, and Section D sensitivity/spec-check language to that same definition. | Reconciled all behavioral-mode definitions to a two-tier model: (a) `/metrics` endpoint and dependency health probe exist on the gateway whenever `prometheus_client` is installed -- they are part of the gateway server, not gated by `--profile monitoring`; (b) `--profile monitoring` controls only whether Prometheus and Grafana containers run to consume those metrics. Updated Spec Completeness Gate behavioral modes (standard mode now states "/metrics endpoint active, health probe running" when prometheus_client installed), Section A "Minimal safe change strategy" item 1 to clarify that /metrics is always present, Section C closure artifact #2 to remove mode ambiguity, and Section D sensitivity item 2 to align. Removed the incorrect claim that standard mode has "no /metrics endpoint, no health probe." | Spec Completeness Gate behavioral modes (line 745: "standard ... no /metrics endpoint, no health probe"), Section A item 1 (line 493: "Additive-only for monitoring stack" implied /metrics was monitoring-only), Section C closure artifact #2 (line 602), Section D item 2 (line 721). |

### v14 audit finding (carried from v15 Audit Resolution Map)

| # | Required Change (AUDIT_CG_MCP_v14.md) | How Addressed | Where in v14 |
|---|----------------------------------------|---------------|--------------|
| 1 | `/metrics` exposure model is internally contradictory: plan states compose mode is "not exposed to host network" and port is NOT published, but also states gateway port 8080 is already exposed for HTTP/MCP and `/metrics` inherits that exposure. Reconcile to one unambiguous model. | Rewrote "Binding model by runtime mode" section and "Security invariant" paragraph to eliminate the contradiction. The new model explicitly states: (a) in compose mode, gateway port 8080 IS published to host via `ports: "8080:8080"` in docker-compose.yml for MCP client access -- this is existing behavior, not introduced by this plan; (b) `/metrics` is a sub-path on the same port and is therefore reachable from host when the port is published; (c) the monitoring profile does NOT add any additional port exposure -- Prometheus reaches `/metrics` via Docker internal network, not via the published host port; (d) `/metrics` exposes only operational counters/histograms/gauges with static enum labels -- no secrets or user data. Updated Risk Surface row 2, Auditor Sensitivity items 1 and 9, and deployment steps to match the reconciled model. Removed all claims that compose-mode `/metrics` is "not exposed to host network" since it inherits the existing 8080 host publication. | v14 "Binding model by runtime mode" section, "Security invariant" paragraph, Risk Surface row 2, Auditor Sensitivity items 1 and 9, deployment step 4. |
| 2 | Closure artifacts only require static rule linting (`promtool check rules`). Add a closure artifact demonstrating end-to-end alert trigger behavior: induce at least one latency breach and one dependency-down condition, capture fired alert evidence, and show actionable message content. | Added closure artifact #12: "Alert trigger drill" that requires: (a) inducing a dependency-down by stopping the ollama container, waiting for probe + alert evaluation, and capturing `DependencyDown` alert in firing state with actionable annotation; (b) inducing a latency breach by injecting artificial delay into a tool call, waiting for alert evaluation, and capturing `SearchLatencyP95High` or equivalent in firing state with actionable annotation. Evidence must include Prometheus `/api/v1/alerts` output showing alert name, state=firing, and annotations.summary text. Added corresponding verification commands in "Exact commands to produce closure artifacts" section. Updated Auditor Sensitivity to note the drill requirement. | v14 closure artifact #4 was static-only. New artifact #12 added after existing #11. |

### v13 audit finding (carried from v15 Audit Resolution Map)

| # | Required Change (AUDIT_CG_MCP_v13.md) | How Addressed | Where in v13 |
|---|----------------------------------------|---------------|--------------|
| 1 | `governance/NOW.md` CURRENT FOCUS is internally inconsistent: `Phase: CG_MCP_v13` but `Active cycle: CG_MCP_v10`. Reconcile to one consistent active cycle/version. | `Active cycle:` line in NOW.md changed from `CG_MCP_v10` to `CG_MCP` (the cycle name without version suffix). The `Phase:` line already carries the version (`CG_MCP_v14`). Prior versions (v12, v13) claimed to fix this but left `Active cycle: CG_MCP_v10` unchanged. This revision actually edits NOW.md to remove the stale version suffix. No plan content changes required -- auditor did not review plan body due to pre-audit gate failure. | NOW.md line 86 (`Active cycle: CG_MCP_v10`). |

### v12 audit finding (carried from v15 Audit Resolution Map)

| # | Required Change (AUDIT_CG_MCP_v12.md) | How Addressed | Where in v12 |
|---|----------------------------------------|---------------|--------------|
| 1 | `governance/NOW.md` CURRENT FOCUS is internally inconsistent: `Phase: CG_MCP_v12` but `Active cycle: CG_MCP_v10`. Reconcile to a single, consistent active cycle designation before substantive audit proceeds. | Same root cause as v13 finding #1. Resolved by changing `Active cycle:` to `CG_MCP` (no version suffix). See v13 resolution above. | NOW.md `Active cycle` line. |

### v11 audit findings (carried from v15 Audit Resolution Map)

| # | Required Change (AUDIT_CG_MCP_v11.md) | How Addressed | Where in v11 |
|---|----------------------------------------|---------------|--------------|
| 1 | Replace dependency-health freshness evidence with an inspectable signal. `prometheus_client` does not emit sample timestamps in text exposition; closure artifact #11's "updated timestamps" method is unreliable. | Added `mcp_dependency_health_last_probe_timestamp` Gauge (unix epoch, per dependency) to metrics module design. Updated `update_dependency_health()` to set this gauge after each probe cycle. Updated closure artifact #11 to verify freshness by reading the `_last_probe_timestamp` gauge value and comparing to current time (delta <= 45s), instead of relying on Prometheus sample timestamps. Updated alerting rules to add `DependencyProbeStale` alert based on this gauge. | v11 metrics module design (no timestamp gauge), closure artifact #11 (relied on "updated timestamps" from `/metrics`), alerting rules (no staleness alert). |
| 2 | Resolve `/metrics` reachability ambiguity. Plan states localhost-only binding while also requiring Prometheus in Docker to scrape over the Docker network -- internally inconsistent. | Added explicit "Binding model by runtime mode" subsection specifying: (a) host-local dev: bind `127.0.0.1`, Prometheus runs on host or accesses via `host.docker.internal`; (b) containerized compose: bind `0.0.0.0` inside container, Docker network provides isolation -- not exposed to host network. Updated deployment steps, risk table row 2, closure artifact #2, and Auditor Sensitivity item 1 to reference the binding model. Removed contradictory "localhost only" phrasing where it conflicted with Docker mode. | v11 metrics module design ("bound to localhost only"), deployment step 4, risk table row 2, closure artifact #2, Auditor Sensitivity item 1. |

### Advisory items also addressed (carried from v15)

| Advisory | Resolution |
|----------|------------|
| `/metrics` exposure boundary | Fully resolved as v11 Required Change #2 above; further refined in v14 Required Change #1 above. |
| Monitoring activation wording inconsistency | All references normalized to `docker compose --profile monitoring`. |

---

## Scope

This cycle covers **Phase 6** from the source proposal: Operational readiness. The source proposal defines five tasks:

1. Add dashboards/alerts for MCP error rate, latency percentiles, dependency health.
2. Define SLOs and runbook for common failures (provider auth fail, embedding outage, DB saturation).
3. Add migration/version strategy for tool schemas and provider contracts.
4. Split SLO dashboards/reports by warm-cache vs cold-start/cold-cache behavior.
5. Enforce compatibility policy checks in release process (2 releases or 6 months minimum support).

### Current state (confirmed via codebase read)

**What already exists and should be preserved:**

- **Structured JSON logging** (`mcp-memory-local/services/shared/src/structured_logging.py`): `JSONFormatter` outputs JSON lines with `timestamp`, `service`, `request_id`, `tool`, `level`, `message`, `duration_ms`. `TimedOperation` context manager logs operation duration. Used by gateway, index, and standards services.
- **Request tracing** (`mcp-memory-local/services/shared/src/structured_logging.py`): `request_id_var` ContextVar propagated via `X-Request-ID` header across all services. Gateway middleware generates or forwards request IDs.
- **Audit logging** (`mcp-memory-local/services/shared/src/audit_log.py`): `AuditLogger.log_tool_call()` with `audit: true` marker, `tool`, `action`, `subject`, `repo`, `provenance_refs`, `correlation_id`, `duration_ms`.
- **Health checks** (`mcp-memory-local/services/gateway/src/server.py`): `GET /health` returns `{"status": "healthy"|"degraded", "index": bool, "standards": bool, "postgres": bool}`. Index and standards services have similar health endpoints.
- **Docker health checks** (`mcp-memory-local/docker-compose.yml`): Postgres (`pg_isready`), Ollama (`/api/version`), services via `depends_on` conditions.
- **SLO document** (`docs/contracts/slo-targets.md`): Comprehensive v0.1.0 (Provisional/Phase 0) defining p50/p95 targets for warm/cold paths, timeout policy, retry policy, availability targets, size budgets. Marked as provisional -- not yet instrumented or validated.
- **Deprecation tests** (`tests/contracts/test_deprecation_warnings.py`): Validates compatibility window documentation (2 releases or 6 months), `X-Deprecated-Tool` header spec, backward compatibility for old payloads.
- **Contract documents** (`docs/contracts/gateway-mcp-tools.md`, `docs/contracts/adr-001-transport-auth-tenancy.md`): Tool definitions with versioning metadata. ADR defines breaking vs non-breaking changes.
- **Error sanitization** (`mcp-memory-local/services/gateway/src/mcp_errors.py`): Maps exceptions to MCP error codes, strips internal URLs/tokens/paths.
- **Database migrations** (`mcp-memory-local/services/index/src/migrations.py`): Sequential migration array (2 migrations). Runs on startup.
- **Basic troubleshooting** (`.ai/memory/operations-troubleshooting.md`): 3 failure scenarios with checks/fixes (embedding service, auth token, missing directory).
- **Soak test** (`tests/mcp/test_mcp_soak.py`): 15-min repeated MCP invocations for crash/leak detection.

**What does NOT exist yet:**

- No Prometheus metrics endpoints (`/metrics`) on any service.
- No Grafana dashboard definitions.
- No alerting rules or thresholds.
- No formal runbooks (only 3 basic troubleshooting scenarios).
- No SLO instrumentation -- `TimedOperation` logs `duration_ms` to stdout but no histogram/percentile aggregation.
- No warm-cache vs cold-cache split in any measurement.
- No compatibility policy enforcement in release process (tests exist but no CI gate).
- No schema migration rollback mechanism.
- No `X-Deprecated-Tool` header implementation (spec exists in contract docs but not in code).

### Path Integrity Sweep

All implementation file paths referenced in this plan, verified against the rmembr repo layout:

| # | Canonical path (relative to rmembr repo root) | Section(s) referencing | Verified |
|---|-----------------------------------------------|----------------------|----------|
| 1 | `mcp-memory-local/services/shared/src/structured_logging.py` | Current state, Task 1, Task 4 | Yes |
| 2 | `mcp-memory-local/services/shared/src/audit_log.py` | Current state | Yes |
| 3 | `mcp-memory-local/services/gateway/src/server.py` | Current state, Task 1, Task 2a | Yes |
| 4 | `mcp-memory-local/services/gateway/src/mcp_errors.py` | Current state | Yes |
| 5 | `mcp-memory-local/services/gateway/src/mcp_tools.py` | Task 5 | Yes |
| 6 | `mcp-memory-local/services/index/src/server.py` | Current state, Task 1 | Yes |
| 7 | `mcp-memory-local/services/index/src/migrations.py` | Current state, Task 3 | Yes |
| 8 | `mcp-memory-local/services/standards/src/server.py` | Current state | Yes |
| 9 | `mcp-memory-local/docker-compose.yml` | Current state, Task 1 | Yes |
| 10 | `docs/contracts/slo-targets.md` | Current state, Task 2, Task 4 | Yes |
| 11 | `docs/contracts/gateway-mcp-tools.md` | Current state, Task 3, Task 5 | Yes |
| 12 | `docs/contracts/adr-001-transport-auth-tenancy.md` | Current state, Task 5 | Yes |
| 13 | `tests/contracts/test_deprecation_warnings.py` | Current state, Task 5 | Yes |
| 14 | `tests/mcp/test_mcp_soak.py` | Current state | Yes |
| 15 | `.ai/memory/operations-troubleshooting.md` | Current state, Task 2 | Yes |
| 16 | `docs/TUNING.md` | Task 2 | Yes |
| 17 | `docs/CONFIGURATION.md` | Task 1 | Yes |

**Path convention:** Service source under `mcp-memory-local/services/`. Tests, docs, and configs at repo root level (`tests/`, `docs/`). Docker-compose and scripts under `mcp-memory-local/`. This convention is used consistently throughout this plan.

---

## SECTION A -- Execution Plan

### Micro-task list

| # | Task | Source proposal ref | Time est. | Risk | Validation artifact |
|---|------|---------------------|-----------|------|---------------------|
| 1 | Add Prometheus metrics to gateway service | Task 1 | 60 min | Medium | `/metrics` endpoint returns histograms for MCP tool latency and request counts |
| 2 | Create operational runbook for common failures | Task 2 | 45 min | Low | Runbook doc covers all 6 failure scenarios with decision trees |
| 2a | **[NEW v10] Add periodic dependency health probe to gateway** | Task 1 | 30 min | Medium | `mcp_dependency_health` gauge updated every 30s; closure evidence shows non-stale values for all 4 dependencies |
| 3 | Document migration/version strategy for tool schemas | Task 3 | 30 min | Low | Strategy doc exists with rollback procedure and version compatibility rules |
| 4 | Add SLO validation test with warm/cold split | Task 1, 4 | 45 min | Medium | Test captures latency by cache state and asserts against SLO targets |
| 5 | Add compatibility policy CI gate **(fail-closed, mandatory in release process)** | Task 5 | 45 min | Medium | CI gate script exits non-zero on policy violation; release blocked until resolved or Board-approved waiver granted |
| 6 | Create Grafana dashboard definition (JSON) | Task 1, 4 | 45 min | Low | Dashboard JSON importable, shows latency percentiles split by cache state |
| 7 | Add alerting rules definition | Task 1 | 30 min | Low | Alert rules file defines thresholds for SLO breaches and dependency failures |

### Files to create (in rmembr repo)

| # | Path | Purpose |
|---|------|---------|
| 1 | `mcp-memory-local/services/shared/src/metrics.py` | Prometheus metrics module: histograms for tool latency (with cache_state label), counters for requests/errors, dependency health gauge, **last-probe-timestamp gauge**, **`update_dependency_health()` probe function** |
| 2 | `docs/operations/runbook.md` | Operational runbook: 6+ failure scenarios with triage decision trees, recovery steps, escalation |
| 3 | `docs/operations/schema-migration-strategy.md` | Tool schema migration/version strategy: breaking vs non-breaking changes, rollback procedure, compatibility window enforcement |
| 4 | `tests/mcp/test_slo_validation.py` | SLO validation test: captures p50/p95 latency for warm and cold paths, asserts against `slo-targets.md` thresholds |
| 5 | `scripts/check_compatibility.py` | CI gate script **(fail-closed)**: validates tool schemas have version metadata, deprecated tools have replacement, compatibility window not violated. Non-zero exit blocks release. |
| 6 | `monitoring/dashboards/gateway-overview.json` | Grafana dashboard JSON: MCP tool latency (p50/p95) split by warm/cold, error rate, dependency health, request throughput |
| 7 | `monitoring/alerts/gateway-alerts.yaml` | Alerting rules: SLO breach thresholds for latency and error rate, dependency health failures, **probe staleness** |
| 8 | `.github/workflows/release-gate.yml` | CI workflow that runs `check_compatibility.py` as a required check before release |

### Files to modify (in rmembr repo)

| # | Path | Change |
|---|------|--------|
| 1 | `mcp-memory-local/services/gateway/src/server.py` | Add `/metrics` endpoint using shared metrics module. Binding per runtime mode (see binding model below). Add metrics middleware to record tool call latency with `cache_state` label. **Add background task that calls `update_dependency_health()` every 30 seconds.** |
| 2 | `mcp-memory-local/services/shared/src/structured_logging.py` | Extend `TimedOperation` to also record Prometheus histogram observation alongside existing log output. |
| 3 | `mcp-memory-local/docker-compose.yml` | Add Prometheus service (scraping gateway `/metrics` via Docker network). Add optional Grafana service with provisioned dashboard. Both behind `--profile monitoring`. |
| 4 | `docs/contracts/slo-targets.md` | Promote from v0.1.0 Provisional to v1.0.0. Add "Instrumented" status. Add reference to metrics module and dashboard. |
| 5 | `docs/CONFIGURATION.md` | Add "Monitoring" section documenting `--profile monitoring`, Prometheus scrape config, Grafana access. |

### Metrics module design (`metrics.py`)

```python
"""Prometheus metrics for gateway observability.

Exports: tool_call_latency, tool_call_total, tool_call_errors,
         dependency_health, dependency_health_last_probe,
         update_dependency_health, metrics_app (ASGI app for /metrics).
"""
from prometheus_client import Histogram, Counter, Gauge, make_asgi_app
import time

# Tool call latency histogram with cache_state label (warm/cold/miss)
tool_call_latency = Histogram(
    "mcp_tool_call_duration_seconds",
    "MCP tool call latency in seconds",
    labelnames=["tool", "cache_state"],
    buckets=[0.05, 0.1, 0.15, 0.3, 0.5, 0.6, 1.0, 1.2, 1.5, 2.0, 4.0, 10.0],
)

# Request counter by tool and status
tool_call_total = Counter(
    "mcp_tool_call_total",
    "Total MCP tool calls",
    labelnames=["tool", "status"],  # status: success, error, denied
)

# Dependency health gauge (1=healthy, 0=degraded)
dependency_health = Gauge(
    "mcp_dependency_health",
    "Dependency health status",
    labelnames=["dependency"],  # index, standards, postgres, ollama
)

# [NEW v12] Last probe timestamp per dependency (unix epoch seconds)
# Provides an inspectable, objective freshness signal that does not
# rely on Prometheus sample timestamps (which prometheus_client does
# not emit in text exposition format).
dependency_health_last_probe = Gauge(
    "mcp_dependency_health_last_probe_timestamp",
    "Unix epoch timestamp of last health probe per dependency",
    labelnames=["dependency"],  # index, standards, postgres, ollama
)

# ASGI app for /metrics endpoint
metrics_app = make_asgi_app()


async def update_dependency_health() -> None:
    """Probe each dependency and update gauge values.

    Called by gateway background task every 30 seconds.
    Reuses the same health-check logic as GET /health:
      - index: HTTP GET to index service /health
      - standards: HTTP GET to standards service /health
      - postgres: connection pool ping (SELECT 1)
      - ollama: HTTP GET to ollama /api/version

    Each probe has a 5-second timeout. On timeout or error,
    gauge is set to 0 (degraded). On success, gauge is set to 1.

    After probing each dependency, sets
    dependency_health_last_probe.labels(dependency=name)
    to time.time() (unix epoch). This provides an inspectable
    freshness signal readable from /metrics without relying on
    Prometheus sample timestamps.
    """
    ...
```

**Behavioral notes:**
- Histogram buckets aligned to SLO targets from `slo-targets.md` (p50 150-600ms, p95 400-4000ms).
- `cache_state` label enables warm vs cold split in dashboards (source proposal task 4).
- `TimedOperation` extended to accept optional `cache_state` parameter; when metrics module is importable, it records a histogram observation. When `prometheus_client` is not installed, metrics degrade gracefully (no-op).
- **[CHANGED v12] `mcp_dependency_health_last_probe_timestamp` gauge** records `time.time()` after each probe cycle, per dependency. This is the authoritative freshness signal for closure artifact #11 and the `DependencyProbeStale` alert. It does not rely on Prometheus sample timestamps.
- **`update_dependency_health()` is called on a 30-second `asyncio` loop started at gateway startup.** It reuses existing health-check logic from `GET /health` (which already probes index, standards, and postgres). Ollama probe uses the same endpoint checked by Docker health checks (`/api/version`). Each probe has a 5-second timeout; failure sets gauge to 0. After all probes complete, each dependency's `_last_probe_timestamp` gauge is set to the current unix epoch. This ensures `DependencyDown` alerts fire within ~1.5 minutes of actual outage (30s probe interval + 1m alert `for` duration).

### Binding model by runtime mode (`/metrics` endpoint)

**[CHANGED v15]** The `/metrics` endpoint is a sub-path on the gateway's HTTP port (8080). Its reachability is determined by the gateway's existing port exposure, not by any separate metrics-specific binding. This section clarifies the actual exposure model without contradiction.

| Runtime mode | Bind address | Gateway port 8080 host-published? | `/metrics` reachable from host? | Prometheus access path |
|-------------|-------------|-----------------------------------|--------------------------------|----------------------|
| **Host-local dev** (no Docker, or gateway outside compose) | `127.0.0.1` (localhost only) | N/A (process binds directly) | Yes, via `localhost:8080/metrics` | Prometheus on host scrapes `localhost:8080/metrics`. Or Prometheus in Docker uses `host.docker.internal:8080`. |
| **Containerized compose** (gateway inside Docker network) | `0.0.0.0` (all interfaces inside container) | **Yes** -- `docker-compose.yml` publishes `ports: "8080:8080"` for MCP client access. This is existing behavior predating this plan. | **Yes** -- `/metrics` inherits the same host-published port as all other gateway HTTP paths. | Prometheus container scrapes `gateway:8080/metrics` via Docker internal network DNS. Does NOT require the host-published port. |

**Implementation detail:** The bind address is controlled by an environment variable `METRICS_BIND_HOST` (default `127.0.0.1`). In `docker-compose.yml`, the gateway service sets `METRICS_BIND_HOST=0.0.0.0`. In host-local dev, the default `127.0.0.1` applies. This single config point eliminates ambiguity.

**[CHANGED v15] Security posture (reconciled):** In compose mode, `/metrics` is reachable from the host via the published 8080 port -- the same port that already serves MCP/HTTP traffic. This is acceptable because:

1. **No new attack surface:** Port 8080 is already published for MCP client access. `/metrics` does not open any additional port or network path.
2. **No sensitive data in metrics:** Metric labels are limited to static enums (`tool`, `cache_state`, `status`, `dependency`). No secrets, tokens, internal URLs, request content, or user data appear in metric values or labels. Error sanitization in `mcp_errors.py` already strips sensitive data before it reaches any response path.
3. **Consistent with existing exposure:** The gateway's `/health` endpoint is already reachable on the same published port and similarly exposes only operational status information.
4. **Monitoring profile does not widen exposure:** `--profile monitoring` adds Prometheus and Grafana containers that communicate over the Docker internal network. It does NOT add any new published ports for the gateway service.

### Dependency health probe design (Task 2a detail)

The gateway's existing `GET /health` endpoint already checks index, standards, and postgres. The new `update_dependency_health()` function:

1. **Extracts the existing health-check logic** into a reusable async function (or calls the internal health-check handler directly).
2. **Adds ollama probe** (`GET http://ollama:11434/api/version` with 5s timeout) -- consistent with Docker health check in `docker-compose.yml`.
3. **Updates gauge per dependency:** `dependency_health.labels(dependency="index").set(1 if index_ok else 0)` (and similarly for standards, postgres, ollama).
4. **[CHANGED v12] Sets timestamp gauge per dependency:** `dependency_health_last_probe.labels(dependency="index").set(time.time())` after each probe completes. This records the exact unix epoch of the last successful or failed probe attempt.
5. **Runs as `asyncio.create_task`** in gateway startup, looping every 30 seconds. Task is cancelled on shutdown.
6. **Staleness guarantee:** Gauge values are always less than 30 seconds old. The `_last_probe_timestamp` gauge provides an objective, inspectable freshness signal. Prometheus scrape interval (15s default) means at most 45 seconds between probe and Grafana display.

### Runbook structure (`docs/operations/runbook.md`)

```markdown
# Operational Runbook -- Context Gateway

## How to use this runbook
Each scenario follows: Symptoms -> Diagnosis -> Recovery -> Escalation.

## Scenario 1: Embedding service unavailable
Symptoms: search_repo_memory returns 503, logs show "embedding_service_unavailable"
Diagnosis: Check ollama health (curl localhost:11434/api/version)
Recovery: docker compose restart ollama; verify model pulled (ollama list)
Escalation: If ollama container crashes repeatedly, check host GPU/memory

## Scenario 2: Database connection pool exhausted
Symptoms: All endpoints return 503, logs show "pool exhausted" or connection timeout
Diagnosis: Check postgres connections (SELECT count(*) FROM pg_stat_activity)
Recovery: Restart gateway service. If persistent, increase pool_size in config.
Escalation: Check for long-running queries or connection leaks

## Scenario 3: Auth token mismatch (401 errors)
Symptoms: Internal service calls fail with 401
Diagnosis: Verify INTERNAL_SERVICE_TOKEN matches across .env and all services
Recovery: Regenerate token in .env, restart all services
Escalation: n/a (local config issue)

## Scenario 4: Bundle cache thrashing (high latency)
Symptoms: get_context_bundle p95 consistently above SLO (>2000ms warm)
Diagnosis: Check cache hit ratio in metrics (mcp_tool_call_duration_seconds{cache_state})
Recovery: Increase BUNDLE_CACHE_TTL. Check if repo content is changing rapidly.
Escalation: If cache size is the issue, increase BUNDLE_CACHE_MAX_SIZE

## Scenario 5: Policy validation failures
Symptoms: Tool calls denied unexpectedly, audit log shows action="deny"
Diagnosis: Check loaded policy bundle version, review deny reasons in audit log
Recovery: Verify policy bundle matches expected version. Reload via service restart.
Escalation: If policy file is corrupted, revert to last known good version

## Scenario 6: MCP client connection failures
Symptoms: VS Code / Claude Code cannot discover or invoke tools
Diagnosis: Check MCP_ENABLED=true, verify /mcp/sse endpoint responds, check client logs
Recovery: Restart gateway. Verify .vscode/mcp.json or .mcp.json config.
Escalation: Check for transport-level issues (firewall, port binding)
```

### SLO validation test design (`test_slo_validation.py`)

```python
"""SLO validation: captures latency by cache state and checks against targets.

Skipped if gateway not available. Runs against live services.
Designed for CI nightly or manual validation.
"""
import pytest

# SLO thresholds from docs/contracts/slo-targets.md v1.0.0
SEARCH_P50_WARM_MS = 150
SEARCH_P95_WARM_MS = 400
SEARCH_P50_COLD_MS = 500
SEARCH_P95_COLD_MS = 1500
BUNDLE_P50_WARM_MS = 500   # cache miss (warm infrastructure)
BUNDLE_P95_WARM_MS = 1200
BUNDLE_P50_COLD_MS = 2000
BUNDLE_P95_COLD_MS = 4000

class TestSloValidation:
    """Latency SLO validation with warm/cold cache split."""

    def test_search_warm_latency(self, mcp_client, indexed_repo):
        """search_repo_memory warm-cache p50 and p95 within SLO."""
        # Run 20 searches (discard first as cold), collect durations
        # Assert: p50 <= SEARCH_P50_WARM_MS, p95 <= SEARCH_P95_WARM_MS
        ...

    def test_search_cold_latency(self, mcp_client, fresh_index):
        """search_repo_memory cold-start p50 and p95 within SLO."""
        # Index fresh repo, immediately search, collect durations
        # Assert: p50 <= SEARCH_P50_COLD_MS, p95 <= SEARCH_P95_COLD_MS
        ...

    def test_bundle_warm_latency(self, mcp_client, indexed_repo):
        """get_context_bundle warm-cache p50 and p95 within SLO."""
        # First call populates cache, subsequent calls are cache hits
        # Assert: p50 <= BUNDLE_P50_WARM_MS, p95 <= BUNDLE_P95_WARM_MS
        ...

    def test_bundle_cold_latency(self, mcp_client, fresh_index):
        """get_context_bundle cold-start p50 and p95 within SLO."""
        # Assert: p50 <= BUNDLE_P50_COLD_MS, p95 <= BUNDLE_P95_COLD_MS
        ...
```

### Compatibility CI gate design (`scripts/check_compatibility.py`)

```python
"""CI gate: validates MCP tool schema compatibility policy.

FAIL-CLOSED: non-zero exit blocks release. No silent override.
Exception path: Board-approved waiver documented in DECISION_LOG.md
with specific tool name and justification.

Checks:
1. All tool schemas in gateway-mcp-tools.md have version metadata.
2. No tool removal without deprecation warning period (2 releases or 6 months).
3. Deprecated tools have documented replacement.
4. X-Deprecated-Tool header present for any deprecated tool.

Exit code 0 = pass, 1 = fail. Required check in release workflow.
"""

def check_version_metadata(contract_path: str) -> list[str]:
    """Verify all tool schemas have Version field."""
    ...

def check_deprecation_window(contract_path: str, changelog_path: str) -> list[str]:
    """Verify no tool removed before compatibility window expires."""
    ...

def check_replacement_documented(contract_path: str) -> list[str]:
    """Verify deprecated tools have replacement listed."""
    ...

def main() -> int:
    """Run all checks. Return 0 if all pass, 1 if any fail.

    On failure, prints specific violations to stderr.
    Does NOT support --force or --skip flags.
    Exception path: add Board-approved waiver to DECISION_LOG.md,
    then add tool name to WAIVER_FILE (scripts/compatibility_waivers.txt).
    Script reads waiver file and excludes waived tools from checks.
    """
    ...
```

**CI integration (`release-gate.yml`):**

```yaml
# .github/workflows/release-gate.yml
name: Release Gate
on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  compatibility-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Run compatibility policy gate
        run: python scripts/check_compatibility.py
        # Non-zero exit fails the workflow and blocks release.
        # No continue-on-error. No allow-failure.
```

**Governed exception path:** If a release must proceed despite a compatibility violation, the process is:
1. Board documents waiver in `DECISION_LOG.md` with tool name, justification, and expiry.
2. Tool name is added to `scripts/compatibility_waivers.txt` (one per line).
3. `check_compatibility.py` reads waiver file and excludes listed tools from checks.
4. Waiver entries expire and must be cleaned up per the documented expiry.

### Grafana dashboard design (`gateway-overview.json`)

Dashboard panels:
1. **MCP Tool Latency (p50/p95)** -- Histogram quantiles from `mcp_tool_call_duration_seconds`, split by `tool` and `cache_state` labels. Separate rows for warm-cache and cold-start.
2. **Request Throughput** -- Rate of `mcp_tool_call_total` by tool, 1-minute windows.
3. **Error Rate** -- Rate of `mcp_tool_call_total{status="error"}` / total, percentage.
4. **Dependency Health** -- `mcp_dependency_health` gauge per dependency (index, standards, postgres, ollama). Panel shows current state (1/0) with color coding.
5. **SLO Compliance** -- Annotation lines at SLO thresholds overlaid on latency panels.
6. **[NEW v12] Dependency Probe Freshness** -- `mcp_dependency_health_last_probe_timestamp` per dependency. Panel shows `time() - gauge_value` as "seconds since last probe". Color threshold: green <= 45s, yellow <= 90s, red > 90s.

Dashboard is a standard Grafana provisioning JSON, importable via Grafana UI or provisioning directory.

### Alerting rules design (`gateway-alerts.yaml`)

```yaml
# Prometheus alerting rules for Context Gateway
groups:
  - name: gateway_slo
    rules:
      - alert: SearchLatencyP95High
        expr: histogram_quantile(0.95, rate(mcp_tool_call_duration_seconds_bucket{tool="search_repo_memory"}[5m])) > 1.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "search_repo_memory p95 latency exceeds 1.5s SLO"
          description: "Current p95: {{ $value | humanizeDuration }}. Runbook: docs/operations/runbook.md Scenario 4."

      - alert: BundleLatencyP95High
        expr: histogram_quantile(0.95, rate(mcp_tool_call_duration_seconds_bucket{tool="get_context_bundle"}[5m])) > 4.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "get_context_bundle p95 latency exceeds 4.0s SLO"
          description: "Current p95: {{ $value | humanizeDuration }}. Runbook: docs/operations/runbook.md Scenario 4."

      - alert: HighErrorRate
        expr: rate(mcp_tool_call_total{status="error"}[5m]) / rate(mcp_tool_call_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "MCP tool error rate exceeds 1%"
          description: "Error rate: {{ $value | humanizePercentage }}. Check gateway logs for error patterns."

      - alert: DependencyDown
        expr: mcp_dependency_health == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dependency {{ $labels.dependency }} is unhealthy"
          description: "{{ $labels.dependency }} has been down for >1m. Runbook: docs/operations/runbook.md Scenario 1 (ollama), Scenario 2 (postgres)."

      # [NEW v12] Staleness alert based on inspectable timestamp gauge
      - alert: DependencyProbeStale
        expr: time() - mcp_dependency_health_last_probe_timestamp > 90
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Dependency health probe for {{ $labels.dependency }} has not run in over 90 seconds"
          description: "Last probe: {{ $value | humanizeDuration }} ago. Gateway background task may have stalled."
```

### Minimal safe change strategy

1. **[CHANGED v16] Additive-only for monitoring consumers, always-on for metrics endpoint.** The `/metrics` endpoint and dependency health probe are part of the gateway server and are active whenever `prometheus_client` is installed. They do not require `--profile monitoring`. The monitoring profile only controls whether Prometheus and Grafana containers are running to consume the metrics. Existing services work identically whether or not `prometheus_client` is installed (graceful degradation).

2. **Metrics module degrades gracefully.** If `prometheus_client` is not installed, `TimedOperation` continues to log `duration_ms` to structured logs with no metrics recording. The `/metrics` endpoint and dependency health probe are not registered. This preserves existing behavior for environments without the optional dependency.

3. **Documentation-heavy.** Runbook and migration strategy are pure documentation. No code changes required.

4. **SLO validation tests are opt-in.** `test_slo_validation.py` requires live services and is skipped in standard `pytest` runs (same skip pattern as existing MCP integration tests). Designed for CI nightly or manual validation.

5. **CI gate is fail-closed.** `check_compatibility.py` is a required check in the release workflow. Non-zero exit blocks release. Exceptions require Board-approved waiver documented in `DECISION_LOG.md`.

6. **No schema migrations, no new runtime dependencies in core services.** `prometheus_client` is added as an optional dependency. Gateway continues to function without it.

7. **[CHANGED v15] `/metrics` binding is mode-aware but exposure is inherited.** Controlled by `METRICS_BIND_HOST` env var (default `127.0.0.1`). In Docker compose, set to `0.0.0.0` for container-internal access. In compose mode, `/metrics` is reachable from the host via the existing published port 8080 -- the same port already serving MCP/HTTP traffic. No new attack surface is introduced. See "Binding model by runtime mode" and "Security posture" sections.

8. **Dependency health probe is non-blocking.** Runs as a background `asyncio` task. Probe failures update gauge to 0 but do not affect request handling. 5-second timeout per probe prevents slow probes from accumulating.

### Order of operations

1. **Create metrics module** -- `mcp-memory-local/services/shared/src/metrics.py` with Prometheus histograms, counters, gauges, **last-probe-timestamp gauge**, and `update_dependency_health()` probe function. Graceful degradation when `prometheus_client` not installed.

2. **Instrument gateway** -- Add `/metrics` endpoint to `server.py` with mode-aware binding (see binding model). Extend `TimedOperation` to record histogram observations. Add metrics middleware for tool call tracking with `cache_state` label. **Add `asyncio` background task that calls `update_dependency_health()` every 30 seconds, started at gateway startup, cancelled on shutdown.** The health probe reuses existing health-check logic from `GET /health` and adds ollama probe. Each probe also sets `_last_probe_timestamp` gauge. **The `/metrics` endpoint and health probe are active whenever `prometheus_client` is installed, regardless of `--profile monitoring`.**

3. **Create monitoring stack** -- Add Prometheus and Grafana services to `docker-compose.yml` behind `--profile monitoring`. Set `METRICS_BIND_HOST=0.0.0.0` on gateway service. Prometheus scrapes `gateway:8080/metrics` via Docker network. Create Grafana dashboard JSON and Prometheus alerting rules.

4. **Create runbook** -- `docs/operations/runbook.md` with 6 failure scenarios expanded from existing troubleshooting doc.

5. **Create schema migration strategy doc** -- `docs/operations/schema-migration-strategy.md` documenting breaking vs non-breaking changes, rollback procedures, version compatibility rules.

6. **Create SLO validation test** -- `tests/mcp/test_slo_validation.py` with warm/cold cache split, latency collection, and assertion against SLO thresholds.

7. **Create compatibility CI gate** -- `scripts/check_compatibility.py` (fail-closed) validating tool schema versioning and deprecation policy. Create `.github/workflows/release-gate.yml` as required release check. Create `scripts/compatibility_waivers.txt` (empty, with format documentation).

8. **Update existing docs** -- Promote `slo-targets.md` to v1.0.0. Add monitoring section to `CONFIGURATION.md`.

9. **Validate** -- Run existing test suite (regression), new SLO validation tests, compatibility gate script, verify dependency health gauge freshness via `_last_probe_timestamp`, and **execute alert trigger drill (closure artifact #12)**.

### Deployment steps

1. Install `prometheus_client` as optional dependency: `pip install prometheus_client` (or add to `requirements-monitoring.txt`).
2. Merge documentation, test, and metrics files (no behavioral change with monitoring disabled).
3. Enable monitoring: `docker compose --profile monitoring up -d`.
4. **[CHANGED v15] Verify `/metrics` endpoint reachability per mode:**
   - **Host-local dev:** `curl localhost:8080/metrics` (gateway binds `127.0.0.1` by default).
   - **Containerized compose:** `curl localhost:8080/metrics` (gateway port 8080 is host-published in docker-compose.yml for MCP client access; `/metrics` is reachable on the same port). Alternatively, verify Prometheus internal scraping: `docker compose exec prometheus wget -qO- gateway:8080/metrics`.
5. **[CHANGED v12] Verify dependency health gauge freshness via timestamp gauge:**
   ```bash
   # Read last-probe timestamps
   curl -s localhost:8080/metrics | grep mcp_dependency_health_last_probe_timestamp
   # Verify all 4 dependencies present (index, standards, postgres, ollama)
   # Verify each timestamp is within 45 seconds of current time
   ```
6. Import Grafana dashboard: open `localhost:3000`, import `monitoring/dashboards/gateway-overview.json`.
7. Run SLO validation: `python -m pytest tests/mcp/test_slo_validation.py -v`.
8. Run compatibility gate: `python scripts/check_compatibility.py`.
9. Execute runbook scenario 1 (embedding outage) as game-day drill.
10. **[NEW v15] Execute alert trigger drill** (closure artifact #12) -- see "Exact commands" section.

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `prometheus_client` dependency conflicts with existing packages | Low | Medium | Added as optional dependency. Metrics degrade gracefully if not installed. Gateway continues to function without it. |
| **[CHANGED v15]** `/metrics` endpoint exposes internal service metadata | Low | Low | `/metrics` is a sub-path on the existing host-published port 8080 -- no new network exposure. Metric labels are limited to static enums (`tool`, `cache_state`, `status`, `dependency`). No secrets, tokens, internal URLs, or user data in metrics. Error sanitization already strips sensitive data. Consistent with existing `/health` endpoint exposure on the same port. |
| Monitoring stack (Prometheus + Grafana) consumes significant resources on dev machine | Medium | Low | Behind `--profile monitoring` -- disabled by default. Prometheus retention set to 24h for dev. No impact on gateway performance. |
| SLO validation tests fail because provisional thresholds are unrealistic | Medium | Medium | Tests use thresholds from existing `slo-targets.md`. If tests fail, thresholds are updated in the document (the test is the validation mechanism). Failures are informational, not blocking. |
| `TimedOperation` metrics recording adds latency to tool calls | Low | Low | Prometheus histogram observation is ~microseconds. No network call. No measurable impact on tool call latency. |
| Compatibility gate blocks a legitimate release | Low | Medium | Governed exception path: Board-approved waiver in `DECISION_LOG.md`, tool added to `scripts/compatibility_waivers.txt`. No silent override or `--force` flag. |
| Dependency health probe adds load to downstream services | Low | Low | 30-second interval, 5-second timeout. Each probe is a single lightweight HTTP GET or SQL ping. Equivalent to existing Docker health checks running at similar intervals. |
| Dependency health probe stalls and accumulates background tasks | Low | Medium | Each probe cycle has a 5-second per-dependency timeout (20s worst case for all 4). 30-second interval ensures previous cycle completes before next starts. Task cancellation on gateway shutdown. |

### Hidden dependencies

- **`prometheus_client` package.** Required for metrics. Not in current `requirements.txt`. Must be added as optional dependency or in a separate `requirements-monitoring.txt`.
- **Port 9090 (Prometheus) and 3000 (Grafana).** Monitoring stack uses these default ports. Docker compose profile must expose them. Conflicts with other local services on same ports possible.
- **`TimedOperation` in shared module.** Extending it affects all three services (gateway, index, standards). Change must be backward-compatible -- metrics recording must be optional.
- **SLO thresholds.** `slo-targets.md` is currently v0.1.0 Provisional. Promoting to v1.0.0 means thresholds become the official targets. If they prove unrealistic, a follow-up cycle is needed to adjust.
- **Existing soak test.** `test_mcp_soak.py` runs for 15 minutes. New SLO validation test should not duplicate this -- it focuses on latency percentiles, not stability.
- **Existing health-check logic in `server.py`.** Dependency health probe reuses this logic. If the health-check handler changes, the probe must be updated accordingly.
- **GitHub Actions for release-gate.** Requires `.github/workflows/` directory and repository Actions enabled. If CI is not yet configured, the workflow file is inert until activated.
- **[NEW v12] `METRICS_BIND_HOST` environment variable.** New config point for metrics binding. Default `127.0.0.1` preserves security for host-local dev. Must be set to `0.0.0.0` in `docker-compose.yml` for container mode. Misconfiguration (forgetting to set it in compose) would make Prometheus unable to scrape -- detected by closure artifact #2.

### Rollback strategy

Per CONSTITUTION.md v0.4:

1. **Metrics rollback:** Remove `metrics.py`, revert `TimedOperation` extension, remove `/metrics` endpoint and background health probe from `server.py`. Gateway reverts to log-only timing. No data loss.
2. **Monitoring stack rollback:** Remove Prometheus and Grafana from `docker-compose.yml`. Delete `monitoring/` directory. No impact on gateway.
3. **Doc rollback:** Delete `docs/operations/runbook.md` and `docs/operations/schema-migration-strategy.md`. Revert `slo-targets.md` to v0.1.0. Revert `CONFIGURATION.md` edits.
4. **Test rollback:** Delete `tests/mcp/test_slo_validation.py`. Delete `scripts/check_compatibility.py`. Delete `.github/workflows/release-gate.yml`. Existing tests unchanged.
5. **Rollback time:** ~2 min for `git revert`. Service restart only needed if metrics were enabled.

---

## SECTION C -- Validation Steps

### Acceptance criteria (from source proposal Phase 6)

1. On-call runbook published with triage steps.
2. Alerts trigger on threshold breaches with actionable messages.
3. Backward compatibility policy documented for MCP tool changes.
4. SLO dashboard exposes p50/p95 for `search_repo_memory` and `get_context_bundle` and tracks against targets.

### Closure artifacts required

1. **Regression pass:** Existing `tests/contracts/`, `tests/mcp/`, and `tests/policy/` tests pass.
2. **[CHANGED v16] Metrics endpoint live:** `curl localhost:8080/metrics` returns Prometheus text format with `mcp_tool_call_duration_seconds` histogram, `mcp_tool_call_total` counter, `mcp_dependency_health` gauge, and `mcp_dependency_health_last_probe_timestamp` gauge. The `/metrics` endpoint is part of the gateway server and is active whenever `prometheus_client` is installed, regardless of whether `--profile monitoring` is enabled. Works in both host-local dev and compose mode (compose uses the existing host-published port 8080).
3. **Dashboard importable:** `monitoring/dashboards/gateway-overview.json` imports into Grafana without errors. Dashboard shows panels for latency (p50/p95 split by cache_state), error rate, throughput, dependency health, **and probe freshness**.
4. **Alert rules valid (static):** `monitoring/alerts/gateway-alerts.yaml` passes `promtool check rules` validation. Rules cover: `SearchLatencyP95High`, `BundleLatencyP95High`, `HighErrorRate`, `DependencyDown`, **`DependencyProbeStale`**.
5. **Runbook complete:** `docs/operations/runbook.md` covers at least 6 failure scenarios, each with Symptoms/Diagnosis/Recovery/Escalation structure.
6. **Migration strategy documented:** `docs/operations/schema-migration-strategy.md` defines breaking vs non-breaking changes, rollback procedure, and compatibility window enforcement.
7. **SLO validation test pass:** `test_slo_validation.py` runs against live services, captures latency by warm/cold cache state, and reports p50/p95 against SLO thresholds. (Test may report SLO misses -- the test itself must run and produce results.)
8. **Compatibility gate pass (fail-closed):** `python scripts/check_compatibility.py` exits 0 against current contract docs. `.github/workflows/release-gate.yml` exists and references `check_compatibility.py` as a required step with no `continue-on-error` or `allow-failure`.
9. **SLO document promoted:** `docs/contracts/slo-targets.md` updated to v1.0.0 with "Instrumented" status and reference to metrics module.
10. **Existing HTTP/MCP workflows unaffected:** `tests/mcp/test_mcp_integration.py` and `tests/mcp/test_mcp_smoke.py` pass.
11. **[CHANGED v12] Dependency health gauge freshness:** `curl -s localhost:8080/metrics | grep mcp_dependency_health_last_probe_timestamp` returns gauge values for all 4 dependencies (`index`, `standards`, `postgres`, `ollama`). Each value is a unix epoch timestamp. Freshness verified by: `current_time - gauge_value <= 45` (30s probe interval + 15s scrape margin). Two reads 30+ seconds apart show updated timestamp values, confirming the probe is running. This method does not depend on Prometheus sample timestamps.
12. **[NEW v15] Alert trigger drill (end-to-end):** Demonstrates that alerts fire and produce actionable messages under real failure conditions. Two scenarios required:
    - **(a) Dependency-down:** Stop the ollama container (`docker compose stop ollama`). Wait for probe cycle (30s) + alert `for` duration (1m) = ~90s minimum. Query Prometheus alerts API (`curl localhost:9090/api/v1/alerts`) and capture `DependencyDown` alert with `state: "firing"`, `labels.dependency: "ollama"`, and `annotations.summary` containing actionable text identifying the failed dependency. Restart ollama after capture.
    - **(b) Latency breach:** Inject artificial latency into `search_repo_memory` calls (e.g., by temporarily adding a `time.sleep(2)` to the tool handler, or by overloading the embedding service). Generate sufficient traffic to populate the 5m rate window. Wait for alert evaluation. Query Prometheus alerts API and capture `SearchLatencyP95High` alert with `state: "firing"` and `annotations.summary` containing the SLO threshold value.
    - **Evidence format:** For each scenario, capture the full JSON response from `curl localhost:9090/api/v1/alerts` showing the relevant alert in firing state. Evidence must include: alert name, state, severity label, and annotations with actionable summary/description text (including runbook reference where applicable).

### Exact commands to produce closure artifacts

```bash
# All commands run from rmembr/ with services up (MCP_ENABLED=true)

# 1. Regression -- existing tests
python -m pytest tests/contracts/ -v
python -m pytest tests/mcp/test_mcp_tools.py tests/mcp/test_mcp_parity.py tests/mcp/test_mcp_transport_gating.py -v
python -m pytest tests/mcp/test_mcp_integration.py -v
python -m pytest tests/mcp/test_mcp_smoke.py -v

# 2. Metrics endpoint (active whenever prometheus_client is installed,
#    regardless of --profile monitoring)
curl -s localhost:8080/metrics | grep mcp_tool_call_duration_seconds
curl -s localhost:8080/metrics | grep mcp_tool_call_total
curl -s localhost:8080/metrics | grep mcp_dependency_health_last_probe_timestamp

# 2b. Verify Prometheus internal scraping (compose mode only, requires --profile monitoring)
# docker compose exec prometheus wget -qO- gateway:8080/metrics | grep mcp_tool_call_duration_seconds

# 3. Dashboard import (manual, requires --profile monitoring for Grafana)
# Open Grafana at localhost:3000
# Import monitoring/dashboards/gateway-overview.json
# Verify 6 panels render without error (latency, throughput, error rate, dep health, SLO, probe freshness)

# 4. Alert rules validation (static)
promtool check rules monitoring/alerts/gateway-alerts.yaml

# 5. Runbook review (manual)
# Verify docs/operations/runbook.md has 6+ scenarios
# Each scenario has Symptoms/Diagnosis/Recovery/Escalation

# 6. Migration strategy review (manual)
# Verify docs/operations/schema-migration-strategy.md covers
# breaking/non-breaking changes, rollback, compatibility window

# 7. SLO validation
python -m pytest tests/mcp/test_slo_validation.py -v

# 8. Compatibility gate (fail-closed verification)
python scripts/check_compatibility.py
# Verify exit code is 0
# Verify .github/workflows/release-gate.yml has no continue-on-error

# 9. SLO document version
grep -q "v1.0.0" docs/contracts/slo-targets.md && echo "PASS" || echo "FAIL"

# 10. HTTP/MCP regression
python -m pytest tests/mcp/test_mcp_integration.py -v
python -m pytest tests/mcp/test_mcp_smoke.py -v

# 11. [CHANGED v12] Dependency health gauge freshness via timestamp gauge
# Read 1: capture timestamps
curl -s localhost:8080/metrics | grep mcp_dependency_health_last_probe_timestamp
# Verify all 4 dependencies present (index, standards, postgres, ollama)
# Record timestamp values

# Wait for at least one probe cycle
sleep 35

# Read 2: capture timestamps again
curl -s localhost:8080/metrics | grep mcp_dependency_health_last_probe_timestamp
# Verify: each timestamp in Read 2 > corresponding timestamp in Read 1
# Verify: current_time - each timestamp <= 45 seconds
# This proves the probe is running and gauge is not stale,
# without relying on Prometheus sample timestamps.

# 12. [NEW v15] Alert trigger drill (requires --profile monitoring active)
# Prerequisite: docker compose --profile monitoring up -d
# Wait for Prometheus to start scraping (30s)

# 12a. Dependency-down drill
docker compose stop ollama
echo "Waiting ~100s for probe cycle + alert for duration..."
sleep 100
# Capture DependencyDown alert in firing state
curl -s localhost:9090/api/v1/alerts | python -m json.tool
# Expected: alert named "DependencyDown" with state "firing",
#   labels.dependency "ollama", annotations.summary containing
#   "Dependency ollama is unhealthy"
# Restart ollama
docker compose start ollama

# 12b. Latency breach drill
# Option A: Inject sleep into search handler temporarily
# Option B: Overload embedding service to cause natural latency
# Generate traffic to populate rate window:
#   for i in $(seq 1 30); do
#     curl -s -X POST localhost:8080/mcp/tools/search_repo_memory \
#       -H "Content-Type: application/json" \
#       -d '{"repo": "test", "query": "test"}' > /dev/null
#   done
# Wait for 5m rate window + alert evaluation
# curl -s localhost:9090/api/v1/alerts | python -m json.tool
# Expected: alert named "SearchLatencyP95High" with state "firing",
#   annotations.summary containing "exceeds 1.5s SLO"
# Revert any injected latency
```

---

## SECTION D -- Auditor Sensitivity

1. **[CHANGED v15] Metrics do not leak sensitive data.** Auditor will verify that `/metrics` endpoint contains only operational metrics (latency, counts, health, probe timestamps) and no secrets, tokens, internal URLs, or user data. Mitigation: metric labels are limited to `tool`, `cache_state`, `status`, `dependency` -- all static enums. No request content in metrics. In compose mode, `/metrics` is reachable from the host via the existing published port 8080 (same as MCP/HTTP traffic) -- no new port exposure. In host-local dev, bound to `127.0.0.1`.

2. **[CHANGED v16] Monitoring consumers are optional; metrics endpoint is always-on when instrumented.** Auditor will verify that Prometheus and Grafana do not become hard dependencies. Mitigation: behind `--profile monitoring` in Docker Compose. Gateway functions identically without monitoring consumers. `prometheus_client` import is guarded with graceful fallback -- when not installed, no `/metrics` endpoint, no health probe, no histogram recording. When installed, `/metrics` and the health probe are active regardless of `--profile monitoring`. This two-tier model (always-on metrics vs optional consumers) is consistent across all plan sections.

3. **SLO thresholds are grounded.** Auditor will verify that SLO targets in test assertions match the values in `slo-targets.md`. Mitigation: test file imports thresholds as named constants with explicit comments referencing `slo-targets.md` version. Any mismatch is visible in code review.

4. **Runbook covers real failure modes.** Auditor will verify that runbook scenarios correspond to actual system behavior, not hypothetical failures. Mitigation: 3 of 6 scenarios are expanded from existing `.ai/memory/operations-troubleshooting.md` (confirmed real). Remaining 3 (cache thrashing, policy failures, MCP client connection) are derived from Phase 4 and Phase 5 implementation patterns.

5. **Compatibility gate enforces policy without silent override.** Auditor will verify that `check_compatibility.py` is wired as a required CI check with fail-closed behavior and no `--force` flag. Mitigation: `.github/workflows/release-gate.yml` runs script as required step. No `continue-on-error`. Exception path requires Board-approved waiver in `DECISION_LOG.md` and entry in `scripts/compatibility_waivers.txt`.

6. **`TimedOperation` extension is backward-compatible.** Auditor will verify that extending `TimedOperation` does not break existing callers in index and standards services. Mitigation: extension adds optional `cache_state` parameter with `None` default. Existing callers pass no new arguments. When `prometheus_client` is not installed, histogram observation is a no-op.

7. **Dashboard and alert definitions are well-formed.** Auditor will verify that Grafana JSON and Prometheus YAML are valid and importable. Mitigation: `promtool check rules` validates alert YAML. Dashboard JSON follows Grafana provisioning schema v8+. Both are validated in closure artifacts.

8. **[CHANGED v12] Dependency health gauge reflects actual state with inspectable freshness.** Auditor will verify that `mcp_dependency_health` values are updated on a defined cadence and that freshness is provable via `mcp_dependency_health_last_probe_timestamp`. Mitigation: 30-second probe interval with 5-second per-dependency timeout. Closure artifact #11 verifies freshness by comparing `_last_probe_timestamp` gauge values to current time (delta <= 45s) and by showing two reads 30s apart with advancing timestamps. This does not rely on Prometheus sample timestamps. `DependencyProbeStale` alert fires if `time() - _last_probe_timestamp > 90s` for 2 minutes.

9. **[CHANGED v15] `/metrics` exposure model is unambiguous.** Auditor will verify that the binding model section is internally consistent and that all plan sections agree on whether `/metrics` is host-reachable in compose mode. Mitigation: the reconciled model explicitly states that `/metrics` inherits the existing host-published port 8080 in compose mode, that this does not introduce new attack surface, and that metrics contain only operational data with static enum labels. All references in risk table, deployment steps, closure artifacts, and this sensitivity section use consistent language. No claims of "not exposed to host network" in compose mode.

10. **[NEW v15] Alerts produce actionable messages under real conditions.** Auditor will verify that closure artifact #12 demonstrates end-to-end alert firing (not just static syntax validation). Mitigation: drill requires inducing two distinct failure conditions (dependency-down and latency breach), waiting for alert evaluation, and capturing Prometheus API evidence showing alerts in firing state with actionable annotations including runbook references.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined -- Prometheus metrics: `mcp_tool_call_duration_seconds` (histogram, labels: `tool` str required, `cache_state` str required enum ["warm","cold","miss"], buckets: [0.05,0.1,0.15,0.3,0.5,0.6,1.0,1.2,1.5,2.0,4.0,10.0]). `mcp_tool_call_total` (counter, labels: `tool` str required, `status` str required enum ["success","error","denied"]). `mcp_dependency_health` (gauge, labels: `dependency` str required enum ["index","standards","postgres","ollama"], value: 1=healthy 0=degraded, updated every 30s by background probe). **`mcp_dependency_health_last_probe_timestamp`** (gauge, labels: `dependency` str required enum ["index","standards","postgres","ollama"], value: unix epoch float, updated every 30s after each probe). `/metrics` endpoint: Prometheus text exposition format (text/plain; version=0.0.4), binding per `METRICS_BIND_HOST` env var (default `127.0.0.1`, `0.0.0.0` in compose). Grafana dashboard: JSON conforming to Grafana provisioning schema v8+. Alert rules: Prometheus alerting rules YAML format. Release gate: GitHub Actions workflow YAML. **[NEW v15] Alert drill evidence: JSON from Prometheus `/api/v1/alerts` endpoint showing alert name, state, labels, and annotations.**
- [x] All boundary conditions named -- SLO thresholds: search p50 warm 150ms, p95 warm 400ms, p50 cold 500ms, p95 cold 1500ms; bundle p50 warm 500ms, p95 warm 1200ms, p50 cold 2000ms, p95 cold 4000ms. Error rate threshold: >1% over 5m = critical. Dependency health: 0 for >1m = critical. **Dependency probe staleness: `time() - _last_probe_timestamp > 90s` for >2m = warning.** Latency alert: p95 >1.5s (search) or >4.0s (bundle) for >5m = warning. "Minor fix" for monitoring issues: fewer than 10 lines changed in gateway server code. `prometheus_client` graceful degradation: import guarded, no-op when absent. SLO test sample size: minimum 20 calls per warm test, 5 calls per cold test. Health probe interval: 30s. Health probe timeout: 5s per dependency. Compatibility gate: exit 0 = pass, exit 1 = fail, no override flags. **Freshness verification threshold: `current_time - gauge_value <= 45s`.** **[NEW v15] Alert drill wait times: dependency-down ~90s (30s probe + 1m for), latency breach ~5m (rate window) + evaluation.**
- [x] **[CHANGED v16] All behavioral modes specified** -- **instrumented** (`prometheus_client` installed: gateway serves HTTP+MCP, `/metrics` endpoint active, health probe running every 30s, `TimedOperation` records histogram observations alongside log output), **uninstrumented** (`prometheus_client` not installed: gateway serves HTTP+MCP, logs timing to stdout, no `/metrics` endpoint, no health probe -- graceful degradation preserves all existing behavior), **monitored** (instrumented + `--profile monitoring` active: Prometheus scrapes `/metrics`, Grafana dashboards active, alerts evaluating), **CI** (SLO validation tests run against live services with skip marker when unavailable, compatibility gate runs as required release check with fail-closed behavior). **[CHANGED v15] Binding modes: host-local dev (`METRICS_BIND_HOST=127.0.0.1`, `/metrics` on localhost only) vs containerized compose (`METRICS_BIND_HOST=0.0.0.0`, `/metrics` reachable from host via existing published port 8080).**
- [x] Rollback procedure cites current CONSTITUTION.md version -- CONSTITUTION.md v0.4; rollback via `git revert` (delete `metrics.py`, `monitoring/`, `docs/operations/`, `tests/mcp/test_slo_validation.py`, `scripts/check_compatibility.py`, `.github/workflows/release-gate.yml`; revert `server.py`, `structured_logging.py`, `docker-compose.yml`, `slo-targets.md`, `CONFIGURATION.md` edits); no schema changes; `prometheus_client` removal from dependencies; rollback time ~2 min plus service restart.
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at `governance/CONSTITUTION.md` (confirmed v0.4), providers.md at `governance/providers.md` (confirmed version 1.3), source proposal at `governance/proposals/context-gateway-mcp-full-alignment-plan.md` (Phase 6 section confirmed), prior cycle closure at `governance/plans/CG_MCP/artifacts/CG_MCP_v9_closure.md` (confirmed Phase 5 CLOSED), implementation repo at `C:\gh_src\rmembr` (confirmed `mcp-memory-local/services/shared/src/structured_logging.py`, `mcp-memory-local/services/gateway/src/server.py`, `docs/contracts/slo-targets.md`, `tests/contracts/test_deprecation_warnings.py` exist and match described state).
- [x] Declared modification scope matches execution steps -- "Files to modify" table (5 rows: server.py, structured_logging.py, docker-compose.yml, slo-targets.md, CONFIGURATION.md) aligns with "Order of operations" steps 2, 3, 8. "Files to create" table (8 rows) aligns with steps 1, 3, 4, 5, 6, 7. No undeclared file modifications.
- [x] Path integrity verified -- All 17 implementation file paths listed in the Path Integrity Sweep table use a single canonical scheme: service source under `mcp-memory-local/services/`, infrastructure under `mcp-memory-local/`, tests and docs at repo root. No mixed path conventions.

READY FOR AUDITOR REVIEW
