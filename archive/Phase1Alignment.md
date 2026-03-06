# CG_MCP_v1 -- Phase 1: Gateway as First-Class MCP Server

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md
prior_cycle: CG_MCP_v0 (Phase 0 -- Clarification & Contract Lock, CLOSED)
implementation_repo: C:\gh_src\rmembr

---

## Scope

This cycle covers **Phase 1** from the source proposal: adding an MCP protocol layer to the existing rMEMbr Context Gateway so it can be discovered and invoked by MCP-compatible clients (VS Code 1.102+, Claude Desktop, etc.).

### Current state of the gateway (confirmed via codebase read)

The gateway is a **FastAPI HTTP service** at `rmembr/mcp-memory-local/services/gateway/src/server.py` (516 lines). It runs on port 8080 and exposes:

- `GET /health` -- multi-service health probe (Index, Standards, Postgres)
- `POST /tools/get_context_bundle` -- orchestrates Index + Standards into a context bundle
- `POST /tools/explain_context_bundle` -- explains a previously assembled bundle
- `POST /tools/validate_pack` -- validates a repo's memory pack
- `POST /proxy/index/{tool}` -- pass-through to Index service (port 8081)
- `POST /proxy/standards/{tool}` -- pass-through to Standards service (port 8082)

**Existing infrastructure that Phase 1 builds on:**
- X-Request-ID correlation middleware (server.py:246-256) with ContextVar propagation to downstream services
- Shared validation module (`services/shared/src/validation/`) with `ValidationError` exception
- Shared structured logging (`services/shared/src/structured_logging.py`) with `TimedOperation` context manager
- `InternalAuthMiddleware` exists in `services/shared/src/auth.py` (used by Index/Standards, NOT by Gateway)
- Bundle caching via PostgreSQL `bundle_cache` table with asyncpg
- Docker Compose orchestration with health checks

**Phase 0 contracts exist in the rMEMbr repo:**
- `docs/contracts/gateway-mcp-tools.md` -- 9 tools defined with full JSON schemas (v0.1.0, MCP spec 2025-03-26)
- `docs/contracts/location-index-schema.md` -- memory_packs, memory_chunks, bundle_cache table schemas
- `docs/contracts/adr-001-transport-auth-tenancy.md` -- transport, auth matrix, tenancy, compatibility policy
- `docs/contracts/slo-targets.md` -- provisional latency targets with warm/cold separation
- `tests/contracts/validate_tool_schemas.py`, `test_negative_payloads.py`, `test_deprecation_warnings.py`

**What does NOT exist yet:** Any MCP protocol code. The gateway is pure REST/HTTP. No MCP SDK dependency, no stdio transport, no MCP tool discovery, no MCP error framing.

---

## SECTION A -- Execution Plan

### Files to create (in rmembr repo)

| # | Path | Purpose |
|---|------|---------|
| 1 | `services/gateway/src/mcp_server.py` | MCP server entry point using Python MCP SDK; registers tools, wires to existing handler functions |
| 2 | `services/gateway/src/mcp_tools.py` | MCP tool definitions: decorators/registration mapping each MCP tool name to the existing handler logic in `server.py` |
| 3 | `services/gateway/src/mcp_errors.py` | MCP error mapping: `ValidationError` -> MCP invalid_params, 502 -> MCP internal_error, 401 -> MCP unauthorized; sanitize all responses |
| 4 | `services/gateway/src/mcp_stdio_shim.py` | Stdio transport entry point (dev-only); gated by `MCP_STDIO_ENABLED` env var (default: false) |
| 5 | `tests/mcp/test_mcp_tools.py` | Unit tests: MCP tool registration, payload coercion, error mapping |
| 6 | `tests/mcp/test_mcp_parity.py` | Parity tests: same request via MCP and HTTP returns equivalent results |
| 7 | `tests/mcp/test_mcp_transport_gating.py` | Transport gating: stdio disabled unless `MCP_STDIO_ENABLED=true` |
| 8 | `tests/mcp/test_mcp_integration.py` | Integration tests: MCP client fixture discovers and calls tools |
| 9 | `tests/mcp/test_mcp_soak.py` | Soak test: repeated MCP invocations for 15+ min, monitor for crash/leak |

### Files to modify (in rmembr repo)

