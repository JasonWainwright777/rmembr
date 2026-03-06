# Local Docker Implementation Plan — MCP-Based Targeted Memory (Gateway + Index + Standards)

**Generated:** 2026-03-04T18:29:17.371387 UTC
**Updated:** 2026-03-04 — Incorporates findings from `enterprise-architecture-review.md`
**Goal:** Build the full **Gateway MCP + Index (Postgres/pgvector) + Standards MCP** stack **locally in Docker** for rapid prototyping, with a clear path to later deployment in Azure private networks.

This plan assumes:
- You want **one MCP "front door"** (Gateway) that produces **Context Bundles**
- You want **two backend MCP services** (Index + Standards) initially, but you can also run them as internal HTTP services behind the Gateway
- You want **repo-first memory packs** as the source of truth (local folders simulating ADO repos)

---

## 0) What You Will Run Locally

### Containers
1. **Postgres + pgvector** — stores chunk embeddings + metadata
2. **Index Service** — ingests markdown, chunks, embeds, and queries pgvector (exposes MCP tools)
3. **Standards Service** — serves canonical standards content (exposes MCP tools)
4. **Gateway Service** — orchestrates Index + Standards and returns a context bundle (exposes MCP tools)

### Optional Local Dependencies (choose one)
- **Local embeddings** via **Ollama** (recommended for "local-first")
  - Can run as a container or on host
- Alternative: local embeddings library (e.g., sentence-transformers) inside the Index container
  (less "enterprise local" but reduces moving parts)

---

## 1) Local Directory Layout

Create a top-level workspace:

```
mcp-memory-local/
  docker-compose.yml
  .env.example              # committed — placeholder values only
  .env                      # git-ignored — real local values
  .gitignore                # must include .env, data/pg/
  services/
    shared/                 # versioned shared library
      pyproject.toml        # pinned version (e.g., 0.1.0)
      src/
        chunking/
        manifest/
        ids/
        validation/
    index/
      Dockerfile
      pyproject.toml        # pins shared lib version
      src/
    standards/
      Dockerfile
      pyproject.toml        # pins shared lib version
      src/
    gateway/
      Dockerfile
      pyproject.toml        # pins shared lib version
      src/
  data/
    pg/
  repos/
    enterprise-standards/          # central repo (local simulation)
      .ai/memory/...
    sample-repo-a/                 # repo A
      .ai/memory/...
    sample-repo-b/                 # repo B
      .ai/memory/...
```

> Later in Azure DevOps, `repos/` is replaced by real repo checkouts in pipelines.

### .gitignore (required)
```
.env
data/pg/
__pycache__/
*.pyc
```

---

## 2) Memory Pack Conventions (Local Simulation)

Each repo should contain:

```
<repo>/
  .ai/
    memory/
      README.md
      manifest.yaml
      instructions.md
      schemas/
      runbooks/
      repo-skills/
```

### manifest.yaml minimal contract
```yaml
pack_version: 1
scope:
  repo: sample-repo-a
  namespace: default            # multi-tenancy — scopes all chunks/packs
owners:
  - platform-architecture
required_files:
  - instructions.md
classification: internal        # enforced at Gateway bundle assembly
embedding:
  model: nomic-embed-text
  dims: 768
  version: locked
references:
  standards:
    - enterprise/ado/pipelines/job-templates-v3
    - enterprise/terraform/module-versioning
override_policy:
  allow_repo_overrides: false
```

---

## 3) Docker Compose (Local Stack)

### 3.1 docker-compose.yml (recommended baseline)
- Postgres with pgvector enabled
- Index, Standards, Gateway services
- Optional Ollama container

Key points:
- Put all services on the same Docker network
- Persist Postgres data in `./data/pg`
- **Only Gateway exposes a host port** — Index and Standards bind to the internal Docker network only

**Compose responsibilities**
- Postgres: store vectors + metadata
- Index: ingest/query
- Standards: serve canonical docs (from `repos/enterprise-standards`)
- Gateway: orchestrate and build bundles

> You can run the Standards service as "read-only file server + MCP tools" for now.

---

## 4) Data Model (Local MVP)

