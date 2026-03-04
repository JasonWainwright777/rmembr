# Enterprise Architecture Review v1 — MCP-Based Targeted Memory Service (Local POC)

**Review Date:** 2026-03-04
**Reviewer Role:** Enterprise Architect
**Artifact Reviewed:** `local-docker-mcp-targeted-memory-implementation-plan.md`
**Review Scope:** Evaluate the local Docker POC for enterprise viability — merits, design flaws, security issues, and long-term risks. Scoring is calibrated for a POC that must demonstrate enterprise-grade patterns, not production hardness.

---

## Scoring Summary

| Category | Score (1–10) | Verdict |
|---|---|---|
| **Architectural Merits** | 8 | Strong foundation with clean separation of concerns |
| **Design Flaws** | 7 | Mostly sound; several gaps need attention before Azure migration |
| **Security Posture** | 7 | Good for a POC; critical gaps remain for enterprise promotion |
| **Long-Term Viability** | 7 | Solid migration path outlined; some structural risks if left unaddressed |
| **Overall Enterprise Readiness** | 7.3 | Viable POC — demonstrates enterprise patterns well, with actionable gaps |

---

## 1. Architectural Merits — Score: 8/10

### What the plan gets right

**1.1 Clean Service Decomposition**
The Gateway / Index / Standards three-service split is well-chosen. Each service has a single responsibility, and the Gateway acting as the sole client-facing entry point is a correct enterprise pattern. This maps cleanly to Azure Container Apps or AKS with an internal ingress controller.

**1.2 Repo-First Memory Packs as Source of Truth**
Anchoring all memory content to versioned repos (simulated locally, real ADO repos later) is architecturally sound. The system never becomes the authoritative store — it is always a derived index. This eliminates an entire class of data-integrity and backup concerns. The `manifest.yaml` contract is well-structured with namespace, classification, and embedding metadata.

**1.3 Content-Hash Upsert (Section 4.3)**
The SHA-256 content-hash deduplication is an excellent pattern. It prevents unnecessary embedding calls (cost savings at scale), enables incremental re-indexing, and validates the production pipeline pattern early. The inclusion of stale-row deletion completes the lifecycle.

**1.4 Deterministic Bundle Assembly (Section 10.1, 10.3)**
The explicit tie-breaking sort (priority class > similarity score > path alphabetical) and the formal definition of determinism are strong enterprise patterns. Reproducible outputs are essential for audit trails and debugging. Few POCs get this right.

**1.5 Observability from Day One (Section 6.3)**
Structured JSON logging, `X-Request-ID` propagation, and health endpoints with dependency checks are included in Phase 1. This is the correct sequencing — retrofitting observability is far more expensive than building it in.

**1.6 Namespace-Based Multi-Tenancy**
The `namespace` column on all core tables, defaulting to `"default"`, is a lightweight but effective multi-tenancy pattern. It will map cleanly to Azure tenant/team boundaries without schema changes.

**1.7 Phased Build Plan**
The five-phase plan is realistic and well-sequenced. Dependencies flow correctly (Postgres first, then Standards, then Index, then Gateway, then DX). Exit criteria are defined for each phase.

### What elevates it

- The plan explicitly documents scaling boundaries (pgvector ~1M vectors) rather than hand-waving.
- Migration notes (Section 15) are concrete and actionable, not aspirational.
- Test scenarios (Section 13) cover happy path, security (path traversal), caching, and classification — good breadth for a POC.

---

## 2. Design Flaws — Score: 7/10

### 2.1 No Schema Migration Strategy — Risk: Medium

**Issue:** Section 4.1 mentions "Create extension + tables at Index startup migration" but does not specify a migration tool or versioning strategy. Running raw DDL at service startup is fragile — if a migration fails mid-way, the service enters an undefined state.

**Impact:** At POC scale this is tolerable. At enterprise scale with multiple environments (dev/staging/prod), unversioned migrations cause deployment failures and data corruption.