| # | Path | Change |
|---|------|--------|
| 1 | `services/gateway/src/server.py` | Extract handler logic into importable functions (currently inline in route decorators). Add MCP server mounting or separate entry point. Add `MCP_ENABLED` env var check. |
| 2 | `services/gateway/requirements.txt` | Add `mcp` (Python MCP SDK) dependency |
| 3 | `services/gateway/pyproject.toml` | Add `mcp` to dependencies list |
| 4 | `services/gateway/Dockerfile` | No change expected (pip install covers new dependency) |
| 5 | `docker-compose.yml` | Add `MCP_ENABLED` and `MCP_STDIO_ENABLED` env vars to gateway service definition |

### Minimal safe change strategy

1. **Refactor before adding.** Extract the inline handler logic in `server.py` route decorators into standalone async functions (e.g., `async def handle_get_context_bundle(params) -> dict`). This is a prerequisite for MCP tool registration without duplicating business logic.

2. **Additive MCP layer.** MCP server code lives in new files (`mcp_server.py`, `mcp_tools.py`, `mcp_errors.py`). The existing FastAPI app and all HTTP endpoints remain unchanged.

3. **Feature-flagged activation.** `MCP_ENABLED` env var (default: `false`). When true, the MCP server starts alongside the HTTP server. When false, only HTTP is available. This allows incremental rollout.

4. **Transport gating.** `MCP_STDIO_ENABLED` env var (default: `false`). Stdio shim only activates when explicitly enabled AND `MCP_ENABLED=true`. Production docker-compose never sets this to true.

5. **Shared correlation IDs.** MCP requests generate/propagate X-Request-ID via the existing `request_id_var` ContextVar from `shared/src/structured_logging.py`. No new middleware needed -- just set the ContextVar at MCP request entry.

6. **Shared auth.** Gateway currently has no client-facing auth middleware (ADR-001 confirms Local env is open). MCP requests follow the same policy. Client auth (Dev/Test/Prod) is a future Phase deliverable per ADR-001.

### Order of operations

1. **Refactor handlers** -- Extract inline handler logic from `server.py` route decorators into importable functions. Existing HTTP routes call these functions. Run existing tests to confirm no regression.

2. **Add MCP SDK dependency** -- Add `mcp` to `requirements.txt` and `pyproject.toml`. Verify compatibility with Python 3.12 and existing FastAPI stack.

3. **Implement MCP tool definitions** (`mcp_tools.py`) -- Register 9 tools from `docs/contracts/gateway-mcp-tools.md`:
   - `search_repo_memory` (proxied to Index)
   - `get_context_bundle` (gateway handler)
   - `explain_context_bundle` (gateway handler)
   - `validate_pack` (gateway handler)
   - `index_repo` (proxied to Index)
   - `index_all` (proxied to Index)
   - `list_standards` (proxied to Standards)
   - `get_standard` (proxied to Standards)
   - `get_schema` (proxied to Standards)

4. **Implement MCP error mapping** (`mcp_errors.py`) -- Map:
   - `ValidationError` -> MCP `InvalidParams` (-32602)
   - HTTP 401 -> MCP error with "unauthorized" code
   - HTTP 502 (service timeout/error) -> MCP `InternalError` (-32603) with sanitized message
   - All responses stripped of internal paths, stack traces, token values

5. **Implement MCP server** (`mcp_server.py`) -- Streamable HTTP transport using MCP SDK. Mount as separate ASGI app or run on separate port. Set `request_id_var` ContextVar at request entry for correlation.

6. **Implement stdio shim** (`mcp_stdio_shim.py`) -- Reuses same tool definitions. Gated by `MCP_STDIO_ENABLED` env var. Entry point: `python -m src.mcp_stdio_shim`.

7. **Update docker-compose** -- Add `MCP_ENABLED` and `MCP_STDIO_ENABLED` env vars (both default false).

8. **Write tests** -- Unit, parity, transport gating, integration, soak (files 5-9 above).

9. **Validate** -- Run full test suite, confirm parity, confirm transport gating, run soak test.

### Deployment steps

