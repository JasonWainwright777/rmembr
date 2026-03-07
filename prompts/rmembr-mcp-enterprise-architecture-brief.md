# rmembr MCP Application: Enterprise Architecture Brief

This document describes the MCP application implemented in this repository (rmembr) in a way that an enterprise reviewer can read end-to-end and decide whether the design meets their architectural expectations, and where it is strong or weak.

It is intentionally written as "what we built" (not a comparison rubric).

## Executive Summary

rmembr is a local-first, service-oriented "targeted AI memory" system. Repositories maintain a curated Markdown "memory pack" under `.ai/memory/**`. The system chunks that content, embeds it via an embedding provider (Ollama by default), stores embeddings in Postgres with pgvector, and retrieves relevant chunks via semantic search. A Gateway service assembles deterministic, budget-bounded "context bundles" for a task and exposes the capability both as HTTP endpoints and as an MCP server.

Key enterprise-facing properties:
- Clear service boundaries (Gateway, Index, Standards) with internal service authentication (`X-Internal-Token`).
- Contracted tool surface (canonical 9 tools), with tests to protect schema/transport behavior.
- Policy-based authorization (tool allow/deny by role) and persona-based classification filtering (public/internal).
- Observability primitives (structured logs, request IDs, Prometheus metrics, optional dashboards/alerts).

Key limitations/gaps (current state, not aspirations):
- In local mode, the Gateway does not enforce inbound client authentication; the trust boundary is typically localhost.
- Memory-pack Markdown front matter metadata is parsed but should not be assumed to drive enforcement end-to-end unless verified in code.
- Primary content source is curated `.ai/memory/**`, not full-repo code ingestion by default.

## System Context And Intended Use

Primary use case:
- Provide stable, curated context to humans and AI assistants during development tasks (search for "how do we do X here?", or assemble a bundle for "implement Y").

Core design choice:
- The source of truth for retrieval is curated documentation the repo owners control, stored in `.ai/memory/**`. This reduces leakage risk and improves relevance vs indexing all code by default.

## High-Level Architecture

Runtime stack (local Docker Compose) lives under `mcp-memory-local/`.

Components:
- Gateway (FastAPI): external entry point, bundle assembly, caching, policy enforcement for tool authz and classification filtering, optional MCP server.
  - Primary code: `mcp-memory-local/services/gateway/src/server.py`
  - MCP transport app: `mcp-memory-local/services/gateway/src/mcp_server.py`
  - Tool registry: `mcp-memory-local/services/gateway/src/mcp_tools.py`
- Index (FastAPI): ingestion + chunking + embeddings + upsert + semantic search + retrieval ranking pipeline.
  - Primary code: `mcp-memory-local/services/index/src/server.py` and related modules
- Standards (FastAPI): serves versioned enterprise standards content used as "must follow" references for bundles.
  - Primary code: `mcp-memory-local/services/standards/src/server.py`
- Shared library: chunking, manifest parsing, auth middleware, validation, structured logging, audit logging, metrics.
  - Primary code: `mcp-memory-local/services/shared/src/`
- Postgres + pgvector: persistence for packs, chunks, and bundle cache.
- Ollama: embedding model server (default embedding model `nomic-embed-text`, 768 dims).

Network and exposure:
- Only the Gateway is exposed to the host by default (typically `http://localhost:8080`).
- Index and Standards are internal services accessed by the Gateway on the container network.

## Data Flow And Core Processes

### 1) Memory Pack Authoring (Repo Owners)

Inputs:
- `repos/<repo>/.ai/memory/manifest.yaml` (metadata; excluded from chunking)
- `repos/<repo>/.ai/memory/*.md` (curated Markdown)

Authoring intent:
- Repository owners curate content to represent "what matters" to retrieval.
- Classification (public/internal) is defined at the pack level and influences what personas can see.

### 2) Indexing / Ingestion (Index Service)

Pipeline:
1. Read `.ai/memory/*.md` from a content provider (filesystem by default; optional GitHub provider).
2. Chunk Markdown into stable anchors (heading-based chunking; deterministic anchor IDs).
3. Embed chunk text using the embedding provider (Ollama by default).
4. Upsert chunk rows into Postgres (stable identity via `(repo, path, anchor, ref)`).
5. Delete chunks removed from source on reindex.

Important notes for reviewers:
- Chunking is designed to be stable across edits to preserve references and reduce index churn.
- YAML front matter can be parsed by the chunker; do not assume it is enforced end-to-end unless verified in the ingest path and bundle logic.

### 3) Retrieval (Index Service)

Two main retrieval modes:
- `search_repo_memory`: query -> top-k semantic matches (for "search").
- `resolve_context`: task -> top-k chunk pointers (for "bundle assembly"), with optional `changed_files` path boosting.

Ranking model (conceptual):
- `final_score = semantic_similarity + path_boost + freshness_boost`

### 4) Bundle Assembly (Gateway Service)

