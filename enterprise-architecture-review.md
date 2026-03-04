# Enterprise Architecture Review: MCP-Based Targeted Memory Service (Local POC)

**Reviewed:** 2026-03-04
**Artifact:** `local-docker-mcp-targeted-memory-implementation-plan.md`
**Perspective:** Enterprise Architect — assessing POC viability for enterprise promotion

---

## Scoring Summary

| Category | Score | Verdict |
|---|---|---|
| **Architectural Merit** | 8/10 | Strong layered design with clear boundaries |
| **Design Flaws** | 6/10 | Several gaps need addressing before enterprise promotion |
| **Security Posture** | 4/10 | Insufficient even for a POC that will inform prod design |
| **Long-Term Viability** | 7/10 | Good bones, but some decisions will create migration friction |
| **Enterprise Readiness (as POC)** | 7/10 | Proves the concept well; needs hardening items on the backlog |

---

## Architectural Merits

### Gateway-as-front-door pattern (8/10)

The single Gateway MCP exposing `get_context_bundle` as the primary interface is the right call. It cleanly separates orchestration from storage/retrieval and gives you a single control point for auth, logging, and rate limiting later. This maps directly to an Azure API Management or Application Gateway topology.

### Repo-first memory packs (9/10)

Using `manifest.yaml` as a declarative contract per repo is a strong design choice. It makes the system auditable, versionable, and gives repo owners agency. The `override_policy.allow_repo_overrides: false` field shows governance is being considered early.

### Bundle assembly with priority classes (8/10)

The precedence model (enterprise must-follow > repo must-follow > task-specific) with size budgets is exactly how context injection should work at scale. The 40/40/20 split is a reasonable starting heuristic.

### Service decomposition (7/10)

Three services + Postgres is appropriate granularity for a POC. The plan correctly notes Gateway calls Index/Standards over HTTP internally, avoiding premature MCP-to-MCP complexity.

---

## Design Flaws

### 1. No content versioning or cache invalidation strategy (5/10 severity)

The plan says `ref=local` for now and `commit_sha` later, but there's no mechanism for detecting stale embeddings. If someone edits a markdown file, the old chunks and embeddings persist until manual re-index. The `content_hash` field exists in the schema but there's no described workflow for using it for staleness detection or deduplication.

**Recommendation:** Even in the POC, implement hash-based upsert logic — compare `content_hash` before re-embedding. This validates the pattern needed in production pipelines.

### 2. Embedding model lock-in without migration path (6/10 severity)

The manifest locks `nomic-embed-text` at 768 dims, which is good for consistency. But there's no plan for what happens when a model change is needed. Re-embedding an entire corpus is expensive. The schema has no `embedding_model` column on `memory_chunks`, so two models can't run side-by-side during migration.

**Recommendation:** Add `embedding_model` and `embedding_version` columns to `memory_chunks`. This is cheap to add now and saves a painful migration later.

### 3. No observability or tracing (5/10 severity)

There's no mention of structured logging, request tracing, or metrics. For a POC meant to validate enterprise viability, the system needs to demonstrate operability. Bundle assembly involves multiple service calls — without trace IDs, debugging will be painful even locally.

**Recommendation:** Add OpenTelemetry trace propagation between services. Even a simple `X-Request-ID` header passed through Gateway → Index → Standards would suffice for POC.

### 4. Bundle determinism is underspecified (4/10 severity)

The plan claims "deterministic, usable context bundle" as a Phase 4 exit criterion, but vector similarity search is inherently non-deterministic (floating point, index ordering). The bundle algorithm doesn't describe tie-breaking or stable sorting.

**Recommendation:** Define explicit tie-breaking rules (e.g., prefer higher priority class, then alphabetical by path). Document what "deterministic" means in this context — same query + same corpus = same bundle, or something weaker.

### 5. Shared library coupling (3/10 severity)

The plan proposes a single shared library for chunking, manifest parsing, IDs, and bundle assembly. This is fine for the POC but creates a deployment coupling risk — any change to chunking logic forces redeployment of all three services.

**Recommendation:** Keep the shared lib but version it. In the POC, pin a version in each service's `pyproject.toml` rather than using path dependencies.

---

## Security Issues

### 1. Plaintext credentials in `.env` (7/10 severity)

`POSTGRES_PASSWORD=memory_pw` in a committed `.env` file is a pattern that migrates poorly. Developers will copy-paste this into Azure deployments. The plan doesn't mention `.gitignore` or secret management.

**Recommendation:** Add `.env` to `.gitignore` immediately. Ship a `.env.example` with placeholder values. Document that Azure migration uses Key Vault / managed identity. This costs nothing and prevents bad habits.

