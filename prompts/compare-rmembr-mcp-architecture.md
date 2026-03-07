# rmembr MCP Architecture (Baseline For Comparison)

Use this document as a reference baseline when you are given a proposed MCP or "context gateway" architecture and you want to assess whether rmembr already implements it, partially implements it, or is missing it.

## How To Use (Paste-Friendly Prompt)

1. Paste the suggested/target architecture after the line `SUGGESTED ARCHITECTURE:` below.
2. Ask the model to produce the requested output format under `RESPONSE FORMAT`.

SUGGESTED ARCHITECTURE:
<paste here>

RESPONSE FORMAT:
- `Covered`: bullet list of suggested elements that rmembr already has (name -> where it exists).
- `Partially Covered`: bullet list (what exists, what is missing).
- `Not Covered`: bullet list (missing elements).
- `Mismatches / Tradeoffs`: bullet list (intentional differences, risks).
- `Verification Steps`: concrete commands/URLs to confirm each claim.
- `Changes Needed`: ordered list of minimal changes to close gaps.

## One-Sentence Summary

rmembr is a local-first "targeted AI memory" system that indexes curated repo Markdown memory packs (`.ai/memory/**`) into Postgres/pgvector via an Index service, and assembles task-specific context bundles via a Gateway service, exposed both as HTTP tools and as an MCP server (primary Streamable HTTP on `/mcp`, legacy SSE compatibility on `/mcp/sse`).

## Goals And Non-Goals

Goals:
- Deterministic, explainable retrieval of curated repo context for a task.
- Local runnable stack (Docker Compose) with clear service boundaries.
- Stable tool contracts (9 tools), with compatibility/deprecation discipline.
- Persona-based classification filtering (public/internal) and role-based tool authorization (reader/writer).
- Extensible content providers (filesystem now; optional GitHub provider).

Non-goals / out of scope (current shape):
- Full enterprise-grade inbound auth at the Gateway in local mode.
- Using Markdown front matter as an enforcement mechanism (metadata is parsed, but not fully persisted/used end-to-end).
- Indexing arbitrary repo code by default (primary source is curated `.ai/memory/**`).

## Runtime Topology (Local Stack)

Primary runnable system lives under `mcp-memory-local/` and is meant to be started via Docker Compose.

Services:
- `gateway` (FastAPI): host-exposed entry point `:8080`.
- `index` (FastAPI): internal service `:8081` (container network).
- `standards` (FastAPI): internal service `:8082` (container network).
- `postgres` (pgvector): stores pack metadata, chunk embeddings, and bundle cache.
- `ollama`: embedding model server (default embedding model `nomic-embed-text`, 768 dims).

Mounts:
- Repos live under `mcp-memory-local/repos/` and are mounted into containers at `/repos`.
- To index this repo as `repo=rmembr`, content must be present at `mcp-memory-local/repos/rmembr/.ai/memory/**`.

## Primary Data Model (Postgres)

Core tables:
- `memory_packs`: one row per `(namespace, repo)` with manifest metadata.
- `memory_chunks`: chunk identifiers + text + embedding + classification + provenance fields.
- `bundle_cache`: cached assembled bundles and bundle records for later explanation.

Indexing strategy:
- Chunk identity is stable via `(repo, path, anchor, ref)`; reindex uses upserts keyed by that.
- Vector search uses pgvector cosine distance with an HNSW index.

## Indexing Pipeline (Ingest)

Input:
- Curated Markdown files under `repos/<repo>/.ai/memory/*.md` plus a `manifest.yaml` (excluded from chunking).

Chunking:
- Markdown is chunked into heading-based segments with stable anchors.
- Headings are prepended to chunk text prior to embedding to preserve context.
- Very short fragments without headings are dropped.
- YAML front matter is parsed by the chunker, but do not assume it is enforced by runtime behavior unless verified in code.

Embeddings:
- Index calls Ollama to embed chunk text.
- Embeddings are stored on `memory_chunks.embedding` and associated with an embedding model/version tag.

Providers:
- Provider framework supports multiple sources.
- Default provider reads local filesystem under `/repos`.
- Optional GitHub provider can index repos from GitHub when configured (token + provider enabled); includes caching to minimize API calls.

Outputs:
- Upserts `memory_chunks` and updates `memory_packs`.
- Deletes chunks that no longer exist in the source.

## Retrieval And Ranking (Search / Resolve)

Index provides semantic retrieval for:
- `search_repo_memory`: query-driven search for top-k chunks.
- `resolve_context`: task-driven retrieval for bundle assembly (can boost `changed_files` path matches).

Ranking model (conceptual):
- `final_score = semantic_similarity + path_boost + freshness_boost`
- `changed_files` can boost matching chunk paths.
- Freshness boost is a configurable stage (may be disabled by default).

## Bundle Assembly (Gateway)

Primary tool:
- `get_context_bundle`: orchestrates retrieval + standards + filtering + sorting + budgeting + caching.

Inputs:
- `repo`, `task`, `persona`, `k`, `ref`, `namespace`, `standards_version`, `changed_files`, optional filters.

Process (conceptual):
1. Optional bundle-cache lookup (keyed by namespace/repo/task hash/ref/standards_version).
2. Call Index to get candidate chunk pointers (`resolve_context`).
3. Fetch referenced standards content from Standards service (bounded to a small count).
4. Apply persona classification filtering (e.g., external only sees `public`).
5. Assign priority classes and deterministically sort results.
6. Enforce a max-character budget by truncation.
7. Cache result and store a "bundle record" for explainability.

Explainability:
- `explain_context_bundle` returns how a previously produced bundle was built (counts, included standards, chunk summaries).

