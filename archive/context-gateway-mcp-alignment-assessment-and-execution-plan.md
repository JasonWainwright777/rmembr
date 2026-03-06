# Context Gateway MCP + 3-Component Vision
## Alignment Assessment + Execution Plan (v2)

## 1) Question answered directly
### Does this repo align with the intended 3-component architecture?
**Short answer: partially aligned today; not fully aligned yet.**

### Why (evidence-based)
- **Component 1 (Context Gateway control point): Mostly aligned.**
  - Gateway already orchestrates bundle assembly and policy-like filtering inputs (`persona`, ranking/limits) via tool endpoints and downstream service calls.
- **Component 2 (Provider-agnostic index of “where everything is”): Not fully aligned.**
  - Current indexing is rooted in `REPOS_ROOT` directory walking and local `.ai/memory` packs, which is location-source constrained by filesystem shape.
- **Component 3 (Retrieval engine based on index-provided locations): Partially aligned.**
  - Retrieval exists (semantic search + resolve context), but location abstraction is not yet provider-neutral, and retrieval is still tightly coupled to current chunk store/query path.
- **Gateway as MCP server (VS Code/any MCP host): Not fully aligned yet.**
  - Current APIs are FastAPI “MCP-style tools”; this is not equivalent to a first-class MCP server transport/handshake expected by MCP hosts.

---

## 2) Current-state architecture map (as implemented)

### A. Gateway
- Exposes HTTP tool endpoints (bundle/explain/validate) and proxies index/standards services.
- Performs orchestration and formatting (JSON/Markdown bundle assembly).

### B. Index
- Handles ingestion (manifest + markdown pack parsing, chunking, embeddings, persistence).
- Handles semantic retrieval and context resolution in same service boundary.
- Uses vector similarity against stored chunk embeddings.

### C. Standards service
- Additional domain service for standards retrieval merged by gateway into bundle output.

### Gap summary against your target
1. **MCP server capability**: missing as first-class transport endpoint.
2. **Provider-agnostic location index**: missing canonical source abstraction.
3. **Strict retrieval boundary**: only partially separated from indexing concerns.

---


## 2.1) Evidence reviewed in this repository
- `README.md`: documents gateway/index/standards stack and describes API surface as FastAPI services with MCP-style tools.
- `docs/USAGE.md`: operational flow (`index-repo`, `search`, `get-bundle`) showing gateway-mediated orchestration over index and standards.
- `docs/CONFIGURATION.md`: current dependency on `REPOS_ROOT` and memory-pack filesystem conventions.
- `mcp-memory-local/services/gateway/src/server.py`: gateway tool endpoints and proxy orchestration to index/standards services.
- `mcp-memory-local/services/index/src/ingest.py`: repo ingestion by scanning `REPOS_ROOT` and `.ai/memory` content.
- `mcp-memory-local/services/index/src/search.py`: retrieval path (`search_repo_memory`, `resolve_context`) in index service.

## 3) Target architecture (full alignment)

## Component 1 — Context Gateway (MCP-native control plane)
**Responsibilities**
- MCP tool exposure (discovery + invocation)
- Request policy/authorization/classification controls
- Query planning and budget controls
- Orchestrating index lookup + retrieval execution
- Provenance-rich response assembly

## Component 2 — Location Index (source/provider agnostic)
**Responsibilities**
- Canonical registration of repositories/doc locations independent of source platform
- Provider adapters (ADO first, then additional connectors)
- Stable external IDs and revisions for change detection
- Query API returning location references, not provider-specific internals

## Component 3 — Retrieval Engine
**Responsibilities**
- Fetching/expanding content from location refs supplied by index
- Chunk normalization, scoring/ranking, and provenance emission
- Returning ranked evidence to gateway for final policy shaping

---

## 4) Execution plan with actionable tasks, acceptance criteria, and proof tests

## Phase 0 — Contract lock and unknowns resolution (no implementation before this)
### Tasks
1. Define MCP tool catalog and JSON schemas (`search_repo_memory`, `get_context_bundle`, `explain_context_bundle`, `validate_pack`, etc.).
2. Decide MCP transports for v1 (stdio, streamable HTTP, or both).
3. Define auth model per environment (local dev vs shared env).
4. Define canonical `LocationRef` schema and index API contracts.
5. Define SLOs and timeout/retry budgets.

### Acceptance criteria
- Signed-off contract docs for MCP tools and `LocationRef`.
- ADR documenting transport + auth decisions.
- Approved SLO table for key tool calls.

### Testing / proof
- Schema validation tests (positive + negative payloads).
- Compatibility tests using sample MCP client requests against schemas.

---

## Phase 1 — Make gateway a first-class MCP server
### Tasks
1. Add MCP server adapter layer in gateway (do not move business logic into adapter).
2. Map MCP tools to existing gateway handlers with strict request/response validation.
3. Keep existing HTTP endpoints for backward compatibility.
4. Add correlation IDs propagated across gateway/index/retrieval calls.
5. Implement deterministic MCP error mapping.

