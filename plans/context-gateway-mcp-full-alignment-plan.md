# Context Gateway MCP + 3-Component Architecture — Full Alignment Plan

## Request being addressed
You asked whether making the **Context Gateway an MCP server** (usable from VS Code or any MCP-capable client) aligns with the intended architecture, and for a concrete plan to reach full alignment across:
1. Context Gateway control plane
2. Source/location index (ADO-first today, but provider-agnostic)
3. Retrieval engine driven by gateway requests using index-provided locations

## Direct alignment answer
**Yes — making the Context Gateway an MCP server is aligned** with the architecture direction, if the Gateway remains the single policy/orchestration boundary and MCP is an interface layer (not business logic).

---

## Planning constraints (no assumptions)
This plan is organized with explicit decision gates where requirements are not yet locked. No blocked item proceeds without an approved decision.

---

## Target end-state definition (must be true)
- Gateway runs as a standards-compliant MCP server endpoint and exposes tool contracts for client use.
- Gateway owns routing, policy, ranking, persona controls, budgets, observability, and provenance.
- Index service becomes a **provider-agnostic location index** with pluggable source connectors (ADO first, extensible).
- Retrieval engine fetches content using locations emitted by the index and returns normalized chunks to gateway.
- End-to-end flow works from an MCP client (e.g., VS Code MCP) with repeatable tests.

---

## Work plan

## Phase 0 — Clarification & contract lock (required before implementation)

### Tasks
- Define and approve canonical MCP tool surface for gateway (names, JSON schemas, errors, auth expectations).
- Define supported MCP transports for phase rollout (stdio and/or streamable HTTP).
- Define identity model for client calls (anonymous local, API key, AAD/OIDC, service principal).
- Define source-of-truth for repository locations and minimum metadata schema.
- Define non-functional targets: latency, timeout, retry policy, throughput, availability expectations.

### Acceptance criteria
- Signed-off `docs/contracts/gateway-mcp-tools.md` with versioned schemas.
- Signed-off `docs/contracts/location-index-schema.md` with required/optional fields.
- Signed-off ADR documenting chosen transports and auth strategy.

### Testing to prove completion
- Contract validation script runs against tool schemas and example payloads.
- Negative contract tests exist for invalid payloads and unauthorized requests.

---

## Phase 1 — Gateway as first-class MCP server

### Tasks
- Implement MCP server wrapper in gateway service, mapping MCP tools to existing gateway handlers.
- Ensure deterministic tool naming, schema publishing, and versioning strategy.
- Preserve current HTTP APIs for backward compatibility while MCP is rolled out.
- Add request correlation IDs propagated from MCP call -> gateway -> index/retrieval -> response.
- Add standardized MCP error mapping (validation, auth, dependency timeout, internal).

### Acceptance criteria
- MCP client can discover and invoke gateway tools successfully.
- Same task returns equivalent results via MCP and existing HTTP paths.
- Logs show end-to-end correlation ID and timing spans.

### Testing to prove completion
- Unit tests: MCP adapter validates payload coercion and error mapping.
- Integration tests: MCP client fixture calls `get_context_bundle` and `search_repo_memory`.
- Regression tests: existing CLI HTTP workflows still pass.
- Soak test: repeated MCP invocations for 15+ minutes without server crash/leak.

---

## Phase 2 — Provider-agnostic location index

### Tasks
- Introduce a `LocationProvider` interface with required operations:
  - enumerate repositories
  - enumerate documents/paths
  - fetch document content/metadata
  - provide stable external IDs and version refs
- Implement ADO provider as first production provider.
- Add local filesystem provider (for parity with current behavior).
- Store canonical location records independent of provider internals.
- Implement re-index workflow using stable IDs/version refs to detect add/update/delete.

### Acceptance criteria
- Index can ingest from at least two providers via the same interface (ADO + filesystem).
- A single repo logical identity can be mapped to provider-specific identifiers.
- No retrieval logic depends on provider-specific path parsing.

### Testing to prove completion
- Provider contract tests run for each provider implementation.
- Golden tests validate identical normalized location records across providers.
- Delta indexing tests verify add/update/delete handling by version/ref changes.

---

## Phase 3 — Retrieval engine separation and normalization

### Tasks
- Separate retrieval into explicit service/module boundary if currently coupled to index internals.
- Make retrieval input strictly: query + constraints + location references from index.
- Normalize fetched artifacts into common chunk model (content, title, path, source, revision, ACL tags).
- Add ranking pipeline stages: lexical prefilter (optional), semantic scoring, freshness/path boosts.
- Return provenance bundle (location ID, provider, revision, chunk anchor, score components).

### Acceptance criteria
- Retrieval accepts location references from index without direct provider calls from gateway.
- Returned chunks include full provenance metadata.
- Ranking behavior is configurable and test-covered.

