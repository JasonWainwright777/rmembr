---
title: Operations Runbook Condensed
---

# Operations Runbook Condensed

Primary source:

- `docs/operations/runbook.md`

Use this as a fast triage map. For full procedures, follow the runbook.

## 1) Embedding Service Unavailable

Symptoms:

- search timeouts or 503
- Ollama dependency unhealthy

Immediate checks:

- Ollama version endpoint
- container status/logs
- model availability (`nomic-embed-text`)

## 2) Postgres Pool Exhausted

Symptoms:

- widespread 503/hangs
- connection timeout/pool exhausted logs

Immediate checks:

- active connection count
- long-running queries
- gateway/index pool sizing

## 3) Internal Token Mismatch

Symptoms:

- 401 from internal service calls
- health dependency failures

Immediate checks:

- `INTERNAL_SERVICE_TOKEN` consistency across services
- service restart after correction

## 4) Bundle Cache Thrashing

Symptoms:

- high bundle p95 latency
- low cache hit pattern

Immediate checks:

- cache_state distribution in metrics
- TTL (`BUNDLE_CACHE_TTL_SECONDS`)
- frequent reindex churn

## 5) Policy Denials

Symptoms:

- unexpected authorization failures
- deny audit log entries

Immediate checks:

- loaded policy file and version
- role/tool mapping and default role
- hot reload setting

## 6) MCP Client Connection Failures

Symptoms:

- client cannot discover/use tools

Immediate checks:

- gateway health
- `MCP_ENABLED` true
- endpoint/transport match in client config
