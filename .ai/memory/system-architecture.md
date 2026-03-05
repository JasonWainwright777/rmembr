---
title: System Architecture
---

# System Architecture (mcp-memory-local)

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

