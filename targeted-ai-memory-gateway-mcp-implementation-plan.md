# Implementation Plan — Repo-Scoped Targeted AI Memory with Gateway MCP (Azure DevOps + Azure Private Network)

**Generated:** 2026-03-04T18:08:41.706555 UTC
**Audience:** Enterprise Architecture + Platform Engineering
**Primary Goal:** Provide **targeted, governed, fast** AI context retrieval for (1) humans working in repos and (2) ephemeral autonomous agents in Azure DevOps pipelines, without “loading everything.”

---

## 0) Executive Summary

This plan implements a **three-layer architecture** with a single **front door** for AI clients:

1. **Memory Packs in repos** (source of truth; versioned, reviewed)
2. **Index Service** (Postgres + pgvector) for fast discovery of relevant pointers
3. **Standards Service** for canonical enterprise instructions/schemas/runbooks (versioned releases)
4. **Gateway MCP** that orchestrates both services and returns a **ready-to-use context bundle**

**Key property:** Retrieval returns **pointers and curated content** pinned to immutable versions (repo commit SHA + standards release tag), enabling deterministic runs on ephemeral Azure DevOps runners.

---

## 1) Target Scenarios & Requirements

### 1.1 Scenarios
**A) Human-in-repo**
- Developer/architect uses an LLM tool while working in an Azure DevOps Repo.
- Needs quick access to repo-specific instructions, schemas, runbooks, and enterprise standards.

**B) Ephemeral autonomous agent (ADO runners)**
- Agent runs on ADO runners, context is cleared each step/run.
- Must retrieve the right memory quickly, deterministically, and securely for each run.

### 1.2 Core Requirements
- **Repo-first governance:** memory content lives in repos for review/versioning.
- **Targeted retrieval:** only fetch what is relevant to the current task.
- **Fast:** low-latency retrieval for interactive and pipeline execution.
- **Deterministic:** pin to repo commit SHA and standards version.
- **Secure:** private network, Entra ID auth, least-privilege per repo/team.
- **Scalable:** expand from small footprint to **hundreds of repos**.
- **Extensible:** swap retrieval backend later (AI Search/OpenSearch) without breaking clients.

---

## 2) High-Level Architecture

### 2.1 Components
1. **Memory Packs (in each repo)** — `/.ai/memory/**`
2. **Enterprise Standards Repo** — canonical instructions/schemas/runbooks
3. **Index MCP** — discovery over embeddings + metadata (Postgres + pgvector)
4. **Standards MCP** — authoritative content service for enterprise standards
5. **Gateway MCP (Front Door)** — returns a context bundle by orchestrating Index + Standards

### 2.2 Data Flow (Typical)
1. Client/agent calls **Gateway MCP**: “I’m working in repo X at commit Y, doing task Z”
2. Gateway calls **Index MCP**: returns ranked pointers to repo memory + referenced standards IDs
3. Gateway calls **Standards MCP**: fetches canonical standards content by ID/version
4. Gateway assembles a **Context Bundle**: curated markdown/text + pointers + citations + policy notes
5. Client uses the bundle to execute work (and can optionally fetch exact repo files locally).

---

## 3) Memory Pack Standard (Repo Convention)

### 3.1 Repo Layout
Each repo includes a consistent AI-facing directory:

```
/.ai/
  memory/
    README.md
    manifest.yaml
    instructions.md
    schemas/
    runbooks/
    adr/
    repo-skills/
    examples/
```

### 3.2 manifest.yaml (Contract)
Minimum fields:

```yaml
pack_version: 1
scope:
  repo: <ado-project>/<repo>
owners:
  - <team-or-alias>
required_files:
  - instructions.md
classification: internal   # optional: internal/confidential/etc.
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

### 3.3 Precedence / Overrides
Default precedence rules (recommended):
- **Enterprise standards win by default**
- Repo-level overrides only allowed if:
  - `override_policy.allow_repo_overrides: true`
  - override explicitly declares which standard IDs it overrides
  - owners/approvers are recorded (via CODEOWNERS / PR reviews)

---

## 4) Services and Tool Contracts (MCP)

### 4.1 Index MCP (Discovery)
**Purpose:** “What should I read?” Return ranked pointers/snippets.

#### Required tools
- `search_repo_memory(repo, commit_sha, query, k, filters?)`
- `resolve_context(repo, commit_sha, task, changed_files?, k, filters?)`
- `search_enterprise_memory(version, query, k, filters?)` *(optional if you also index central)*
- `health()`

#### Output should include
- `repo`, `commit_sha`
- `path`, `anchor`
- `snippet`
- `score`
- `metadata` (tags/domain/pack)
- `standard_refs` (IDs referenced by the matched chunk)

> Best practice: Index MCP returns **pointers**, not full documents.

### 4.2 Standards MCP (Authoritative Content)
**Purpose:** “Give me canonical instructions/schemas.” Versioned and governed.

#### Required tools
- `get_standard(id, version)` → markdown/text payload
- `list_standards(domain?, version?)`
- `get_schema(name_or_id, version)` → JSON/YAML
- `health()`

### 4.3 Gateway MCP (Front Door)
**Purpose:** Provide a single interface for clients and agents.

#### Primary tools
- `get_context_bundle(repo, commit_sha, task, changed_files?, persona?, k?, filters?)`
- `explain_context_bundle(bundle_id)` (why items were chosen; useful for trust)
- `health()`

#### Context Bundle content (recommended shape)
- **Pinned versions:** repo commit SHA + standards release tag
- **Curated guidance:** key excerpts (bounded length)
- **Pointers/citations:** path + anchor per excerpt
- **Required schemas/rules:** included or referenced
- **Policy/precedence notes:** what is canonical vs local
- **Trace metadata:** retrieval scores, filters applied (optional)

---

## 5) Index Data Model (Postgres + pgvector)

### 5.1 Tables (Minimum)
**memory_chunks**
- `id` (uuid)
- `source_kind` (`repo_memory` | `enterprise_standard`)
- `repo` (text) — ADO project/repo identifier (nullable for standards)
- `ref_type` (`commit` | `tag` | `branch`)
- `ref` (text) — commit SHA or tag
- `path` (text)
- `anchor` (text)
- `heading` (text)
- `chunk_text` (text)
- `metadata_json` (jsonb)
- `content_hash` (text) — sha256 of chunk text
- `embedding` (vector(768))
- `created_at`, `updated_at`

**memory_packs**
- `repo`
- `pack_version`
- `owners`
- `classification`
- `embedding_model`
- `last_indexed_ref`
- `last_indexed_at`

### 5.2 Indexes
- pgvector index (HNSW or IVFFlat depending on pgvector version and workload)
- btree indexes on `(repo, ref)` and `(source_kind, ref)`
- optional: `tsvector` column for hybrid lexical search + rerank

---

## 6) Retrieval Strategy (Hybrid by Default)

### 6.1 Recommended Ranking Pipeline
1. **Scope filter** (repo + commit; and/or standards version)
2. **Lexical prefilter** (optional but recommended at scale)
3. **Vector search** (top N)
4. **Rerank** (optional): combine lexical + vector score
5. **Dedupe**: remove near-duplicates and repeated anchors
6. **Bundle assembly**: enforce size budgets and precedence rules

### 6.2 Size Budgets (Important for LLM consumption)
- Limit context bundle payload (e.g., 15–40 KB text) by:
  - selecting top K chunks
  - truncating excerpts to a max length
  - prefer “instructions/schemas” over narrative when task is procedural

---

## 7) Ingestion & Indexing Pipelines (Azure DevOps)

### 7.1 Repo Memory Pack Indexing
**Trigger:** changes under `/.ai/memory/**` on PR merge to main (and optionally on PR validation).

Steps:
1. Checkout repo at commit SHA
2. Parse manifest.yaml + markdown
3. Chunk content with stable anchors (heading-based + chunk index)
4. Embed chunks (locked model/version)
5. Upsert into Postgres with `(repo, ref=commit_sha, path, anchor)` uniqueness
6. Delete stale rows for removed files at that commit scope

### 7.2 Standards Repo Indexing
**Trigger:** on release tag (e.g., `standards@2026.03`) or main merge with nightly release.

Steps:
1. Build release artifact of standards
2. Chunk + embed + upsert into Postgres with `source_kind=enterprise_standard` and `ref=release_tag`
3. Publish release notes and deprecations list

### 7.3 Determinism Strategy
- Pipelines pass their **repo commit SHA** to Gateway MCP.
- Gateway pins standards by:
  - declared version in repo manifest, OR
  - pipeline variable (e.g., `STANDARDS_VERSION=standards@2026.03`), OR
  - default “current” release tag.

---

## 8) Security, Networking, and Access Control (Azure)

### 8.1 Private Network Placement
- Deploy MCP services (Gateway, Index, Standards) into **Azure Container Apps** or **AKS** with **private ingress**.
- Postgres in **Azure Database for PostgreSQL** (private endpoint) or self-managed in AKS for dev/test.
- Ensure all traffic stays within private VNets (plus Private DNS zones).

### 8.2 Authentication / Authorization
- Use **Microsoft Entra ID** (managed identities) for:
  - ADO pipeline identity → Gateway MCP
  - Developer tools → Gateway MCP
- Enforce **repo-level access** at Gateway:
  - caller can only query repos it’s authorized for
  - standards access based on classification

### 8.3 Auditability
- Log:
  - who queried what repo/standard
  - bundle IDs and selected pointers
  - policy decisions (precedence/overrides applied)

---

## 9) Operational Model

### 9.1 SLAs (Typical Targets)
- Gateway response time p95: < 500–1500ms (depends on rerank and standards fetch)
- Index query time p95: < 200–600ms
- Standards fetch: < 200–400ms

### 9.2 Observability
- Metrics:
  - query latency, error rate, bundle size
  - cache hit rate (standards)
  - top queried standards, top repos
- Tracing:
  - correlation IDs per request from Gateway → Index → Standards

### 9.3 Caching
- Cache standards content by `(id, version)` in Gateway (memory cache) for fast reuse.
- Cache embeddings for repeated queries if needed (optional).

---

## 10) Rollout Plan (Phased)

### Phase 1 — Establish Conventions (2–6 repos)
- Define `/ .ai/memory` structure and `manifest.yaml`
- Seed enterprise standards repo with initial domains (pipelines, terraform, security baseline)
- Implement simple Gateway that:
  - reads manifest references
  - returns standards content + minimal repo pointers (lexical)

**Exit criteria**
- Humans can reliably find “how we do work” guidance from within repo.

### Phase 2 — Index Service MVP (10–30 repos)
- Deploy Postgres + pgvector
- Implement Index MCP and ingest pipelines for repo packs + standards
- Implement Gateway `get_context_bundle` with determinism and precedence

**Exit criteria**
- Ephemeral ADO agents get deterministic context bundles pinned to commit + standards release.

### Phase 3 — Scale to Hundreds of Repos
- Optimize ingestion (incremental, changed-only)
- Add hybrid lexical + vector rerank (tsvector)
- Add multi-tenant partitioning strategy (by repo group/team)
- Add policy enforcement (classification, overrides)

**Exit criteria**
- Onboarding a new repo is “drop in Memory Pack + pipeline template,” no bespoke work.

### Phase 4 — Advanced Features
- Near-duplicate detection for memory updates
- “Explain why” bundle selection
- Automatic pack validation (required files, broken references)
- Optional: replace pgvector backend with Azure AI Search for higher scale/QPS

---

## 11) Engineering Tasks Checklist

### 11.1 Memory Pack Standardization
- [ ] Define folder structure and required files
- [ ] Define manifest schema and validation rules
- [ ] Provide templates and examples
- [ ] Add CODEOWNERS for `/ .ai/memory/**`

### 11.2 Standards Repo
- [ ] Create standards repo structure
- [ ] Release/versioning policy (monthly/quarterly tags)
- [ ] Deprecation policy (how “old” standards are handled)

### 11.3 Index MCP + Postgres
- [ ] Postgres schema + migrations
- [ ] Embedding pipeline and model/version locking
- [ ] Vector query endpoints
- [ ] Optional: tsvector hybrid fields

### 11.4 Standards MCP
- [ ] Fetch content by ID/version
- [ ] List standards by domain
- [ ] Serve schemas in JSON/YAML

### 11.5 Gateway MCP
- [ ] Orchestrate Index + Standards
- [ ] Deterministic pinning (commit + standards version)
- [ ] Precedence rules and override policy
- [ ] Context bundle assembly with size budgets
- [ ] Audit logging and tracing IDs

### 11.6 Azure DevOps Integration
- [ ] Pipeline templates for indexing triggers
- [ ] Secure service connections (managed identity)
- [ ] Runner job steps to call Gateway MCP

---

## 12) Key Design Decisions (Record as ADRs)
- Store-of-truth remains in repos; index is derivative.
- Gateway is the only client-facing interface for agents.
- Determinism: commit SHA + standards release tag pinned for pipelines.
- Central standards are canonical; repo overrides are explicit and controlled.
- Hybrid retrieval is default for precision and trust.

---

## Appendix A — Example Context Bundle (Illustrative)

```
Bundle:
- repo: ProjectX/RepoY
- commit: 7f3a...c21
- standards: standards@2026.03
- task: "Add new ADO pipeline stage for terraform plan/apply"

Included:
1) Enterprise ADO job template v3 (canonical excerpt + link)
2) Enterprise terraform module versioning rules (canonical excerpt + link)
3) RepoY pipeline conventions (repo pointers + snippet)
4) RepoY terraform folder structure (repo pointers + snippet)

Notes:
- Central standards take precedence.
- Repo overrides: none.
```

---

## Appendix B — Migration / Future Options
- Swap Postgres/pgvector to **Azure AI Search** for managed scaling and hybrid retrieval features.
- Add federation across orgs/tenants if needed using separate indexes per business unit.
- Add a policy engine (OPA) for fine-grained access and classification enforcement.

---