**Recommendation:** Use Alembic (Python ecosystem) or a similar migration tool. Version each migration. Run migrations as a separate init container or startup step, not interleaved with application boot. This is a small lift now that prevents significant pain later.

### 2.2 Shared Library as Path Dependency — Risk: Medium

**Issue:** Section 6.1 states the shared library is a path dependency with "explicit version constraint." In practice, Python path dependencies in `pyproject.toml` do not enforce version constraints the way published packages do. A developer changing `services/shared/` affects all services immediately regardless of the version pin.

**Impact:** The plan intends to prevent silent coupling but the mechanism does not actually enforce it in a monorepo with path dependencies.

**Recommendation:** Either (a) accept the coupling for the POC and document it as a known limitation, or (b) use a local package registry or `pip install -e ./shared[==0.1.0]` with CI checks that verify the declared version matches `shared/pyproject.toml`. For the POC, option (a) is pragmatic — but flag this for Azure migration where the shared library should be a proper internal package.

### 2.3 No Rate Limiting or Backpressure — Risk: Low (POC) / High (Enterprise)

**Issue:** The Gateway exposes a host port and accepts unbounded requests. There is no mention of rate limiting, request queuing, or backpressure on the embedding pipeline.

**Impact:** In the POC, a single developer won't overload the system. In enterprise deployment, a misconfigured CI pipeline or aggressive agent could saturate Ollama/embedding service and degrade all users.

**Recommendation:** Document this as a known gap. For the POC, add a simple semaphore or concurrency limit on `index_repo` / `index_all` calls. For Azure, use API Management or Azure Front Door rate limiting.

### 2.4 Bundle Cache Invalidation is Incomplete — Risk: Medium

**Issue:** Section 10.1 implements TTL-based cache expiry (default 5 minutes). However, the cache key is `(namespace, repo, task_hash, ref, standards_version)`. If a repo is re-indexed (new content) but `ref` remains `"local"`, the cache will serve stale bundles until TTL expires.

**Impact:** During active development, a user re-indexes a repo and immediately queries the Gateway — they get the old bundle for up to 5 minutes. This is confusing and will erode trust in the system.

**Recommendation:** Add an explicit cache-bust mechanism: either (a) `index_repo` returns a new `ref` token that changes on each indexing run and the Gateway incorporates it into the cache key, or (b) `index_repo` invalidates relevant cache entries directly. Option (b) is simpler for the POC.

### 2.5 No Graceful Degradation When Standards Service is Down — Risk: Low

**Issue:** The Gateway calls both Index and Standards to assemble a bundle. If Standards is unreachable, the behavior is unspecified. Does the Gateway return an error? Return a partial bundle? Timeout?

**Impact:** In a POC this is minor. In enterprise, the Standards service being unavailable should not prevent all context retrieval.

**Recommendation:** Define the failure mode explicitly. Suggested: Gateway returns a partial bundle with a `warnings` field indicating Standards was unreachable. Include a `degraded: true` flag so consumers know the bundle is incomplete.

### 2.6 `task_hash` in Cache Key is Undefined — Risk: Low

**Issue:** The bundle cache key includes `task_hash` but the plan does not specify how `task` (a free-text string) is hashed. Different hashing approaches (exact string hash vs. semantic hash) produce very different cache hit rates.

**Recommendation:** For the POC, use SHA-256 of the raw `task` string. Document that this means semantically identical but lexically different queries will miss the cache. Semantic deduplication is a future optimization.

---

## 3. Security Posture — Score: 7/10

### 3.1 Input Validation is Well-Designed — Strength

Section 5.0 is thorough: repo whitelist, path traversal prevention, query length limits, filter schema validation, and regex-based ID validation. Implementing this as shared middleware is correct. Test scenario F (path traversal) validates this. This is above-average for a POC.