Caching:
- Search-based bundles cached with a TTL.
- Bundle records stored with a fixed 24-hour TTL for explain calls.

## HTTP Tools Surface (Gateway)

Gateway exposes HTTP endpoints (non-MCP) that are used by the Python CLI and can be used directly:
- `GET /health`
- `POST /tools/get_context_bundle`
- `POST /tools/explain_context_bundle`
- `POST /tools/validate_pack`
- `POST /proxy/index/{tool}` (forwards to Index tools with internal auth headers)
- `POST /proxy/standards/{tool}` (forwards to Standards tools with internal auth headers)

Note:
- The CLI at `mcp-memory-local/scripts/mcp-cli.py` is an HTTP client for these endpoints; it is not an MCP client.

## MCP Server Surface (Gateway)

MCP is hosted by the Gateway as an ASGI sub-app when enabled.

Transports:
- Primary: Streamable HTTP on `/mcp` (methods `GET`, `POST`, `DELETE`).
- Legacy compatibility: SSE on `GET /mcp/sse` plus `POST /mcp/messages/`.
- Optional dev shim: stdio transport (guarded by env flags).

Enablement:
- `MCP_ENABLED=true` mounts the MCP server.
- `MCP_STDIO_ENABLED=true` enables stdio shim entrypoint.

Session/handshake expectations:
- Streamable HTTP clients must send an appropriate `Accept` header; otherwise `initialize` may be rejected as "Not Acceptable".

## Canonical 9 Tools

Read-oriented tools:
- `search_repo_memory`
- `get_context_bundle`
- `explain_context_bundle`
- `validate_pack`
- `list_standards`
- `get_standard`
- `get_schema`

Write-oriented tools:
- `index_repo`
- `index_all`

Contract discipline:
- Treat tool schemas as stable contracts; breaking changes require compatibility policy (aliases / deprecation window).

## Standards Service

Purpose:
- Serves "enterprise standards" documents, versioned by directory convention.

Conceptual model:
- Standards are addressed by an ID derived from a path-like identifier.
- `list_standards` and `get_standard` operate within a chosen standards version (`local`, `v3`, `v4`, ...).

## AuthN, AuthZ, Policy, And Tenancy

Inter-service auth (Gateway -> Index/Standards):
- Gateway adds `X-Internal-Token` and request IDs on proxied/internal calls.
- Index/Standards reject missing/invalid internal token on non-health endpoints.

Client -> Gateway auth (local mode):
- In local mode, inbound auth is typically not enforced; the local trust boundary is `localhost`.

Authorization and policy:
- Policy bundle controls which roles can call which tools (reader vs writer).
- Policy bundle controls persona -> allowed classifications for bundle visibility.
- Deny-by-default posture is intended for tool authorization decisions.

Tenancy:
- Requests include a `namespace` and DB tables include `namespace` columns.
- Default namespace is `default`.

## Observability And Quality Gates

Tracing:
- Request ID propagation via `X-Request-ID` across gateway and internal calls.

Metrics:
- Prometheus metrics available via `/metrics` when `prometheus_client` is installed.
- Tool latency and cache-state labels are part of the instrumentation contract.

Audit logging:
- Tool invocations are audit-logged with structured data and sanitized errors for clients.

Test gates:
- Contract/schema validation tests for tool surfaces.
- MCP transport gating tests (ensuring flags behave as intended).
- SLO validation tests for latency targets (warm/cold cache).

## Operational Workflows (Typical)

1. Start stack: `cd mcp-memory-local && docker compose up -d`
2. Pull embedding model: `docker compose exec ollama ollama pull nomic-embed-text`
3. Ensure repo pack is mounted: `mcp-memory-local/repos/<repo>/.ai/memory/**`
4. Index repo: `POST /proxy/index/index_repo` (or CLI `python scripts/mcp-cli.py index-repo <repo>`)
5. Search: `POST /proxy/index/search_repo_memory` (or CLI `python scripts/mcp-cli.py search <repo> "<query>"`)
6. Bundle: `POST /tools/get_context_bundle` (or CLI `python scripts/mcp-cli.py get-bundle <repo> "<task>"`)
7. MCP clients: configure client to use `http://localhost:8080/mcp` (primary transport).

## Known Gaps / Cautions (Important For Comparison)

- Memory-pack YAML front matter is parsed but should not be assumed to be enforced end-to-end (verify whether metadata persists into DB and is used in ranking/bundling).
- Repo-level "must follow" prioritization may be documented as intent but not fully implemented unless verified in code paths.
- Inbound client auth at the Gateway is not the focus of the local stack (enterprise auth matrix is documented as an ADR and can be implemented for Dev/Test/Prod).
- Suggested architectures that require indexing *all code* need explicit provider changes; the default model is curated Markdown memory packs.

## Concrete Verification Commands (Localhost)

Health:
- `curl -s http://localhost:8080/health`

MCP initialize (Streamable HTTP):
- `curl -s -X POST http://localhost:8080/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}'`

Index a repo:
- `curl -s -X POST http://localhost:8080/proxy/index/index_repo -H "Content-Type: application/json" -d '{"repo":"sample-repo-a","ref":"local"}'`

Search:
- `curl -s -X POST http://localhost:8080/proxy/index/search_repo_memory -H "Content-Type: application/json" -d '{"repo":"sample-repo-a","query":"auth patterns","k":5,"ref":"local"}'`

Bundle:
- `curl -s -X POST http://localhost:8080/tools/get_context_bundle -H "Content-Type: application/json" -d '{"repo":"sample-repo-a","task":"add OAuth login","persona":"agent"}'`

