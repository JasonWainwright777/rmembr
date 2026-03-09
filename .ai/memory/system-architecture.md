---
title: System Architecture
---

# System Architecture (mcp-memory-local)

## Classification

rMEMbr is a **Federated Context Retrieval System (FCRS)**:

- **Federated** — multiple independent services (index, standards, gateway) each own their data domain and can be queried independently
- **Context** — assembles contextual bundles from memory chunks, standards, and policies tailored to the requesting agent's needs
- **Retrieval** — semantic search via pgvector embeddings with ranked results (path boost, freshness boost) assembled into bounded context windows

The gateway acts as the federation layer — it fans out to index and standards services, merges results, applies budget/policy constraints, and returns a unified bundle.

## Components

## Gateway (FastAPI)

- External entry point on host `:8080`
- Orchestrates calls to Index and Standards
- Assembles “context bundles” with:
  - semantic matches from repo memory
  - referenced enterprise standards
  - persona-based classification filtering
  - deterministic sorting and size budgeting
  - caching (`bundle_cache`)

Key file: `mcp-memory-local/services/gateway/src/server.py`.

## Index (FastAPI)

- Internal-only service (no host port exposed)
- Reads `repos/<repo>/.ai/memory/**`
- Chunks markdown into stable anchors
- Calls Ollama embeddings
- Upserts to Postgres (`memory_chunks`, `memory_packs`)
- Performs semantic search with pgvector cosine distance

Key files:
- `mcp-memory-local/services/index/src/ingest.py`
- `mcp-memory-local/services/index/src/search.py`
- `mcp-memory-local/services/shared/src/chunking/chunker.py`

## Standards (FastAPI)

- Internal-only service
- Serves “enterprise standards” content from a standards repo (default: `repos/enterprise-standards/.ai/memory/**`)
- Supports simple version resolution (`local`, `v3`, `v4`, ...)

Key file: `mcp-memory-local/services/standards/src/server.py`.

## Postgres + pgvector

Stores:

- `memory_packs`: per repo pack metadata
- `memory_chunks`: chunk text + embeddings + identifiers
- `bundle_cache`: cached bundle payloads and bundle records

Schema is created by Index on startup: `mcp-memory-local/services/index/src/migrations.py`.

## Ollama

- Embedding provider called by the Index service
- Default: `nomic-embed-text` via `/api/embed`

Key file: `mcp-memory-local/services/index/src/embeddings.py`.

## Retrieval & Ranking Pipeline

The Index service includes a pluggable ranking pipeline beyond raw cosine similarity:

- `services/index/src/retrieval/engine.py`: orchestrates search → rank → normalize
- `services/index/src/retrieval/ranker.py`: applies configurable ranking stages
- `services/index/src/retrieval/types.py`: RankingConfig, ScoreComponents, ProvenanceInfo

Score components: `semantic + path_boost + freshness_boost = final score`

## Provider Framework

Index has a pluggable provider system for content sources:

- `services/index/src/providers/registry.py`: ProviderRegistry
- `services/index/src/providers/filesystem.py`: FilesystemProvider (default, reads local filesystem)
- `services/index/src/providers/github.py`: GitHubProvider (reads from GitHub repos via REST API)
- Migration 2 adds `provider_name` and `external_id` columns for multi-provider support
- Migration 3 adds `github_cache` table for ETag-based tree caching and blob content caching
- Config: `ACTIVE_PROVIDERS` env var (comma-separated: `filesystem`, `github`)
- GitHubProvider activates only when `GITHUB_TOKEN` is present in environment
- Two-layer cache (tree ETag + blob SHA) keeps steady-state API cost at 0-2 calls per index run

## MCP Protocol Server

Gateway includes an optional MCP (Model Context Protocol) server:

- `services/gateway/src/mcp_tools.py`: registers 9 tools
- `services/gateway/src/mcp_server.py`: Streamable HTTP transport (`/mcp`) plus legacy SSE transport (`/mcp/sse`, `/mcp/messages/`)
- `services/gateway/src/mcp_stdio_shim.py`: stdio transport option
- Gated by `MCP_ENABLED` env var (default: false); stdio via `MCP_STDIO_ENABLED`

## Observability

- `services/shared/src/metrics.py`: Prometheus metrics (`/metrics` endpoint when prometheus_client installed)
  - Histograms: `mcp_tool_call_duration_seconds`
  - Counters: `mcp_tool_call_total`, `mcp_tool_call_errors_total`
  - Gauges: `mcp_dependency_health`, `mcp_dependency_health_last_probe_timestamp`
- `services/shared/src/audit_log.py`: structured audit logging for tool invocations

## Request/Data Flow

## Indexing

1. User (via CLI) calls Gateway `/proxy/index/index_repo`
2. Gateway forwards to Index `/tools/index_repo` (with `X-Internal-Token`)
3. Index reads `repos/<repo>/.ai/memory/**` and chunks content (shared chunker)
4. Index calls Ollama to embed changed chunks
5. Index upserts rows to Postgres

## Bundle Assembly

1. User calls Gateway `/tools/get_context_bundle` with `{repo, task, persona, ...}`
2. Gateway calls Index `/tools/resolve_context` to get top-k chunk pointers
3. Gateway calls Standards `/tools/list_standards` + `/tools/get_standard` to fetch up to 5 standards
4. Gateway filters chunks by persona classification and applies size budget
5. Gateway returns JSON bundle and a markdown rendering