1. Merge to main behind `MCP_ENABLED=false` (no behavior change).
2. Set `MCP_ENABLED=true` in local docker-compose; run integration + parity tests.
3. Validate with VS Code 1.102+ MCP client: tool discovery, invocation, response rendering.
4. Monitor logs for X-Request-ID completeness across MCP -> Gateway -> Index/Standards chain.

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Handler refactor introduces regression in existing HTTP endpoints | Medium | High | Run existing `tests/contracts/` suite after refactor, before adding MCP code. Existing tests: `validate_tool_schemas.py`, `test_negative_payloads.py`, `test_deprecation_warnings.py`. |
| Python MCP SDK incompatible with FastAPI 0.115+ or Python 3.12 | Low | High | Pin MCP SDK version in requirements. Test import and basic registration before full implementation. |
| MCP server and HTTP server port conflict or resource contention | Medium | Medium | Options: (a) mount MCP as ASGI sub-app on same uvicorn, (b) separate port. Decide during implementation; both are testable. |
| Stdio shim accidentally enabled in docker-compose production profile | Low | High | Transport gating test. docker-compose.yml never sets `MCP_STDIO_ENABLED=true`. CI check. |
| MCP error mapping leaks internal service URLs or token values | Medium | High | MCP error sanitization in `mcp_errors.py`. Integration test validates no internal URLs (`http://index:8081`, `http://standards:8082`) or token patterns appear in MCP error responses. |
| Correlation ID not propagated from MCP entry to downstream services | Low | Medium | MCP request handler sets `request_id_var` ContextVar (same mechanism as HTTP middleware at server.py:246-256). Integration test validates X-Request-ID in downstream logs. |
| SLO degradation from MCP protocol overhead vs direct HTTP | Medium | Low | MCP adds framing overhead. SLO targets are provisional (slo-targets.md). Benchmark after implementation; MCP overhead should be <50ms per request. |

### Hidden dependencies

- **Python MCP SDK maturity.** The `mcp` Python package must support streamable HTTP transport and tool registration. If it doesn't, a custom MCP protocol adapter is needed (significantly more work).
- **asyncpg pool sharing.** If MCP server runs in the same process, it shares the asyncpg connection pool initialized in `server.py:213-240` (lifespan). If separate process, pool must be initialized independently.
- **Shared module path.** Dockerfile sets `PYTHONPATH="/app/shared/src:/app/gateway"`. MCP entry points must use the same PYTHONPATH or be added to it.

### Rollback strategy

Per CONSTITUTION.md v0.4:

1. **Feature flag rollback:** Set `MCP_ENABLED=false` in docker-compose env. MCP server does not start. All HTTP endpoints unaffected. Rollback time: config change + `docker compose up -d` (~2 min).
2. **Code rollback:** `git revert` the MCP commits. All MCP code is in new files. The only modified existing file is `server.py` (handler extraction refactor), which is a pure refactor with no behavior change -- but revert is still clean. Rollback time: ~10 min.
3. **Dependency rollback:** Remove `mcp` from `requirements.txt`. Rebuild container. Rollback time: ~5 min.

---

## SECTION C -- Validation Steps

### Acceptance criteria (from source proposal Phase 1)

1. MCP client can discover and invoke gateway tools successfully.
2. Streamable HTTP path is enabled by default for deployable environments; stdio is disabled outside approved dev profiles.
3. Same task returns equivalent results via MCP and existing HTTP paths.
4. Logs show end-to-end correlation ID and timing spans.

### Closure artifacts required

1. **Handler refactor regression pass:** Existing `tests/contracts/` tests pass after handler extraction.
2. **MCP unit tests pass:** Tool registration, payload coercion, error mapping validated.
3. **MCP parity tests pass:** Same request via MCP and HTTP returns equivalent response bodies.
4. **Transport gating tests pass:** Stdio cannot activate without `MCP_STDIO_ENABLED=true`.
5. **MCP integration tests pass:** MCP client fixture discovers tools, calls `get_context_bundle` and `search_repo_memory`.
6. **Soak test pass:** 15+ min repeated MCP invocations, no crash or memory leak.
7. **Error sanitization verified:** No internal URLs, paths, or tokens in MCP error responses.

### Exact commands to produce closure artifacts

```bash
# All commands run from rmembr/mcp-memory-local/ with services up via docker compose

# 1. Regression -- existing contract tests
python -m pytest tests/contracts/validate_tool_schemas.py -v
python -m pytest tests/contracts/test_negative_payloads.py -v
python -m pytest tests/contracts/test_deprecation_warnings.py -v

# 2. MCP unit tests
python -m pytest tests/mcp/test_mcp_tools.py -v

# 3. MCP parity tests
python -m pytest tests/mcp/test_mcp_parity.py -v

# 4. Transport gating tests
python -m pytest tests/mcp/test_mcp_transport_gating.py -v

# 5. MCP integration tests (requires running services)
docker compose up -d
python -m pytest tests/mcp/test_mcp_integration.py -v

# 6. Soak test (15 min minimum)
python -m pytest tests/mcp/test_mcp_soak.py -v --timeout=1200

# 7. Error sanitization (included in unit and integration tests)
# Validated by assertions in test_mcp_tools.py and test_mcp_integration.py
```

