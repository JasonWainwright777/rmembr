# Tuning Guide

## Embedding Model Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_MODEL` | `nomic-embed-text` | Ollama model name |
| `EMBED_DIMS` | `768` | Vector dimensions |

**nomic-embed-text** (default) is a good general-purpose model:
- 768 dimensions, ~274M parameters
- Strong performance on retrieval benchmarks
- Runs well on CPU-only hosts via Ollama

**Alternatives to consider:**
- `mxbai-embed-large` — 1024 dims, slightly better accuracy, more compute
- `all-minilm` — 384 dims, faster, lower accuracy
- `snowflake-arctic-embed` — 768 dims, strong multilingual support

**Changing the model requires:**
1. Update `EMBED_MODEL` and `EMBED_DIMS` in `.env`
2. Update `embedding.model` and `embedding.dims` in every `manifest.yaml`
3. Update the `vector(768)` column definition in migrations if dims change
4. Re-pull the model: `docker compose exec ollama ollama pull <model>`
5. Reindex all repos: `python scripts/mcp-cli.py index-all`

Existing embeddings from a different model are not compatible — you must reindex.

## Chunk Size Tuning

Set in `services/shared/src/chunking/chunker.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_CHUNK_CHARS` | `2000` | Max characters per chunk (~500 tokens) |
| `MIN_CHUNK_CHARS` | `100` | Minimum chars; smaller chunks without headings are dropped |

**Trade-offs:**
- **Larger chunks** (3000-4000): more context per result, fewer chunks to search, but less precise retrieval and faster budget exhaustion
- **Smaller chunks** (500-1000): more precise retrieval, better budget utilization, but may lose cross-paragraph context
- **Default (2000)**: balanced for technical documentation with heading-delimited sections

**How chunking works:**
1. Splits on `##` and `###` headings
2. Sections exceeding `MAX_CHUNK_CHARS` are further split on paragraph boundaries (`\n\n`)
3. Each chunk's heading is prepended for embedding context
4. Content hash (SHA-256) enables incremental reindex — unchanged chunks are skipped

After changing chunk sizes, reindex all repos.