### 3.2 Inter-Service Auth is Present but Weak — Risk: Medium

**Issue:** A single shared secret (`X-Internal-Token`) is used for all inter-service communication. This is better than nothing (and catches accidental port exposure), but:
- The token is static and stored in `.env`
- There is no token rotation mechanism
- All services share the same token (no service-specific identity)
- No replay protection

**Impact:** For a local POC behind Docker networking, this is adequate. The risk is that this pattern gets carried into Azure without upgrading to Managed Identity / mTLS.

**Recommendation:** Acceptable for POC. Ensure the migration notes (Section 15) explicitly flag this as "must replace" rather than "nice to have." Consider adding a comment in `.env.example`: `# DO NOT use shared secrets in production — use Entra ID managed identities`.

### 3.3 No TLS on Internal Traffic — Risk: Low (POC) / High (Enterprise)

**Issue:** All inter-service calls are plain HTTP on the Docker network. This is standard for local Docker development but becomes a compliance violation in enterprise environments (SOC2, HIPAA, etc.).

**Impact:** Section 15 mentions mTLS for Azure migration. The risk is that the migration underestimates the effort — mTLS requires certificate management, rotation, and service mesh configuration.

**Recommendation:** Acceptable for POC. Consider adding a `# TLS` section to the migration notes that estimates the effort and identifies Azure Private Endpoints as the simplest path (avoids self-managed mTLS).

### 3.4 Classification Enforcement is Persona-Based, Not Identity-Based — Risk: Medium

**Issue:** Section 11.4 enforces classification based on a `persona` string parameter passed by the caller. There is no authentication of the caller's identity — anyone who can reach the Gateway can claim any persona.

**Impact:** In the POC (single developer), this is fine. In enterprise, this is a data exfiltration vector: an attacker (or misconfigured agent) passes `persona=human` and retrieves `internal` content they should not see.

**Recommendation:** Document this as a "POC simplification" that must be replaced by Entra ID token-based identity before Azure deployment. The Gateway must extract the caller's identity from an auth token, resolve their group memberships, and map to classification levels server-side — never trust the client-supplied persona.

### 3.5 No Audit Logging — Risk: Medium

**Issue:** The plan includes structured logging (Section 6.3) but does not mention audit logging — who accessed what data, when, and with what persona/classification level.

**Impact:** In enterprise environments, especially those handling `confidential` classified content, audit trails are a compliance requirement. Retrofitting audit logging is expensive because it requires understanding every data access path.

**Recommendation:** Add a lightweight audit log for the POC: log every `get_context_bundle` call with `(timestamp, request_id, namespace, repo, persona, classification_level_applied, chunks_returned_count)`. This validates the pattern and provides debugging value even locally.

### 3.6 Postgres Credentials in Plaintext .env — Risk: Low (POC)

**Issue:** `POSTGRES_PASSWORD=CHANGE_ME` in `.env.example` is fine, but there is no mechanism to verify that developers actually change it.

**Recommendation:** Add a startup check in the Index service that rejects `CHANGE_ME` as a password value with a clear error message. This is a 5-line check that prevents a real mistake.

---

## 4. Long-Term Issues — Score: 7/10

### 4.1 Embedding Model Lock-In — Risk: Medium

**Issue:** The plan stores `embedding_model` and `embedding_version` per chunk (Section 4.1), which is excellent. However, there is no described process for migrating from one embedding model to another. When `nomic-embed-text` is superseded, all existing vectors become incompatible with queries embedded by the new model.

**Impact:** At enterprise scale (hundreds of repos, millions of chunks), re-embedding the entire corpus is expensive and time-consuming. Without a migration strategy, teams will defer the upgrade indefinitely, leading to degraded search quality.

**Recommendation:** Document a model migration strategy now, even if it is not implemented in the POC:
1. Ingest new content with the new model in parallel (dual-write to a new embedding column or separate table).
2. Backfill existing chunks in batches.
3. Switch query-time embedding to the new model.
4. Drop the old embedding column after validation.