### 4.1 Postgres schema (minimum)
Create extension + tables at Index startup migration.

**Extensions**
- `CREATE EXTENSION IF NOT EXISTS vector;`

**Tables**
- `memory_chunks`
  - id (PK)
  - namespace: tenant/team scope (default: `"default"`)
  - source_kind: repo_memory | enterprise_standard
  - repo: repo name
  - ref_type/ref: for local, use `branch=local` or `commit=dev`
  - path, anchor, heading
  - chunk_text, metadata_json, content_hash
  - embedding_model: model name used to generate this embedding (e.g., `nomic-embed-text`)
  - embedding_version: model version or checkpoint identifier
  - embedding vector(768)
  - classification: mirrors manifest classification (e.g., `internal`, `confidential`)
  - created_at, updated_at

- `memory_packs`
  - id (PK)
  - namespace: tenant/team scope (default: `"default"`)
  - repo, pack_version, owners, classification, embedding_model, last_indexed_ref
  - created_at, updated_at

- `bundle_cache` (Phase 4)
  - id (PK)
  - cache_key: hash of `(namespace, repo, task_hash, ref, standards_version)`
  - bundle_json
  - created_at
  - expires_at (TTL-based expiry)

**Indexes**
- HNSW index on `memory_chunks.embedding` for vector similarity (better recall than IVFFlat, acceptable build time at POC scale)
- B-tree index on `(namespace, repo, ref)` for filtered queries
- B-tree index on `bundle_cache.cache_key` with partial index on `expires_at > now()`

> **Scaling note:** pgvector with HNSW performs well up to ~1M vectors. For enterprise scale beyond this, evaluate Azure AI Search or a dedicated vector database. Document this boundary explicitly.

### 4.2 Determinism Locally
For local prototyping, use:
- `ref_type = "branch"` and `ref = "local"`
Later replace with real `commit_sha` from ADO.

### 4.3 Content-Hash Upsert Logic
During ingestion, the Index service must:
1. Compute `content_hash` (SHA-256 of `chunk_text`)
2. Check if a chunk with the same `(repo, path, anchor, ref)` already exists
3. **If `content_hash` matches** — skip re-embedding (no-op)
4. **If `content_hash` differs** — re-embed and upsert
5. **If chunk no longer exists in source** — delete the stale row

This validates the incremental re-indexing pattern required in production pipelines and avoids unnecessary embedding calls.

---

## 5) Service Contracts (MCP Tools)

### 5.0 Input Validation (All Services)

Every tool must validate inputs before processing:

