---
title: Configuration
---

# Configuration (mcp-memory-local)

## Primary Config Surface

- `mcp-memory-local/.env` (copy from `.env.example`)
- `mcp-memory-local/docker-compose.yml`
- Service defaults via environment variables in code

## Common Environment Variables

## Postgres

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `POSTGRES_HOST` and `POSTGRES_PORT` are container-facing (default `postgres:5432`)

## Embeddings (Index)

- `OLLAMA_URL` (default `http://ollama:11434`)
- `EMBED_MODEL` (default `nomic-embed-text`)
- `EMBED_DIMS` (informational; schema assumes 768 unless migrations change)

## Repos + Standards

- `REPOS_ROOT` (default `/repos` inside containers)
- `STANDARDS_REPO` (default `enterprise-standards`)
- `DEFAULT_STANDARDS_VERSION` (default `local`)

## Gateway Behavior

- `GATEWAY_MAX_BUNDLE_CHARS` (default `40000`)
- `GATEWAY_DEFAULT_K` (default `12`)
- `BUNDLE_CACHE_TTL_SECONDS` (default `300`)

## Auth

- `INTERNAL_SERVICE_TOKEN` is required for Gateway <-> Index/Standards calls.
  - Index and Standards reject missing/invalid tokens for all non-`/health` endpoints.

