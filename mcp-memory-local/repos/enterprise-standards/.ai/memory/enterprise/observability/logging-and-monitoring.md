---
title: Logging and Monitoring Standard
domain: observability
standard_id: enterprise/observability/logging-and-monitoring
version: v1
classification: internal
---

# Logging and Monitoring Standard

## Overview

All production services must emit structured logs, expose health endpoints, and publish metrics. Observability is not optional — it is a deployment prerequisite.

## Structured Logging

- All log entries must be structured JSON
- Required fields: `timestamp`, `level`, `message`, `service`, `correlationId`
- Optional fields: `userId`, `traceId`, `spanId`, `duration`, `errorCode`
- Never log secrets, tokens, passwords, or PII
- Use consistent log levels across all services

### Log Levels

| Level | Usage |
|-------|-------|
| Debug | Diagnostic detail, disabled in production |
| Information | Business events, request lifecycle |
| Warning | Recoverable issues, degraded performance |
| Error | Operation failures, unhandled exceptions |
| Critical | System-wide failures, data loss risk |

## Health Endpoints

Every service must expose:

- `GET /health` — returns `200 OK` with dependency status
- `GET /health/ready` — readiness probe (can serve traffic)
- `GET /health/live` — liveness probe (process is running)

Health responses must include:
```json
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "cache": "healthy",
    "downstream-api": "degraded"
  },
  "version": "1.2.3"
}
```

## Metrics

- Expose a `/metrics` endpoint in Prometheus exposition format
- Required metrics:
  - `http_request_duration_seconds` (histogram) — request latency by route and status
  - `http_requests_total` (counter) — request count by route, method, and status
  - `http_request_errors_total` (counter) — error count by route and error type
  - `dependency_health` (gauge) — 1 for healthy, 0 for unhealthy
- Use consistent label names: `service`, `route`, `method`, `status_code`

## Alerting

- Every production service must define alerts for:
  - Error rate > 1% over 5 minutes
  - P95 latency > SLO target over 5 minutes
  - Health check failures for > 2 minutes
  - Dependency health degraded for > 5 minutes
- Alerts must route to the owning team's on-call channel

## Distributed Tracing

- Propagate `X-Request-ID` and W3C `traceparent` headers across all service boundaries
- Use OpenTelemetry SDK for trace instrumentation
- Sample at 100% in non-production, 10% minimum in production
