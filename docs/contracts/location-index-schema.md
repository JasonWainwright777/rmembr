# Location Index Schema Contract

**Version:** 0.1.0
**Status:** Locked (Phase 0)
**Last Updated:** 2026-03-05

---

## Overview

The location index stores chunked, embedded content from repository memory packs. It is backed by PostgreSQL with the pgvector extension. This document defines the canonical record schemas for the two core tables: `memory_packs` (pack-level metadata) and `memory_chunks` (chunk-level records with embeddings).

---

## Table: `memory_packs`

Pack-level metadata for each indexed repository memory pack.

| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `BIGSERIAL` | Yes (PK) | auto | Internal surrogate key |
| `namespace` | `TEXT` | Yes | `'default'` | Tenant namespace. Used for logical isolation. See Tenant Isolation below. |
| `repo` | `TEXT` | Yes | - | Repository name (e.g., `sample-repo-a`). Must not contain path traversal characters. |
| `pack_version` | `INT` | Yes | `1` | Version of the memory pack format |
| `owners` | `JSONB` | Yes | `'[]'` | Array of owner identifiers (email, team name) |
| `classification` | `TEXT` | Yes | `'internal'` | Data classification level: `public` or `internal` |
| `embedding_model` | `TEXT` | Yes | `'nomic-embed-text'` | Embedding model used for this pack's chunks |
| `last_indexed_ref` | `TEXT` | Yes | `'local'` | Last git ref that was indexed |
| `created_at` | `TIMESTAMPTZ` | Yes | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Yes | `now()` | Last update timestamp |

**Constraints:**
- `UNIQUE (namespace, repo)` -- one pack record per repo per namespace

---

## Table: `memory_chunks`

Individual content chunks with vector embeddings.

| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `BIGSERIAL` | Yes (PK) | auto | Internal surrogate key |
| `namespace` | `TEXT` | Yes | `'default'` | Tenant namespace. All queries MUST filter by namespace. |
| `source_kind` | `TEXT` | Yes | `'repo_memory'` | Content origin: `repo_memory` or `enterprise_standard` |
| `repo` | `TEXT` | Yes | - | Repository name |
| `ref_type` | `TEXT` | Yes | `'branch'` | Type of git ref: `branch`, `tag`, `commit` |
| `ref` | `TEXT` | Yes | `'local'` | Git ref value (branch name, tag, or SHA) |
| `path` | `TEXT` | Yes | - | File path within the memory pack (e.g., `.ai/memory/instructions.md`) |
| `anchor` | `TEXT` | Yes | - | Chunk anchor within file (e.g., `secrets-management-c0`) |
| `heading` | `TEXT` | Yes | `''` | Nearest parent heading for context |
| `chunk_text` | `TEXT` | Yes | - | Full text content of the chunk |
| `metadata_json` | `JSONB` | Yes | `'{}'` | Arbitrary metadata from front-matter or manifest |
| `content_hash` | `TEXT` | Yes | - | SHA-256 hash of chunk content for change detection |
| `embedding_model` | `TEXT` | Yes | `'nomic-embed-text'` | Model used to generate the embedding |
| `embedding_version` | `TEXT` | Yes | `'locked'` | Embedding version tag (for re-embedding tracking) |
| `embedding` | `vector(768)` | No | `NULL` | 768-dimensional embedding vector (pgvector) |
| `classification` | `TEXT` | Yes | `'internal'` | Data classification: `public` or `internal` |
| `created_at` | `TIMESTAMPTZ` | Yes | `now()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Yes | `now()` | Last update timestamp |

**Constraints:**
- `UNIQUE (repo, path, anchor, ref)` -- one chunk per position per ref

**Indexes:**
- `idx_chunks_embedding_hnsw` -- HNSW index on `embedding` using `vector_cosine_ops` for approximate nearest-neighbor search
- `idx_chunks_namespace_repo_ref` -- B-tree on `(namespace, repo, ref)` for filtered queries

---

## Table: `bundle_cache`

Cache for assembled context bundles.

| Column | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `BIGSERIAL` | Yes (PK) | auto | Internal surrogate key |
| `cache_key` | `TEXT` | Yes | - | SHA-256 hash of (namespace, repo, task_hash, ref, standards_version) |
| `bundle_json` | `JSONB` | Yes | - | Full bundle payload |
| `created_at` | `TIMESTAMPTZ` | Yes | `now()` | Cache entry creation time |
| `expires_at` | `TIMESTAMPTZ` | Yes | - | Expiration time (default TTL: 300 seconds) |

**Indexes:**
- `idx_bundle_cache_key` -- B-tree on `cache_key`
- `idx_bundle_cache_key_unique` -- Unique index on `cache_key` for upsert support

---

## Tenant Isolation Semantics

### `namespace` field

The `namespace` field provides logical tenant isolation at the data layer:

1. **Required on all records.** Every `memory_packs` and `memory_chunks` row MUST have a non-empty `namespace` value.
2. **Required in all queries.** Every search, resolve, and index operation MUST include a `namespace` filter. Queries without a namespace filter are rejected at the validation layer.
3. **Default value: `'default'`.** Single-tenant deployments use the default namespace. Multi-tenant deployments assign a unique namespace per tenant.
4. **Isolation guarantee:** No query can return chunks from a namespace other than the one specified in the request. This is enforced by the SQL WHERE clause in `search.py` and `resolve_context`.
5. **No cross-namespace operations.** There is no API that queries across multiple namespaces. Aggregation across namespaces requires separate queries.

### Deployment model

The current deployment model is **single-tenant with multi-tenant-capable schema**:
- One Postgres database serves one organization
- The `namespace` column and unique constraints are in place so that multi-tenant deployment requires no schema migration
- Multi-tenant deployment would add a namespace-routing layer at the Gateway, which is out of scope for Phase 0

---

## Provider-Specific Extension

The `metadata_json` JSONB column on `memory_chunks` serves as the escape hatch for provider-specific fields. Examples:

```json
{
  "ado_work_item_id": "12345",
  "ado_project": "MyProject",
  "github_issue_url": "https://github.com/org/repo/issues/42",
  "custom_tags": ["terraform", "networking"]
}
```

This field is not validated against a fixed schema. Consumers should treat unknown keys as opaque metadata.

---

## Embedding Specifications

| Property | Value |
|----------|-------|
| Model | `nomic-embed-text` |
| Dimensions | 768 |
| Storage | pgvector `vector(768)` |
| Index type | HNSW with `vector_cosine_ops` |
| Similarity metric | Cosine similarity (via `<=>` operator) |
| Normalization | Vectors are unit-normalized before storage; dot product approximates cosine |

---

## Change Detection

Chunks are identified by `(repo, path, anchor, ref)`. On re-indexing:

1. Compute SHA-256 hash of new chunk content
2. Compare to stored `content_hash`
3. If changed: delete old chunk, insert new chunk with updated embedding
4. If file deleted from disk: delete all chunks for that file path
5. File renames are treated as delete + add (no rename tracking)

All per-file operations (delete old + insert new) are wrapped in a single transaction.