---

## SECTION D -- Auditor Sensitivity

1. **Handler refactor risk.** Extracting inline logic from route decorators in `server.py` is the highest-risk change because it modifies the only existing production file. Auditor will verify the refactor is behavior-preserving. Mitigation: existing contract tests run before AND after refactor; diff will show pure extraction with no logic changes.

2. **Transport security.** Stdio shim must be provably non-activatable without explicit opt-in. Auditor will check the env var gating and test coverage. Mitigation: `MCP_STDIO_ENABLED` defaults to false; transport gating test is an explicit closure artifact; docker-compose.yml never sets it to true.

3. **Error information leakage.** MCP error responses must not expose `http://index:8081`, `http://standards:8082`, `INTERNAL_SERVICE_TOKEN`, or Python stack traces. Auditor will check `mcp_errors.py` sanitization logic. Mitigation: dedicated error mapping module with explicit allowlist of user-visible fields; integration test asserts no internal patterns in responses.

4. **MCP SDK supply chain.** Adding a new dependency (`mcp` package). Auditor will check: (a) package source/maintainer, (b) pinned version, (c) no known CVEs. Mitigation: pin exact version in requirements.txt; verify PyPI package metadata.

5. **Auth gap.** Gateway currently has no client-facing auth (Local env per ADR-001). MCP inherits this gap. Auditor may flag that MCP makes the unauthenticated surface more accessible. Mitigation: ADR-001 explicitly states "Gateway currently does not enforce client auth (Local environment). Dev/Test/Prod client auth is a Phase 1 deliverable." This plan adds MCP but does not change the auth boundary. Client auth is tracked for a future cycle.

6. **Correlation ID completeness.** MCP requests must set `request_id_var` ContextVar so downstream calls include X-Request-ID. Auditor will check that the existing mechanism (server.py:246-256, shared/structured_logging.py) is reused, not duplicated. Mitigation: plan specifies reuse of existing ContextVar; integration test validates end-to-end ID.

7. **Parity completeness.** Parity tests must cover all 9 tools defined in `gateway-mcp-tools.md`, not just the 2-3 gateway-native tools. Auditor will check coverage breadth. Mitigation: parity test matrix explicitly covers all 9 tools.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined (field names, types, required vs. optional) -- 9 MCP tools fully defined in `docs/contracts/gateway-mcp-tools.md` with JSON Schema for request/response; MCP error codes defined in `mcp_errors.py` spec (InvalidParams -32602, InternalError -32603, unauthorized)
- [x] All boundary conditions named -- transport gating (`MCP_STDIO_ENABLED` default false); feature flag (`MCP_ENABLED` default false); SLO targets from `docs/contracts/slo-targets.md` (provisional, p50/p95 warm/cold); soak test minimum 15 min; compatibility window 2 releases or 6 months per `docs/contracts/adr-001-transport-auth-tenancy.md`; max bundle size 40,000 chars; k range 1-100; query maxLength 2000
- [x] All behavioral modes specified -- standard (HTTP + MCP both active, `MCP_ENABLED=true`), HTTP-only (`MCP_ENABLED=false`, default), dev-stdio (`MCP_STDIO_ENABLED=true`, local only), degraded (Index/Standards down -> MCP returns structured error via `mcp_errors.py`, Gateway health reports "degraded")
- [x] Rollback procedure cites current CONSTITUTION.md version -- CONSTITUTION.md v0.4; rollback via feature flag (`MCP_ENABLED=false`) or `git revert`; all MCP code in new files except `server.py` handler extraction
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at `governance/CONSTITUTION.md`, providers.md at `governance/providers.md`, source proposal at `governance/proposals/context-gateway-mcp-full-alignment-plan.md`, Phase 0 contracts at `rmembr/docs/contracts/` (4 docs confirmed), prior cycle at `governance/plans/CG_MCP/CG_MCP_v0.md` (all confirmed via file reads this session)

READY FOR AUDITOR REVIEW