The `embedding_model` column already supports querying by model — this is the foundation for the migration path.

### 4.2 pgvector Scaling Ceiling — Risk: Medium

**Issue:** The plan correctly identifies the ~1M vector ceiling for pgvector with HNSW (Section 4.1). For a large enterprise with hundreds of repos and years of accumulated content, this ceiling is reachable.

**Impact:** Migration from pgvector to Azure AI Search or a dedicated vector DB is significant effort — different query APIs, different indexing pipelines, different operational model.

**Recommendation:** The Index service's search abstraction should be documented as the migration boundary — any vector DB migration replaces the Index service internals only. This is implicitly true but should be made explicit in an architecture decision record (ADR).

### 4.3 Monorepo vs. Polyrepo Tension — Risk: Low

**Issue:** The plan uses a monorepo layout (`services/shared/`, `services/index/`, etc.) with a shared library as a path dependency. This works for a POC but creates challenges in enterprise CI/CD: a change to `shared/` triggers rebuilds of all services, and independent service versioning becomes difficult.

**Impact:** If the team grows beyond 2-3 developers, the monorepo coupling slows velocity and increases blast radius of changes.

**Recommendation:** Acceptable for POC. For Azure migration, evaluate splitting into separate repos per service with the shared library published as an internal package (Azure Artifacts feed).

### 4.4 No Backup or Recovery Strategy — Risk: Low (POC) / High (Enterprise)

**Issue:** Postgres data lives in `./data/pg/` with no backup mechanism. The plan correctly positions repos as the source of truth (so the index is rebuildable), but `bundle_cache` and `memory_packs` metadata would be lost.

**Impact:** In the POC, losing data means re-running `index_all`. In enterprise, losing the index during a deployment means degraded service until re-indexing completes (which could take hours at scale).

**Recommendation:** For the POC, document that the data is rebuildable and the recovery procedure is `index_all`. For Azure, ensure the migration plan includes Azure Database for PostgreSQL automated backups and point-in-time restore.

### 4.5 Standards Versioning Strategy is Underspecified — Risk: Medium

**Issue:** Section 12 Phase 2 says "map version param to directory structure or Git tags" but does not commit to one approach. These have very different operational models (tag-based requires checkout mechanics; directory-based requires content duplication).

**Impact:** If the POC uses directory-based versioning but Azure uses Git-tag-based versioning, the Standards service internals change substantially during migration.

**Recommendation:** Choose one strategy now and implement it in the POC. Git-tag-based versioning is more enterprise-aligned but harder locally. Directory-based is simpler for POC but should be documented as a "local simplification" with a concrete migration path.

### 4.6 No API Versioning on MCP Tools — Risk: Medium

**Issue:** The MCP tool contracts (Section 5) have no versioning scheme. If `get_context_bundle` needs a breaking change (e.g., adding a required parameter, changing the return schema), all consumers break simultaneously.

**Impact:** Once agents and pipelines depend on these tool contracts, breaking changes require coordinated rollouts across all consumers.

**Recommendation:** Add a `version` or `api_version` parameter to each tool (defaulting to `"v1"`). Alternatively, version the tool names themselves (e.g., `get_context_bundle_v1`). Align with MCP protocol versioning conventions if they exist.

---

## 5. Additional Observations

### 5.1 The Plan Has Already Been Iterated — Positive Signal

Appendix C shows this plan incorporates findings from a prior architecture review. The traceability table mapping findings to sections is a strong governance practice. This indicates the team is receptive to architectural feedback — a cultural positive for enterprise adoption.

### 5.2 The "Persona" Abstraction Has Legs

The human/agent/external persona model is simple but extensible. In enterprise, this maps naturally to Entra ID groups, service principal types, and external partner access tiers.

### 5.3 Missing: Load/Performance Testing Plan

