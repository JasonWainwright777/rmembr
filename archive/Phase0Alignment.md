# CG_MCP_v0 -- Phase 0: Clarification & Contract Lock

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md

---

## Scope

This cycle covers **Phase 0 only** from the source proposal: defining and locking the contract surface, transport behavior, auth matrix, location index schema, SLO targets, and compatibility policy. No application code is written in this cycle. All outputs are documentation artifacts under `docs/contracts/`.

Subsequent phases (1-6) will be governed as separate cycles after Phase 0 contracts are locked.

---

## SECTION A -- Execution Plan

### Files to create

| # | Path | Purpose |
|---|------|---------|
| 1 | `docs/contracts/gateway-mcp-tools.md` | Canonical MCP tool surface: tool names, JSON schemas (request/response), error codes, auth expectations, versioning metadata |
| 2 | `docs/contracts/location-index-schema.md` | Location index canonical record schema: required/optional fields, tenant_id semantics, provider-agnostic identifiers |
| 3 | `docs/contracts/adr-001-transport-auth-tenancy.md` | ADR documenting: streamable HTTP as primary transport, stdio as dev-only shim, auth matrix by environment (Local/Dev/Test/Prod), single-tenant deployment with multi-tenant-capable schema, 2-release/6-month compatibility window |
| 4 | `docs/contracts/slo-targets.md` | SLO document: p50/p95 targets for `search_repo_memory` and `get_context_bundle`, warm-cache vs cold-start measurement separation, timeout and retry policy |
| 5 | `tests/contracts/validate_tool_schemas.py` | Contract validation script: validates tool schemas against example payloads |
| 6 | `tests/contracts/test_negative_payloads.py` | Negative contract tests: invalid payloads and unauthorized request handling |
| 7 | `tests/contracts/test_deprecation_warnings.py` | Deprecation/compatibility tests: validates alias behavior and telemetry emission |

### Files to modify

None. This is a greenfield documentation cycle.

### Minimal safe change strategy

1. Create `docs/contracts/` directory.
2. Create `tests/contracts/` directory.
3. Write contract documents (files 1-4) based on locked decisions in the source proposal.
4. Write contract validation scripts (files 5-7) that can run standalone against the schema definitions.
5. All contract documents use versioned headers so future changes are trackable.

### Order of operations

1. Create directory structure (`docs/contracts/`, `tests/contracts/`).
2. Write `gateway-mcp-tools.md` -- this is the primary contract that other documents reference.
3. Write `location-index-schema.md` -- defines the data model the tools operate on.
4. Write `adr-001-transport-auth-tenancy.md` -- cross-cutting architectural decisions.
5. Write `slo-targets.md` -- non-functional requirements.
6. Write test scripts (5, 6, 7) -- validation layer for the contracts.
7. Run validation scripts to confirm internal consistency.

### Deployment steps

No deployment. All artifacts are committed to the repository only.

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Contract schemas are underspecified, causing Phase 1 rework | Medium | Medium | Spec Completeness Gate self-check below; Auditor review |
| Tool naming or schema diverges from MCP specification | Low | High | Reference official MCP SDK spec during schema authoring; include spec version in tool contract header |
| Auth matrix gaps leave ambiguous enforcement rules | Medium | High | Enumerate all 4 environments explicitly; require deny-by-default statement |
| SLO targets set without baseline data | Medium | Low | Mark targets as "initial/provisional" with re-evaluation trigger after Phase 1 benchmarks |

### Hidden dependencies

- The MCP tool surface depends on the current gateway handler signatures. If gateway handlers do not yet exist in this repo, tool schemas will be defined as forward-looking contracts (not wrappers around existing code).
- The location index schema depends on ADO's actual API field availability. Schema should include a "provider-specific extension" escape hatch.
- SLO targets reference `search_repo_memory` and `get_context_bundle` -- these tool names must be locked in `gateway-mcp-tools.md` before SLOs reference them.

### Rollback strategy

All changes are new file additions. Rollback is: `git revert <commit>` which removes the added files. No existing files are modified. Per CONSTITUTION.md v0.4, this is a low-risk, fully reversible change.

---

## SECTION C -- Validation Steps

### Closure artifacts required

1. All 4 contract documents exist and contain versioned headers.
2. All 3 test scripts exist and execute without error.
3. Contract validation script (`validate_tool_schemas.py`) passes against the defined schemas.
4. Negative payload tests enumerate at least: missing required fields, wrong types, empty payloads, unauthorized (no token / expired token / wrong scope).
5. Deprecation tests validate at least one compatibility alias scenario.

### Exact commands to produce closure artifacts

```bash
# Verify all contract documents exist
ls docs/contracts/gateway-mcp-tools.md
ls docs/contracts/location-index-schema.md
ls docs/contracts/adr-001-transport-auth-tenancy.md
ls docs/contracts/slo-targets.md

# Run contract validation
python tests/contracts/validate_tool_schemas.py
python -m pytest tests/contracts/test_negative_payloads.py -v
python -m pytest tests/contracts/test_deprecation_warnings.py -v
```

---

## SECTION D -- Auditor Sensitivity

The following items are likely to draw Auditor scrutiny:

1. **Schema completeness**: Tool schemas must include field names, types, required vs optional, and example values. Vague or placeholder schemas will trigger FIX REQUIRED.
2. **Auth matrix specificity**: Each environment (Local/Dev/Test/Prod) must have explicit, non-ambiguous auth requirements. "TBD" entries will trigger FIX REQUIRED.
3. **SLO justification**: Targets copied from the proposal without measurement context. Mitigation: mark as provisional with re-evaluation gate.
4. **MCP spec compliance**: Tool contracts must reference a specific MCP specification version. Auditor will check that schema conventions match the referenced spec.
5. **tenant_id enforcement**: Location index schema must show tenant_id as a required field with explicit isolation semantics, not optional or deferred.
6. **Test coverage gaps**: If negative tests only cover "happy path adjacent" cases (e.g., missing one field) without truly adversarial inputs, Auditor may flag insufficient boundary coverage.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined (field names, types, required vs. optional) -- gateway-mcp-tools.md will contain full JSON Schema definitions for each tool's request and response
- [x] All boundary conditions named -- auth matrix enumerates all 4 environments; SLOs specify p50/p95 with warm/cold separation; compatibility window is 2 releases or 6 months
- [x] All behavioral modes specified -- standard (streamable HTTP), dev-only (stdio), degraded/fallback (provider timeout -> partial response with well-formed error)
- [x] Rollback procedure cites current CONSTITUTION.md version -- rollback is git revert; CONSTITUTION.md v0.4 referenced
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at governance/CONSTITUTION.md, providers.md at governance/providers.md, source proposal at governance/proposals/context-gateway-mcp-full-alignment-plan.md (all confirmed via file reads this session)

READY FOR AUDITOR REVIEW
