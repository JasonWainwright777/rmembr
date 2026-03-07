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

## Service URLs

- `INDEX_URL` (default `http://index:8081`)
- `STANDARDS_URL` (default `http://standards:8082`)
- `GATEWAY_PORT` (default `8080`), `INDEX_PORT` (default `8081`), `STANDARDS_PORT` (default `8082`)

## Gateway Behavior

- `GATEWAY_MAX_BUNDLE_CHARS` (default `40000`)
- `GATEWAY_DEFAULT_K` (default `12`)
- `BUNDLE_CACHE_TTL_SECONDS` (default `300`)

## Ranking (Index)

- `RANKING_PATH_BOOST` (default `0.1`): similarity boost for `changed_files` matches
- `RANKING_FRESHNESS_BOOST` (default `0.0`, disabled): boost for recently updated chunks
- `RANKING_FRESHNESS_WINDOW_HOURS` (default `168` = 7 days)

## Policy

- `POLICY_FILE` (path to policy JSON; defaults to built-in `policy/default_policy.json`)
- `POLICY_HOT_RELOAD` (enable hot-reload of policy file)
- Policy defines: persona→classification mapping, tool authorization, budget limits

## MCP Protocol

- `MCP_ENABLED` (stack default `true` in compose/env example; code fallback `false`): enable MCP server; primary transport is Streamable HTTP on `/mcp`, legacy SSE remains on `/mcp/sse`
- `MCP_STDIO_ENABLED` (default `false`): enable MCP stdio transport

## Providers (Index)

- `ACTIVE_PROVIDERS`: comma-separated list of content providers (default: filesystem only)

## GitHub Provider (Index)

- `GITHUB_TOKEN`: fine-grained PAT with Contents: Read-only and Metadata: Read-only (required for github provider; absent = provider not registered)
- `GITHUB_REPOS`: comma-separated `owner/repo` list to index (e.g., `octocat/my-repo,org/other-repo`)
- `GITHUB_API_URL`: API base URL (default: `https://api.github.com`; set for GitHub Enterprise)
- `GITHUB_DEFAULT_BRANCH`: branch to read .ai/memory from (default: `main`)

## Auth

- `INTERNAL_SERVICE_TOKEN` is required for Gateway <-> Index/Standards calls.
  - Index and Standards reject missing/invalid tokens for all non-`/health` endpoints.