### Testing to prove completion
- Integration tests: gateway -> index -> retrieval -> gateway response across providers.
- Reproducibility tests: same query + same index revision returns stable top-K ordering tolerance.
- Fault tests: provider timeout/degraded index returns partial but well-formed response.

---

## Phase 4 — Policy, security, and tenancy hardening

### Tasks
- Enforce persona/classification policy at gateway prior to response assembly.
- Add per-tool authorization checks and deny-by-default paths.
- Add audit logging for tool call subject, repo scope, and returned provenance references.
- Implement request budget controls (token/content limits, max sources, timeout caps).

### Acceptance criteria
- Unauthorized tool calls are denied with structured error responses.
- Sensitive chunks are excluded according to persona/classification rules.
- Audit log records are queryable and include correlation IDs.

### Testing to prove completion
- Security tests: allow/deny matrix for all MCP tools.
- Policy tests: personas receive expected redaction/filters.
- Budget tests: oversized queries are rejected or truncated predictably.

---

## Phase 5 — VS Code / generic MCP client interoperability

### Tasks
- Provide `docs/integration/vscode-mcp.md` with exact configuration and troubleshooting.
- Provide reference configs for at least one additional MCP host/client.
- Validate tool discovery, invocation, and response rendering in supported clients.
- Add smoke test harness that simulates MCP client startup + tool call sequence.

### Acceptance criteria
- Fresh environment setup completes from docs without tribal knowledge.
- VS Code MCP client can list and invoke gateway tools successfully.
- At least one non-VS Code MCP client also passes smoke flow.

### Testing to prove completion
- Manual UAT checklist executed and signed off.
- Automated smoke tests run in CI (or nightly if interactive setup required).

---

## Phase 6 — Operational readiness

### Tasks
- Add dashboards/alerts for MCP error rate, latency percentiles, dependency health.
- Define SLOs and runbook for common failures (provider auth fail, embedding outage, DB saturation).
- Add migration/version strategy for tool schemas and provider contracts.

### Acceptance criteria
- On-call runbook published with triage steps.
- Alerts trigger on threshold breaches with actionable messages.
- Backward compatibility policy documented for MCP tool changes.

### Testing to prove completion
- Game-day drills for dependency outages.
- Alert simulation tests for threshold crossing.

---

## Backlog decomposition (actionable tasks)

### Epic A — MCP Gateway
- A1: Implement MCP server transport adapter in gateway.
- A2: Publish tool schemas + schema versioning metadata.
- A3: Map gateway exceptions to MCP-standard error payloads.
- A4: Add parity tests MCP vs HTTP responses.

### Epic B — Location Index abstraction
- B1: Define `LocationProvider` contract and fixtures.
- B2: Build ADO provider implementation.
- B3: Build filesystem provider implementation.
- B4: Introduce canonical location schema storage + migration.

### Epic C — Retrieval normalization
- C1: Separate retrieval API boundary and request/response DTOs.
- C2: Implement provenance-rich chunk model.
- C3: Add ranking stage configuration with tests.

### Epic D — Security and governance
- D1: Tool-level auth middleware.
- D2: Persona/classification enforcement tests.
- D3: Audit log pipeline with correlation IDs.

### Epic E — Client interoperability
- E1: VS Code MCP setup doc + sample config.
- E2: Secondary MCP client validation.
- E3: CI smoke test harness for MCP startup and tool invocation.

---

## Definition of Done (full alignment)
All items below must be true simultaneously:
- Gateway is the only external AI integration boundary and is reachable via MCP.
- Index is provider-agnostic with at least ADO + filesystem providers passing contract tests.
- Retrieval consumes index locations and returns normalized provenance-rich chunks.
- Security/policy controls are enforced and auditable.
- VS Code (and one additional MCP client) can successfully discover and call tools.
- Documentation and runbooks enable repeatable setup/operations.

---

## Open questions requiring your decisions
To avoid assumptions, these answers are required before implementation starts:
1. **Primary MCP transport for v1:** stdio, streamable HTTP, or both?
2. **Auth model for MCP clients:** local dev unauthenticated, API key, AAD/OIDC, or mixed by environment?
3. **Provider priority after ADO:** GitHub, GitLab, SharePoint, Confluence, or other?
4. **Tenancy scope:** single-tenant per deployment or multi-tenant with strict isolation?
5. **Policy source:** where do persona/classification rules live and who owns updates?
6. **Latency SLO target:** required p50/p95 for tool calls (e.g., search/bundle)?
7. **Change-management policy:** expected backward compatibility window for tool schema versions?
8. **Minimum supported MCP clients:** exact versions of VS Code extension(s) and additional host(s)?