## Bundle Size Budget

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_MAX_BUNDLE_CHARS` | `40000` | Max total characters across all chunks in a bundle |

The gateway fills the bundle in priority order until the budget is exhausted:

1. Enterprise standards (must-follow) are included first
2. Repo must-follow chunks come next
3. Task-specific chunks fill the remaining budget
4. If a chunk would exceed the budget but at least 100 chars remain, it is truncated with `...(truncated)`

**Tuning considerations:**
- **LLM context window**: 40,000 chars ≈ 10,000 tokens — fits comfortably in a 32K-token context with room for the task prompt and response
- **Increase to 60,000-80,000** for models with 128K+ context windows
- **Decrease to 20,000** if using smaller models or if bundles include too much low-relevance content
- Standards content is capped at 2,000 characters per standard in markdown format
- At most 5 standards are fetched per bundle

## K Parameter Tuning

Two separate K values control how many chunks are retrieved:

| Context | Default | Range | Description |
|---------|---------|-------|-------------|
| `search` CLI | 8 | 1-100 | Results returned from a direct search |
| `get-bundle` / `GATEWAY_DEFAULT_K` | 12 | 1-100 | Chunks retrieved for bundle assembly |

**Guidelines:**
- **k=8** for search: good for quick lookups, returns top matches
- **k=12** for bundles: retrieves more candidates so priority filtering and budget packing have material to work with
- **k=20-30**: useful when `--changed-files` is set — the similarity boost may promote lower-ranked chunks
- **k>50**: rarely beneficial; diminishing returns and slower queries
- Higher K values increase query latency linearly (more vectors to score and return)

## Cache TTL Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `BUNDLE_CACHE_TTL_SECONDS` | `300` (5 min) | TTL for search-based bundle cache entries |
| Bundle record TTL | `86400` (24 hours) | TTL for `explain-bundle` records (not configurable) |

**Search bundle cache** (`BUNDLE_CACHE_TTL_SECONDS`):
- Cache key is a hash of `namespace:repo:task_hash:ref:standards_version`
- Same task query against the same repo returns cached result within TTL
- **Increase to 3600** (1 hour) if memory packs change infrequently
- **Decrease to 60** during active authoring when you're iterating on pack content
- Set to `0` to disable caching (every request hits the index)

**Bundle records** (24-hour TTL):
- Created when `get-bundle` runs; keyed as `bundle:<uuid>`
- Used by `explain-bundle` to retrieve previously assembled bundles
- Not configurable — designed to outlive a typical work session

Expired entries are filtered at query time (checked against `expires_at`).

## Database Pool Sizing

| Service | `min_size` | `max_size` | Description |
|---------|-----------|-----------|-------------|
| Index | 2 | 10 | Handles indexing (write-heavy) and search (read-heavy) |
| Gateway | 1 | 5 | Handles bundle cache reads/writes only |

**Tuning guidance:**
- **Index `max_size`**: increase if indexing multiple repos concurrently or if search latency degrades under load. Each concurrent index or search operation holds one connection.
- **Gateway `max_size`**: increase if serving many concurrent bundle requests. The gateway only touches the database for cache operations.
- **PostgreSQL `max_connections`**: ensure it exceeds the sum of all service pool `max_size` values (default: 15 total). PostgreSQL default is 100.
- Monitor with `SELECT count(*) FROM pg_stat_activity` to check actual connection usage.

## Network Timeouts

| Timeout | Value | Location | Description |
|---------|-------|----------|-------------|
| Proxy timeout | 120s | gateway `PROXY_TIMEOUT` | Gateway-to-internal-service timeout (hardcoded) |
| CLI timeout | 120s | mcp-cli.py `TIMEOUT` | CLI-to-gateway timeout (hardcoded) |
| Health check interval | 5s | docker-compose `healthcheck.interval` | Service health poll frequency |

**Why 120 seconds for proxy/CLI:**
- Initial indexing of a large repo can take 60-90 seconds due to embedding generation
- Ollama may need to load the model into memory on first request
- Subsequent requests are much faster (model stays loaded, unchanged chunks are skipped)

These timeouts are hardcoded. To change them, edit `PROXY_TIMEOUT` in `gateway/src/server.py` and `TIMEOUT` in `scripts/mcp-cli.py`.

## pgvector HNSW Index Performance

The `idx_chunks_embedding_hnsw` index uses HNSW (Hierarchical Navigable Small World) with cosine distance.

**Performance characteristics:**
- Sub-millisecond search up to ~100K vectors
- ~1-5ms search at ~1M vectors
- Index build time grows with dataset size (minutes for 1M vectors)
- Memory usage: roughly 1.5-2x the raw vector data size

**Scaling considerations at ~1M vectors:**
- HNSW parameters (`m`, `ef_construction`) use pgvector defaults — sufficient for most workloads
- If recall drops at scale, consider tuning `ef_search` at query time: `SET hnsw.ef_search = 100`
- The `idx_chunks_namespace_repo_ref` B-tree index enables filtered queries to scan fewer vectors
- Vacuum regularly: `VACUUM ANALYZE memory_chunks` to maintain index health

**When the current architecture is sufficient:**
- Up to ~1M total chunks across all repos (typical: 100-500 repos with 10-50 chunks each)
- Single-node PostgreSQL with adequate RAM for the HNSW index

## Scaling Boundaries

This system is designed for single-team or small-organization use. Consider alternatives when:

- **>1M vectors**: pgvector HNSW performance degrades; consider dedicated vector databases (Qdrant, Weaviate, Pinecone)
- **>100 concurrent users**: the single gateway becomes a bottleneck; add horizontal scaling with a load balancer
- **>10 repos indexing simultaneously**: Ollama embedding throughput and DB write contention may cause timeouts; consider GPU-accelerated Ollama or batched indexing
- **Multi-region**: the single PostgreSQL instance adds latency; consider read replicas or a distributed database
- **Real-time indexing**: the 3-second debounce and sequential processing in the file watcher may lag behind rapid changes; consider a message queue

## Priority Class Ordering

Priority classes determine the order in which chunks fill the bundle budget:

| Priority | Class | Source | Typical Content |
|----------|-------|--------|-----------------|
| 0 (highest) | `enterprise_must_follow` | Enterprise standards | Compliance rules, security policies |
| 1 | `repo_must_follow` | Repo memory (flagged) | Architecture decisions, coding standards |
| 2 (lowest) | `task_specific` | Repo memory (by similarity) | Contextually relevant documentation |

**How priority affects bundles:**
1. All retrieved chunks are tagged with their priority class
2. Chunks are sorted by priority (0 first), then by similarity score within each class
3. The character budget is consumed in order — higher priority chunks are always included before lower ones
4. If the budget is tight, lower-priority task-specific chunks get truncated or excluded

**Practical impact:**
- With the default 40,000 char budget, enterprise standards (typically 2-5 items at ~2,000 chars each) consume 10,000-10,000 chars
- Remaining ~30,000 chars go to repo memory chunks
- If enterprise standards are large, reduce their count in `references.standards` or increase the bundle budget