### Acceptance criteria
- MCP client can discover and invoke gateway tools successfully.
- Equivalent outputs between MCP tool calls and existing HTTP endpoints for same inputs.
- Correlation IDs visible in logs across service boundaries.

### Testing / proof
- Unit tests for adapter validation + error mapping.
- Integration tests with MCP client fixture invoking core tools.
- Regression tests for existing CLI HTTP flows.
- 15-minute sustained invocation test without leak/crash.

---

## Phase 2 — Build provider-agnostic Location Index
### Tasks
1. Introduce `LocationProvider` interface:
   - list repos
   - list docs/paths
   - fetch content/metadata
   - expose stable IDs + revision/ref
2. Implement provider adapters:
   - Adapter A: local filesystem (current behavior)
   - Adapter B: ADO repos (first external provider)
3. Create canonical location store schema decoupled from provider path formats.
4. Add re-index delta logic using provider revision identities.

### Acceptance criteria
- Same ingest pipeline works through both filesystem and ADO adapters.
- Index API returns provider-neutral `LocationRef` records.
- Retrieval/gateway code paths do not parse provider-specific path formats.

### Testing / proof
- Contract test suite run against each provider adapter.
- Golden tests verifying normalized location identity output.
- Delta tests for add/update/delete/rename across revisions.

---

## Phase 3 — Retrieval engine boundary hardening
### Tasks
1. Define retrieval service API: input = query + constraints + `LocationRef[]`.
2. Ensure retrieval performs content fetch/normalization/scoring independent of gateway.
3. Emit full provenance fields (provider, external_id, revision, path, anchor, score components).
4. Support configurable ranking stages (semantic + boosts).

### Acceptance criteria
- Gateway consumes retrieval responses without direct provider/data-store coupling.
- All returned evidence items include complete provenance metadata.
- Ranking behavior controlled by config and covered by tests.

### Testing / proof
- End-to-end tests: gateway -> index -> retrieval -> gateway output.
- Reproducibility tests for ranking stability at fixed index revision.
- Failure-mode tests (provider timeout, partial retrieval, index degradation).

---

## Phase 4 — Security/policy and tenancy controls
### Tasks
1. Enforce authorization per MCP tool.
2. Enforce persona/classification filtering at gateway assembly boundary.
3. Add audit events with correlation IDs + scope + evidence references.
4. Add query/content budget guards.

### Acceptance criteria
- Unauthorized requests denied by policy with structured error payload.
- Persona/classification constraints demonstrably enforced in outputs.
- Audit trail searchable for each tool call.

### Testing / proof
- Allow/deny matrix tests across tools and personas.
- Redaction/filtering tests with classified fixtures.
- Budget-limit tests for large queries and excessive candidate sets.

---

## Phase 5 — VS Code and generic MCP-client interoperability
### Tasks
1. Publish VS Code MCP setup guide with exact configuration values.
2. Publish second-client guide (at least one non-VS Code MCP host).
3. Add client smoke harness for startup/discovery/invoke flow.
4. Add troubleshooting section for auth, transport, and schema mismatch cases.

### Acceptance criteria
- Clean-room setup succeeds using docs only.
- VS Code MCP client can discover and invoke tools end-to-end.
- One additional MCP host passes smoke flow.

### Testing / proof
- Manual UAT checklist signed off.
- Automated smoke run (CI/nightly) for non-interactive verification.

---

## 5) Backlog-ready work items (implementation order)
1. Contract docs + ADRs (Phase 0).
2. Gateway MCP adapter + parity tests (Phase 1).
3. `LocationProvider` abstraction + filesystem adapter + tests (Phase 2 start).
4. ADO adapter + normalized `LocationRef` persistence + delta tests (Phase 2 completion).
5. Retrieval API boundary + provenance model + ranking tests (Phase 3).
6. Security/policy enforcement + audit/budget tests (Phase 4).
7. VS Code + second-client validation docs and smoke harness (Phase 5).

---

## 6) Definition of done for “full alignment”
All must be true at once:
- Gateway is the only external integration boundary and is MCP-native.
- Index is provider-agnostic with at least filesystem + ADO adapters passing contract tests.
- Retrieval consumes provider-neutral location refs and returns provenance-rich ranked evidence.
- Security/policy controls are enforced and auditable.
- VS Code and at least one additional MCP host can discover and call tools successfully.

---

## 7) Questions that must be answered (no assumptions)
Please answer these before implementation starts:
1. For v1 MCP transport, do you want **stdio**, **streamable HTTP**, or **both**?
2. What auth model should be required in each environment (local/dev/test/prod)?
3. After ADO, which provider should be next priority (GitHub, GitLab, SharePoint, Confluence, etc.)?
4. Is deployment single-tenant or multi-tenant from day one?
5. Who owns persona/classification policy updates, and where should those rules live?
6. What are required p50/p95 latency targets for `search_repo_memory` and `get_context_bundle`?
7. What backward-compatibility window is required for MCP tool schema versions?
8. Which exact VS Code MCP integration and version do you want as the primary supported target?