Bundle assembly (conceptual flow):
1. Optional bundle cache lookup (hash of namespace/repo/task/ref/standards version).
2. Ask Index for candidate chunk pointers (`resolve_context`).
3. Fetch standards content from Standards service (bounded to a small count).
4. Apply persona-based classification filtering (visibility rules).
5. Assign priority classes, deterministically sort.
6. Apply a max-character budget (truncate to fit).
7. Store in cache and persist a "bundle record" to enable later explanation.

Explainability:
- `explain_context_bundle` reports what was included and why (counts, priority breakdown, per-chunk summary).

## External Interfaces

### HTTP (Gateway)

Gateway provides a stable HTTP API used by the lightweight CLI and can be used by other automation:
- `GET /health`
- `POST /tools/get_context_bundle`
- `POST /tools/explain_context_bundle`
- `POST /tools/validate_pack`
- `POST /proxy/index/{tool}` (authenticated internal proxy)
- `POST /proxy/standards/{tool}` (authenticated internal proxy)

CLI:
- `mcp-memory-local/scripts/mcp-cli.py` calls Gateway HTTP endpoints (it is not an MCP client).

### MCP Server (Gateway)

MCP server is hosted by Gateway as an ASGI sub-app.

Transports:
- Primary: Streamable HTTP on `/mcp` (`GET`, `POST`, `DELETE`).
- Legacy compatibility: SSE on `/mcp/sse` plus `/mcp/messages/`.
- Optional dev shim: stdio transport (feature-flagged).

Enablement flags:
- `MCP_ENABLED=true` enables MCP server mounting.
- `MCP_STDIO_ENABLED=true` enables stdio shim.

Practical interoperability note:
- Streamable HTTP clients must send an `Accept` header compatible with JSON responses; otherwise MCP `initialize` may be rejected as "Not Acceptable".

## Canonical Tool Surface (Contract)

The system exposes 9 tools (conceptual grouping):

Read-oriented:
- `search_repo_memory`
- `get_context_bundle`
- `explain_context_bundle`
- `validate_pack`
- `list_standards`
- `get_standard`
- `get_schema`

Write-oriented:
- `index_repo`
- `index_all`

Contract governance:
- Tool schemas are treated as a stable contract.
- Deprecation/compatibility expectations are documented and validated via tests.

Primary contract docs:
- `docs/contracts/gateway-mcp-tools.md`
- `docs/contracts/adr-001-transport-auth-tenancy.md`

## Security Architecture

### Trust Boundaries

Trust boundary 1: Client -> Gateway
- Local mode typically assumes localhost trust (no inbound auth enforced by default).
- In enterprise environments, this boundary is where TLS termination and inbound auth would be added (reverse proxy or direct Gateway middleware).

Trust boundary 2: Gateway -> Index / Standards
- Internal service calls are authenticated via a shared secret token passed as `X-Internal-Token`.
- Index and Standards reject missing/invalid tokens for non-health endpoints.

Trust boundary 3: Data at rest
- Postgres stores embeddings and chunk text.
- Operational policy should treat chunk text as sensitive if it includes internal content; classification controls visibility but does not encrypt data at rest by itself.

### Authentication (Current Behavior)

Inter-service authentication:
- Shared secret (`INTERNAL_SERVICE_TOKEN`) is required for internal service calls.

Client authentication:
- Not enforced by default in the local stack.
- ADR documents expected auth modes for Dev/Test/Prod; implementers should treat this as an enterprise deployment requirement.

### Authorization And Policy (Gateway)

There are two primary authorization dimensions:

1) Tool authorization (role-based)
- Tools are permitted/denied based on caller role (e.g., reader vs writer).
- Write tools like `index_repo`/`index_all` are expected to require elevated permission.

2) Content visibility (persona-based classification filter)
- Content has a classification (e.g., `public`, `internal`).
- Persona determines which classifications are visible in bundles (e.g., external should not see internal).

Policy source:
- Policy can be loaded from a configured policy bundle (`POLICY_FILE`) or fall back to built-in defaults.
- Policy may support hot reload in non-prod contexts (`POLICY_HOT_RELOAD=true`).

Security strength:
- The policy system centralizes authorization logic and enables deny-by-default posture for tool calls.

Security caveat:
- Classification filtering is only as good as the classification values stored on chunks and the discipline in authoring memory packs.

### Input Validation And Error Sanitization

Input validation:
- The system validates core request fields (repo names, query sizes, k bounds, namespaces, etc.).

Error handling posture:
- Client-facing errors should avoid leaking internal URLs, tokens, or container paths.

### Auditability

Audit logging:
- Tool invocations are logged with structured fields (intended to enable review of "who called what", success/failure, and denial reasons).

Request tracing:
- Gateway assigns/propagates `X-Request-ID` across internal calls; logs and metrics can correlate via request IDs.

## Data Management And Privacy

Data sources:
- Primary: curated Markdown memory packs.
- Optional: provider framework supports other sources (e.g., GitHub provider).

