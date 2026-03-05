---
title: Data Model (Postgres)
---

# Data Model (Postgres + pgvector)

Schema is created by the Index service on startup:
`mcp-memory-local/services/index/src/migrations.py`.

## `memory_packs`

Tracks per-repo metadata (upserted during indexing).

Notable columns:

- `namespace`, `repo` (unique together)
- `classification` (default `internal`)
- `embedding_model` (default `nomic-embed-text`)
- `last_indexed_ref` (default `local`)

## `memory_chunks`

Stores chunk content and embeddings.

Notable columns:

- identifiers: `repo`, `ref`, `path`, `anchor` (unique with `(repo, path, anchor, ref)`)
- content: `heading`, `chunk_text`, `content_hash`
- retrieval: `embedding vector(768)` with HNSW index (cosine ops)
- access: `classification`

The Index service returns `similarity = 1 - (embedding <=> query_embedding)`.

## `bundle_cache`

Stores:

- search bundle cache entries (TTL via `expires_at`)
- bundle records for `explain_context_bundle` as `cache_key = bundle:<uuid>`

Gateway ensures a unique index on `cache_key` at startup (for upsert-like behavior).