The POC should include at least a basic performance baseline: how long does `index_repo` take for a 50-file repo? How long does `get_context_bundle` take end-to-end? These numbers inform capacity planning for Azure. Add a "Phase 5.5" or extend Phase 5 to include basic timing benchmarks.

### 5.4 Missing: Error Contract Standardization

The plan defines input validation (Section 5.0) but does not specify a standard error response format. All services should return errors in a consistent structure (e.g., `{ "error": { "code": "VALIDATION_ERROR", "message": "...", "request_id": "..." } }`). Trivial to add now, painful to retrofit.

---

## 6. Consolidated Risk Matrix

| ID | Risk | Severity (POC) | Severity (Enterprise) | Mitigation Status |
|---|---|---|---|---|
| D-1 | No schema migration tool | Low | High | Not addressed |
| D-2 | Shared lib version pin unenforced | Low | Medium | Acknowledged in plan |
| D-3 | No rate limiting | Low | High | Not addressed |
| D-4 | Stale cache after re-index | Medium | Medium | Not addressed |
| D-5 | No graceful degradation | Low | Medium | Not addressed |
| D-6 | task_hash undefined | Low | Low | Not addressed |
| S-1 | Static shared secret auth | Low | High | Migration notes mention Entra ID |
| S-2 | No TLS internally | Low | High | Migration notes mention mTLS |
| S-3 | Client-supplied persona trust | Low | Critical | Not explicitly flagged |
| S-4 | No audit logging | Low | High | Not addressed |
| S-5 | Default credential check missing | Low | Low | Not addressed |
| L-1 | Embedding model migration | Low | High | Columns exist; process undefined |
| L-2 | pgvector scaling ceiling | Low | Medium | Documented boundary |
| L-3 | Monorepo coupling | Low | Medium | Not addressed |
| L-4 | Standards versioning uncommitted | Low | Medium | Deferred |
| L-5 | No API versioning on tools | Low | High | Not addressed |
| L-6 | No backup/recovery strategy | Low | High | Implicitly rebuildable |

---

## 7. Verdict

**This POC is enterprise-worthy as a proof of concept.** The architecture demonstrates the right patterns: service decomposition, source-of-truth in repos, deterministic output, content-hash deduplication, classification enforcement, namespace-based multi-tenancy, and observability from day one. These are not trivial to get right, and the plan gets them right.

The gaps identified (schema migrations, cache invalidation, audit logging, API versioning, persona authentication) are all addressable without architectural rework. None require redesigning the service boundaries, data model, or interaction patterns. This is the hallmark of a sound architecture — the skeleton is correct, and the gaps are flesh that can be added incrementally.

### Priority Actions Before Declaring POC Complete

| Priority | Item | Effort |
|---|---|---|
| **P1** | D-4: Cache invalidation on re-index | Small — add cache-bust to `index_repo` |
| **P1** | S-3: Document persona trust limitation explicitly | Trivial — add to migration notes |
| **P1** | S-4: Add audit logging on `get_context_bundle` | Small — structured log entry |
| **P2** | L-5: Add API versioning to tool contracts | Small — default `v1` parameter |
| **P2** | D-1: Adopt Alembic for schema migrations | Medium — but prevents future pain |
| **P2** | 5.4: Standardize error response format | Small — shared middleware |
| **P3** | D-3: Add concurrency limit on ingestion | Small — semaphore |
| **P3** | 5.3: Add basic performance benchmarks | Medium — timing harness |

### Bottom Line

**Proceed with implementation.** The architecture is sound, the migration path to Azure is credible, and the identified gaps are tactical, not structural. Address P1 items before declaring the POC complete. P2/P3 items can be backlogged for the Azure migration phase.

---

*Review conducted against the plan artifact dated 2026-03-04. Scoring reflects POC context — enterprise deployment scores would shift downward until the identified gaps are closed.*