Stored data:
- Chunk text (or snippet text) and embeddings are stored in Postgres.
- Bundle cache stores assembled bundles for a TTL; bundle records are retained for explanation for a fixed period (currently 24 hours).

Privacy posture:
- The curated memory-pack approach reduces accidental capture of secrets compared to "index all code", but does not eliminate the need for secrets hygiene.
- Enterprise deployment should include scanning memory packs for secrets and applying clear authoring guidance.

## Tenancy And Isolation

Tenancy model:
- Schema includes a `namespace` dimension to support multi-tenant separation.
- Default namespace is `default`.

Isolation caveat:
- Namespace isolation is enforced at the application query layer, not via database row-level security by default.

## Operational Architecture

### Observability

Metrics:
- Prometheus metrics exposed at `/metrics` when enabled/installed.
- Metrics cover tool call latency, call counts, error counts, and dependency health.

Dashboards/alerts:
- Optional monitoring stack with Prometheus and Grafana can be enabled.

Logs:
- Structured logs across services, correlated by request ID.

### Reliability And Performance

Caching:
- Bundle caching reduces repeated expensive retrieval/standards fetch work for similar tasks.

Database performance:
- Vector search uses pgvector with an HNSW index (optimized for approximate nearest neighbor search).

SLO posture:
- SLO targets are documented and validated with tests in the repo.
  - See `docs/contracts/slo-targets.md` and `tests/mcp/test_slo_validation.py`.

### Runbooks And Troubleshooting

Operational guidance exists for common failure modes (embedding service down, database pool exhaustion, token mismatch, MCP client issues).
- See `docs/operations/runbook.md`

## Change Management And Quality Gates (Process)

Contract stability gates:
- Tool schemas and transport behaviors are protected by contract tests under `tests/contracts/` and `tests/mcp/`.

Transport gating:
- Tests ensure transport flags behave as expected and prevent unintended exposure.

Policy gates:
- Policy behavior and deny/allow logic is tested under `tests/policy/`.

Retrieval and providers:
- Retrieval ranking and provider behaviors have tests under `tests/retrieval/` and `tests/providers/`.

Practical process expectation:
- Changes that touch contracts, transport, policy/authz, retrieval, or providers should run the contract + MCP + policy test suites as minimum quality gates.

## Enterprise Fit: Strengths And Weaknesses

### Strengths

- Clear separation of concerns: ingestion/retrieval (Index) vs orchestration/bundling/policy (Gateway) vs standards content (Standards).
- Stable and test-protected tool surface (9 tools), suitable for integration with MCP-capable clients.
- Internal service authentication reduces lateral movement risk between services when deployed in a shared network.
- Deterministic sorting + budgeting produces reproducible bundles, which helps reviewability and auditability.
- Provider abstraction supports enterprise extension (e.g., GitHub Enterprise, other content sources) without changing core tool semantics.
- Observability-first hooks (metrics, request IDs, structured logs) support productionization.

### Weaknesses / Risks (Current State)

- Inbound client authentication is not enforced by default; enterprise deployment should require TLS + authn at Client -> Gateway boundary.
- Classification and policy correctness depends on consistent memory-pack authoring discipline; misclassified content could leak to external persona if misconfigured.
- Namespace-based tenancy is application-enforced; high-assurance multi-tenancy may require DB-level protections (RLS) and identity-to-namespace routing.
- Embedding and storage model implies sensitive text is stored in Postgres; enterprises may require encryption at rest, key management integration, and data retention controls.
- Front matter metadata is not a reliable enforcement mechanism unless the ingest/bundle pipeline persists and uses it; treat it as documentation intent only unless verified.
- Default design optimizes for curated docs; architectures expecting full-code indexing or deeper code intelligence require additional providers and guardrails.

### Where This Fits Best

- Teams that want predictable, curated, task-relevant context for assistants, with low operational overhead.
- Environments where repo owners can maintain `.ai/memory/**` as a governed artifact (like ADRs/runbooks), and where policy and classification are treated as first-class.

### Where This Fits Poorly (Without More Work)

- Environments that require strong client auth by default on localhost, strict multi-tenant isolation enforced in the database, or strict no-storage-of-source-text requirements.
- Use cases that require indexing all code automatically without curated memory packs.

## Enterprise Deployment Recommendations (If Moving Beyond Local)

Minimum hardening steps:
- Add TLS termination and inbound authentication at the Gateway boundary (reverse proxy or Gateway middleware).
- Define and enforce a secrets hygiene process for `.ai/memory/**` (scanning + review gates).
- Define a retention policy for `bundle_cache` and any stored bundle records, aligned with enterprise policy.
- Lock down network access so Index/Standards are not reachable externally.
- Consider row-level security and stricter namespace routing if multi-tenant isolation is required.
- Document and enforce a compatibility policy for tool contract changes (already documented; ensure releases follow it).

Operational steps:
- Run the contract and MCP test suites as required CI gates for changes that affect interfaces.
- Monitor tool latency and error rates using the provided metrics and dashboards; alert on dependency health.