### 2. No input validation on MCP tool parameters (6/10 severity)

The tool contracts accept `repo: str`, `query: str`, `filters?: dict` with no described validation. In the Index service, `repo` likely maps to a filesystem path (`repos/<repo>/.ai/memory/`). Without validation, this is a path traversal vector: `repo=../../etc` could read arbitrary files.

**Recommendation:** Validate `repo` against a whitelist of known repos (from `memory_packs` table or a config list). Validate `query` length. Validate `filters` schema. Do this in the POC — it's where validation patterns for production are established.

### 3. No TLS between services (4/10 severity for POC)

All inter-service communication is plaintext HTTP on a Docker network. Acceptable for local dev, but the migration notes don't mention TLS or mTLS as a requirement for Azure.

**Recommendation:** Add to migration notes: "Enable mTLS between Gateway, Index, and Standards services via Azure Private Endpoints or service mesh." This ensures the architecture review doesn't lose this requirement.

### 4. Gateway is the only auth boundary (5/10 severity)

The plan says Gateway is the "only externally exposed port" — but if any service is accidentally exposed (misconfigured Docker publish, port mapping error), Index and Standards have zero authentication. Defense in depth is missing.

**Recommendation:** Even for POC, add a simple shared-secret header check on Index and Standards. This validates the pattern and catches misconfiguration.

### 5. No data classification enforcement (5/10 severity)

The manifest has a `classification: internal` field, but nothing in the architecture enforces it. There's no described mechanism to prevent a `confidential` chunk from appearing in a bundle served to an unauthorized consumer.

**Recommendation:** At minimum, have the Gateway check `classification` against the `persona` parameter and filter accordingly. This is a critical enterprise requirement to prototype early.

---

## Long-Term Issues

### 1. pgvector scaling limits (6/10 severity)

pgvector works well up to ~1M vectors. Enterprise-scale with hundreds of repos, thousands of documents, and multiple embedding versions could exceed this. The plan doesn't discuss indexing strategy (IVFFlat vs HNSW) or partitioning.

**Recommendation:** Use HNSW indexes in the POC (better recall, acceptable build time at small scale). Document the scaling boundary and identify Azure Cognitive Search or a dedicated vector DB as the enterprise alternative if needed.

### 2. No multi-tenancy model (7/10 severity)

The current design assumes a single tenant. In an enterprise, there will be multiple teams, projects, and security boundaries. There's no `tenant_id`, no row-level security, no scoping of search results by access control.

**Recommendation:** Add a `namespace` or `tenant` column to `memory_chunks` and `memory_packs` now. Even if only one value is used in the POC, the schema is ready.

### 3. No bundle caching or idempotency (5/10 severity)

Every `get_context_bundle` call runs the full pipeline: embed query → vector search → fetch standards → assemble. At enterprise scale with agents making repeated similar queries, this is wasteful. There's no caching layer or bundle deduplication.

**Recommendation:** Add a `bundle_cache` table keyed on `(repo, task_hash, ref, standards_version)` with a TTL. Prototype this in Phase 4.

### 4. Embedding provider as single point of failure (4/10 severity)

If Ollama goes down, the entire Index service is non-functional — not just ingestion, but any query that needs to embed the search query. There's no fallback or graceful degradation.

**Recommendation:** Separate the embedding dependency for ingestion (can fail and retry) from query-time embedding (needs a fallback or pre-computed query cache).

### 5. Standards versioning is underspecified (5/10 severity)

The plan uses `version=local` for standards but doesn't describe how versioned standards coexist. When enterprise standards change (e.g., Terraform module versioning v3 → v4), repos pinned to v3 need to keep getting v3 content. The `get_standard(id, version)` API exists but the storage and resolution mechanism isn't described.

**Recommendation:** Define how standards versions map to Git tags or directory structures. Prototype at least two versions of one standard to validate the resolution logic.

---

## Verdict

**This is a strong POC design that validates the core architectural thesis:** a Gateway-orchestrated, repo-first memory system with semantic search and standards enforcement is viable and maps well to Azure private network deployment.

**The primary risks for enterprise promotion are:**

1. **Security patterns are too relaxed** — even for a POC, the auth/classification enforcement patterns needed in production should be validated
2. **The embedding model migration story is missing** — this will bite hard at scale
3. **Multi-tenancy isn't even stubbed** — retrofitting tenant isolation is one of the most expensive architectural changes

### Recommended Pre-Code Additions to Phase 1

Before writing code, add three items to Phase 1:

- **Input validation** on all tool parameters (especially `repo`)
- **`embedding_model` column** on `memory_chunks`
- **`namespace` column** on both tables

These are low-cost additions that dramatically reduce future migration risk.