- **`repo`**: Validate against a whitelist of known repos (loaded from `memory_packs` table or a config allowlist). Reject any value containing path traversal characters (`..`, `/`, `\`). This prevents directory traversal attacks where `repo=../../etc` could read arbitrary files.
- **`query`**: Enforce maximum length (e.g., 2000 characters). Reject empty strings.
- **`k`**: Enforce range (1–100).
- **`filters`**: Validate against a known schema of allowed filter keys and value types. Reject unknown keys.
- **`id` (standards)**: Validate against path-based ID pattern (`^[a-z0-9\-]+(/[a-z0-9\-]+)*$`).
- **`namespace`**: Validate against allowlist. Default to `"default"` if omitted.

Implement validation as a shared middleware/decorator in the shared library so all services enforce the same rules consistently.

### 5.1 Index MCP tools (MVP)
- `index_repo(repo: str, ref: str = "local") -> {indexed_files, chunks, skipped_unchanged}`
- `index_all(ref: str = "local") -> {repos_indexed, chunks, skipped_unchanged}`
- `search_repo_memory(repo: str, query: str, k: int = 8, ref: str = "local", namespace: str = "default", filters?: dict) -> results[]`
- `resolve_context(repo: str, task: str, k: int = 12, ref: str = "local", namespace: str = "default", changed_files?: list[str]) -> pointers[]`
- `health()`

### 5.2 Standards MCP tools (MVP)
- `get_standard(id: str, version: str = "local") -> markdown`
- `list_standards(domain?: str, version: str = "local") -> list`
- `get_schema(id: str, version: str = "local") -> json/yaml`
- `health()`

### 5.3 Gateway MCP tools (MVP)
- `get_context_bundle(repo: str, task: str, persona: str = "human", k: int = 12, ref: str = "local", namespace: str = "default", standards_version: str = "local", changed_files?: list[str], filters?: dict) -> bundle`
- `explain_context_bundle(bundle_id: str) -> explanation`
- `validate_pack(repo: str, ref: str = "local") -> validation_report`
- `health()`

---

## 6) Implementation Approach (Local-First)

### 6.1 Language / Framework
Pick one for speed:
- **Python** for all services (fast iteration, good embedding ecosystem)
- Use a **versioned shared library** (`services/shared/`) for:
  - chunking
  - manifest parsing
  - canonical IDs and anchors
  - bundle assembly logic
  - input validation middleware

**Pin the shared library version** in each service's `pyproject.toml` (e.g., as a path dependency with explicit version constraint). This prevents a change in chunking logic from silently affecting all services — each service opts in to shared library updates by bumping its pin.

### 6.2 MCP Server Implementation
- Use your chosen MCP SDK (the same one you intend to use later)
- Each service exposes MCP tools and calls other services over HTTP (or MCP client-to-MCP server calls)

Local simplification:
- Gateway calls Index/Standards via internal HTTP endpoints, even if they also expose MCP
- This avoids "MCP-to-MCP" complexity until needed

### 6.3 Observability

All services must implement structured logging and request tracing from day one:

- **Request tracing**: Gateway generates an `X-Request-ID` (UUID) for each inbound call and propagates it to Index and Standards via HTTP headers. All log lines include this ID.
- **Structured logging**: Use JSON-formatted logs with fields: `timestamp`, `service`, `request_id`, `tool`, `level`, `message`, `duration_ms`.
- **Health endpoints**: Already planned — extend to include dependency status (e.g., Postgres connectivity, Ollama reachability).

> For the POC, this is sufficient. In Azure, replace with OpenTelemetry SDK exporting to Azure Monitor / Application Insights.

---

## 7) Embeddings (Local)

### Option A (Recommended): Ollama + nomic-embed-text
- Run Ollama on host or in container
- Index service calls Ollama's embed endpoint

Pros:
- Mirrors your original local-first approach
- Keeps model execution out of your Python containers

Cons:
- One more runtime dependency
- Single point of failure (see resilience section below)

### Option B: In-container embedding library
- Use sentence-transformers (or similar)

Pros:
- Fewer moving parts
Cons:
- Less aligned with "local inference service" pattern

**Recommendation:** start with Option A for parity with future "private network inference" patterns.

### 7.1 Embedding Resilience

Separate the embedding dependency by usage:

- **Ingestion (batch)**: If Ollama is unreachable, fail the ingestion job with a clear error and allow retry. Do not block the service from starting.
- **Query-time (interactive)**: If Ollama is unreachable, return an error to the caller with a descriptive message (`embedding_service_unavailable`). Do not silently return empty results.

> Future enhancement: implement a query embedding cache (LRU or Redis-backed) so repeated identical queries don't require Ollama. This is optional for the POC but valuable at scale.

---

## 8) Chunking + Anchors (MVP Rules)

Chunking rules:
1. Parse YAML front matter (single front matter per file)
2. Split on headings (`##`, `###`)
3. Split long sections into paragraphs
4. Enforce chunk size budgets (tokens/characters)

Anchors:
- Generate stable-ish anchors like:
  - `<heading_slug>-c<chunk_index>`
- Store `anchor` and `heading` with each chunk

Store two texts:
- `chunk_text_embed` (heading + body) for embeddings
- `chunk_text_display` for snippets (optional; can be same initially)

---

## 9) Local Ingestion Workflow

### 9.1 Minimal ingestion commands
- `index_repo sample-repo-a`
- `index_all`

Both commands now use **content-hash upsert logic** (see §4.3): unchanged chunks are skipped, modified chunks are re-embedded, deleted chunks are pruned. The response includes `skipped_unchanged` count for visibility.

### 9.2 File watching (optional)
Add a dev-only file watcher:
- watch `repos/**/.ai/memory/**`
- reindex changed repo automatically

---

## 10) Gateway Bundle Assembly (Local MVP)

### 10.1 Bundle algorithm (local)
1. Load repo manifest
2. Validate `namespace` and `classification` against `persona`
3. Determine standards refs from manifest
4. Check `bundle_cache` for a matching `(namespace, repo, task_hash, ref, standards_version)`:
   - **Cache hit (not expired)**: return cached bundle immediately
   - **Cache miss**: continue to step 5
5. Call Index:
   - `resolve_context(repo, task, k, namespace)`
6. Fetch canonical standards content from Standards service
7. **Filter by classification**: exclude any chunks where `classification` exceeds the access level of the requesting `persona` (e.g., a `"human"` persona may see `internal` content but not `confidential`; adjust mapping as needed)
8. Select top items by priority class:
   - enterprise must-follow
   - repo must-follow
   - task-specific
9. **Apply tie-breaking rules for determinism**:
   - Primary sort: priority class (enterprise > repo > task)
   - Secondary sort: similarity score descending
   - Tertiary sort: path alphabetical ascending
   - This ensures the same query + same corpus produces the same bundle
10. Apply size budget and truncate excerpts
11. Cache the assembled bundle in `bundle_cache` with a configurable TTL (default: 5 minutes for local)
12. Return:
    - JSON bundle (with `bundle_id` for `explain_context_bundle`)
    - rendered markdown

### 10.2 Default size budgets
For local testing:
- max bundle text: 20–40 KB
- top chunks: 8–16
- standards share: ~40%
- repo share: ~40%
- task matches: ~20%

### 10.3 Determinism Definition
For this system, "deterministic" means: **given the same query, the same indexed corpus (identical content hashes), and the same configuration, the bundle output is identical.** Non-determinism from floating-point vector search is mitigated by the tie-breaking sort in step 9 — if two chunks have effectively equal similarity scores, the stable sort on path ensures consistent ordering.

---

## 11) Security Model (Dev)

### 11.1 Credential Management
- **Never commit `.env`** — use `.env.example` with placeholder values as a template
- `.env` is listed in `.gitignore` (see §1)
- Credentials in `.env` are for local development only

### 11.2 Inter-Service Authentication
Even locally, all internal services (Index, Standards) require a shared-secret header:
- Header: `X-Internal-Token`
- Value: loaded from `INTERNAL_SERVICE_TOKEN` in `.env`
- Gateway includes this header on all calls to Index/Standards
- Index and Standards reject requests missing or mismatching this header with `401 Unauthorized`

This validates the defense-in-depth pattern and catches Docker port-mapping misconfigurations where an internal service is accidentally exposed to the host.

### 11.3 Network Isolation
- **Only Gateway exposes a host-mapped port** (e.g., `8080:8080`)
- Index, Standards, and Postgres bind only to the internal Docker network — no `ports:` mapping in `docker-compose.yml`
- Ollama may be on host network or internal network depending on setup

### 11.4 Classification Enforcement
The Gateway enforces `classification` at bundle assembly time (see §10.1 step 7):
- Each chunk inherits `classification` from its `memory_pack` manifest
- The `persona` parameter maps to an access level
- Chunks exceeding the persona's access level are excluded from the bundle

Default persona-to-classification mapping (configurable):
| Persona | Max Classification |
|---|---|
| `human` | `internal` |
| `agent` | `internal` |
| `external` | `public` |

> In Azure, this maps to Entra ID group membership and RBAC roles.

---

## 12) Step-by-Step Build Plan (Phased)

### Phase 1 — Boot the stack + hardening foundations (1–2 days)
- [ ] Create repo structure under `repos/`
- [ ] Create `.gitignore` with `.env`, `data/pg/`
- [ ] Create `.env.example` with placeholder values
- [ ] Create docker-compose with Postgres + services (only Gateway port exposed to host)
- [ ] Implement Postgres migrations in Index service, including:
  - `namespace` column on `memory_chunks` and `memory_packs`
  - `embedding_model` and `embedding_version` columns on `memory_chunks`
  - `classification` column on `memory_chunks`
  - HNSW index on `memory_chunks.embedding`
  - B-tree index on `(namespace, repo, ref)`
- [ ] Implement shared input validation module (`services/shared/`)
- [ ] Implement `X-Internal-Token` auth check on Index and Standards services
- [ ] Implement `X-Request-ID` propagation and structured JSON logging
- [ ] Implement `health()` tools for all services (include dependency checks)

**Exit:** `docker compose up` runs; services respond to health checks; internal auth rejects unauthenticated requests; logs are structured JSON with request IDs.

### Phase 2 — Standards service + versioning (1–2 days)
- [ ] Define standard IDs (path-based: `enterprise/<domain>/<name>`)
- [ ] Implement standards version resolution: map `version` param to directory structure or Git tags (e.g., `enterprise-standards/v3/terraform/module-versioning/`)
- [ ] Seed at least **two versions** of one standard to validate resolution logic
- [ ] Implement `get_standard`, `list_standards`, `get_schema` with input validation
- [ ] Load content from `repos/enterprise-standards/.ai/memory`

**Exit:** Standards MCP can serve canonical docs locally, including version-specific retrieval.

### Phase 3 — Index ingestion + search (2–4 days)
- [ ] Implement chunker + manifest parser
- [ ] Implement embedding adapter (Ollama) with resilience handling (§7.1)
- [ ] Implement `index_repo`, `index_all` with **content-hash upsert logic** (§4.3)
- [ ] Implement vector search with `namespace` filtering and return pointers + snippets
- [ ] Verify `embedding_model` and `embedding_version` are stored with every chunk

**Exit:** You can index repos and search semantically. Unchanged content is skipped on re-index. Embedding model is tracked per chunk.

### Phase 4 — Gateway bundling (2–4 days)
- [ ] Implement `get_context_bundle` with classification enforcement (§11.4)
- [ ] Implement precedence rules (standards > repo)
- [ ] Implement deterministic tie-breaking sort (§10.1 step 9)
- [ ] Implement size budgets and truncation
- [ ] Implement citations/pointers in output
- [ ] Implement `bundle_cache` table and cache-hit logic with configurable TTL
- [ ] Implement `explain_context_bundle` (store bundle record)

**Exit:** One call returns a deterministic, classification-filtered context bundle. Repeated identical queries return cached results.

### Phase 5 — Developer experience (2–5 days)
- [ ] Provide CLI script for calling gateway MCP tools
- [ ] Provide examples for humans (markdown output)
- [ ] Provide examples for agents (JSON output)
- [ ] Add optional file watcher for auto-reindex
- [ ] Document scaling boundaries (pgvector ~1M vectors, when to evaluate alternatives)

**Exit:** Smooth workflow for interactive use and pipeline simulation.

---

## 13) Local Testing Scenarios

### Scenario A — Human
- Query: "How do we version terraform modules in this repo?"
- Expect:
  - standards excerpt (module versioning)
  - repo conventions excerpt (naming/folder structure)
  - schema pointers if relevant

### Scenario B — Ephemeral agent simulation
- Run a script that:
  - starts clean
  - calls gateway with `task` and `changed_files`
  - uses bundle to drive a "mock" operation

### Scenario C — Classification filtering
- Create a repo with `classification: confidential` chunks
- Query with `persona=external`
- **Expect:** confidential chunks are excluded from the bundle

### Scenario D — Cache behavior
- Call `get_context_bundle` twice with identical parameters
- **Expect:** second call returns faster (cache hit), identical output

### Scenario E — Incremental re-index
- Index a repo, then modify one file
- Re-index the same repo
- **Expect:** only the modified file's chunks are re-embedded; unchanged chunks report `skipped_unchanged`

### Scenario F — Input validation
- Call `index_repo` with `repo=../../etc/passwd`
- **Expect:** `400 Bad Request` with validation error, not a file read

### Scenario G — Standards versioning
- Request `get_standard("enterprise/terraform/module-versioning", version="v3")`
- Request same standard with `version="v4"`
- **Expect:** different content reflecting each version

---

## 14) Deliverables Checklist

- [ ] Docker compose stack boots reliably
- [ ] `.env` is git-ignored; `.env.example` is committed with placeholders
- [ ] Inter-service auth (`X-Internal-Token`) is enforced on Index and Standards
- [ ] Structured JSON logging with `X-Request-ID` tracing across all services
- [ ] Input validation on all MCP tool parameters
- [ ] Standards MCP serves canonical content with version resolution
- [ ] Index MCP ingests and searches repo memory packs with content-hash upsert
- [ ] `embedding_model` and `namespace` columns present and populated
- [ ] Gateway MCP returns context bundles with classification filtering, deterministic sort, citations, and version pins
- [ ] Bundle caching with TTL-based expiry
- [ ] Example repos and standards repo included for demonstration
- [ ] Test scenarios A–G pass

---

## 15) Migration Notes (Local → Azure Private Network)

When you move to Azure:
- Replace local `repos/` with real ADO repo checkouts in ingestion pipelines
- Replace local `ref=local` with `commit_sha`
- Deploy Postgres via Azure Database for PostgreSQL + private endpoint
- Use Entra ID auth and managed identities (replaces `X-Internal-Token`)
- **Enable mTLS** between Gateway, Index, and Standards services via Azure Private Endpoints or service mesh
- Map `persona` to Entra ID group membership for classification enforcement
- Map `namespace` to Azure tenant/team boundaries
- Gateway remains the client-facing interface; Index/Standards can be internal services
- Replace structured JSON logging with OpenTelemetry SDK exporting to Azure Monitor / Application Insights
- Evaluate Azure AI Search or dedicated vector DB if corpus exceeds ~1M vectors
- Migrate `INTERNAL_SERVICE_TOKEN` and `POSTGRES_PASSWORD` to Azure Key Vault
- Replace Ollama with Azure-hosted embedding inference (Azure OpenAI or private model endpoint)

---

## Appendix A — Suggested Environment Variables (.env.example)

```
# --- Postgres ---
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=memory
POSTGRES_USER=memory
POSTGRES_PASSWORD=CHANGE_ME

# --- Embeddings ---
EMBED_PROVIDER=ollama
OLLAMA_URL=http://ollama:11434
EMBED_MODEL=nomic-embed-text
EMBED_DIMS=768

# --- Repos ---
REPOS_ROOT=/repos
STANDARDS_REPO=enterprise-standards
DEFAULT_STANDARDS_VERSION=local

# --- Gateway ---
GATEWAY_MAX_BUNDLE_CHARS=40000
GATEWAY_DEFAULT_K=12
BUNDLE_CACHE_TTL_SECONDS=300

# --- Inter-Service Auth ---
INTERNAL_SERVICE_TOKEN=CHANGE_ME

# --- Multi-Tenancy ---
DEFAULT_NAMESPACE=default
```

---

## Appendix B — "Next File" to Add (if you want)
If you want, the next artifact to produce is a **docker-compose.yml + minimal service skeletons** (FastAPI + MCP wiring) so you can start coding immediately.

---

## Appendix C — Architecture Review Reference

This plan incorporates all findings from the enterprise architecture review conducted on 2026-03-04. See `enterprise-architecture-review.md` for the full assessment including scoring rationale and detailed risk analysis.

### Findings Addressed

| Finding | Section(s) Updated |
|---|---|
| Content-hash upsert for staleness detection | §4.3, §9.1, §12 Phase 3 |
| Embedding model migration columns | §4.1, §12 Phase 1 |
| Observability and request tracing | §6.3, §12 Phase 1 |
| Bundle determinism and tie-breaking | §10.1, §10.3 |
| Shared library versioning | §1, §6.1 |
| Plaintext credentials / .gitignore | §1, §11.1, Appendix A |
| Input validation on all parameters | §5.0, §12 Phase 1 |
| TLS / mTLS for Azure migration | §15 |
| Defense-in-depth inter-service auth | §11.2, §12 Phase 1 |
| Classification enforcement | §4.1, §10.1, §11.4 |
| pgvector scaling boundaries | §4.1 note, §12 Phase 5 |
| Multi-tenancy namespace column | §2, §4.1, §5.x, §12 Phase 1 |
| Bundle caching with TTL | §4.1, §10.1, §12 Phase 4 |
| Embedding provider resilience | §7.1 |
| Standards versioning resolution | §12 Phase 2 |
