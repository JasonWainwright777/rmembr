# CG_MCP_v7 -- Phase 4: Policy, Security, and Tenancy Hardening

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md
prior_cycle: CG_MCP_v6 (Phase 3 -- Retrieval Engine Separation and Normalization, CLOSED)
prior_version: n/a (first version for Phase 4)
implementation_repo: C:\gh_src\rmembr

---

## Scope

This cycle covers **Phase 4** from the source proposal: policy, security, and tenancy hardening. The source proposal defines five tasks:

1. Enforce persona/classification policy at gateway prior to response assembly.
2. Add per-tool authorization checks and deny-by-default paths.
3. Add audit logging for tool call subject, repo scope, and returned provenance references.
4. Implement request budget controls (token/content limits, max sources, timeout caps).
5. Integrate policy bundle loading from versioned artifact with startup load and non-prod hot reload.

### Recommended Next Actions (carried from Phase 3 closure)

The v6 closure artifact identified Phase 4 as the next cycle. No carry-forward items from v6 require resolution -- the audit achieved clean PASS.

### Current state (confirmed via codebase read)

**What already exists and should be preserved:**

- **Persona/classification filtering** (`server.py:144-147`): `_filter_by_classification()` filters chunks by persona using `PERSONA_CLASSIFICATION` dict. Currently hardcoded in gateway server.py.
- **Internal service auth** (`shared/src/auth.py`): `InternalAuthMiddleware` enforces `X-Internal-Token` on Index and Standards. Gateway injects this header for internal calls.
- **Input validation** (`shared/src/validation/validators.py`): Validates repo, query, k, namespace, filters, standard_id. Rejects path traversal.
- **Structured JSON logging** (`shared/src/structured_logging.py`): JSON formatter with `request_id`, `tool`, `duration_ms`, `service`. `TimedOperation` context manager. `X-Request-ID` propagation via `request_id_var` contextvar.
- **MCP error sanitization** (`gateway/src/mcp_errors.py`): Strips internal URLs, token refs, container paths, stack traces from MCP error responses.
- **Budget controls (partial)**: `GATEWAY_MAX_BUNDLE_CHARS` (40000), `GATEWAY_DEFAULT_K` (12), `BUNDLE_CACHE_TTL_SECONDS` (300). No per-tool timeout caps. No max-sources limit distinct from `k`.
- **MCP tool dispatch** (`gateway/src/mcp_tools.py`): 9 tools registered. No per-tool auth checks -- all tools are callable by any client.
- **Request ID middleware** (`server.py:249-259`): Generates/propagates `X-Request-ID` on all gateway requests.

**What does NOT exist yet:**

- No per-tool authorization (any MCP client can call any tool including `index_repo`, `index_all`).
- No deny-by-default posture -- all tools are open.
- No audit log records for tool calls (only operational logs exist).
- No per-tool timeout caps (gateway uses 30s for Index, 120s for proxy -- not configurable per tool).
- No max-sources limit separate from `k`.
- No policy-as-code bundle (persona/classification mapping is hardcoded in server.py).
- No policy hot-reload mechanism.
- No `tenant_id` enforcement at gateway boundary (namespace exists but is not validated against auth claims).

---

## SECTION A -- Execution Plan

### Micro-task list

| # | Task | Source proposal ref | Time est. | Risk | Validation artifact |
|---|------|---------------------|-----------|------|---------------------|
| 1 | Create policy types module | Task 5 | 30 min | Low | Unit tests pass |
| 2 | Create policy loader with startup load and non-prod hot reload | Task 5 | 45 min | Medium | Unit tests pass, reload test pass |
| 3 | Create per-tool authorization middleware | Task 2 | 45 min | High | Allow/deny matrix tests pass |
| 4 | Create audit logger module | Task 3 | 30 min | Low | Audit log format tests pass |
| 5 | Refactor gateway to use policy-driven classification | Task 1 | 30 min | Medium | Existing contract tests pass, policy tests pass |
| 6 | Add per-tool timeout and max-sources budget controls | Task 4 | 30 min | Medium | Budget tests pass |
| 7 | Wire policy loader and auth middleware into gateway lifespan | Tasks 1-5 | 30 min | Medium | Integration tests pass |
| 8 | Wire audit logging into MCP dispatch and HTTP handlers | Task 3 | 30 min | Low | Audit log integration tests pass |
| 9 | Update docker-compose with new env vars | Tasks 2-5 | 15 min | Low | Services start with defaults |
| 10 | Write all tests | Tasks 1-5 | 60 min | Low | Full test suite passes |

### Files to create (in rmembr repo)

| # | Path | Purpose |
|---|------|---------|
| 1 | `services/gateway/src/policy/__init__.py` | Package init; exports `PolicyBundle`, `PolicyLoader`, `ToolAuthz` |
| 2 | `services/gateway/src/policy/types.py` | Policy DTOs: `PolicyBundle`, `PersonaPolicy`, `ToolPolicy`, `BudgetPolicy` |
| 3 | `services/gateway/src/policy/loader.py` | `PolicyLoader`: loads policy from file or defaults, optional non-prod hot reload via file watcher |
| 4 | `services/gateway/src/policy/authz.py` | `ToolAuthz`: per-tool authorization checks, deny-by-default, role-based allow lists |
| 5 | `services/shared/src/audit_log.py` | `AuditLogger`: structured audit log records for tool calls with subject, repo, tool, provenance refs, correlation ID |
| 6 | `tests/policy/__init__.py` | Test package init |
| 7 | `tests/policy/test_types.py` | Unit tests for policy DTOs |
| 8 | `tests/policy/test_loader.py` | Unit tests for PolicyLoader (startup load, reload, defaults) |
| 9 | `tests/policy/test_authz.py` | Unit tests for ToolAuthz allow/deny matrix |
| 10 | `tests/policy/test_audit_log.py` | Unit tests for AuditLogger format and fields |
| 11 | `tests/policy/test_integration.py` | Integration tests: policy-driven gateway behavior end-to-end |
| 12 | `tests/policy/test_budget.py` | Budget control tests: per-tool timeouts, max-sources rejection/truncation |
| 13 | `mcp-memory-local/policy/default_policy.json` | Default policy bundle file (ships with repo) |

### Files to modify (in rmembr repo)

| # | Path | Change |
|---|------|--------|
| 1 | `services/gateway/src/server.py` | Replace hardcoded `PERSONA_CLASSIFICATION` with policy-driven lookup. Add `PolicyLoader` init in lifespan. Add per-tool timeout and max-sources from policy. Wire `AuditLogger` into request flow. |
| 2 | `services/gateway/src/mcp_tools.py` | Add `ToolAuthz` check before dispatch. Add `AuditLogger` call after dispatch. Add per-tool budget enforcement (timeout, max_sources). |
| 3 | `services/gateway/src/mcp_errors.py` | Add `AuthorizationError` mapping to MCP error code (use INVALID_PARAMS or custom code). |
| 4 | `services/shared/src/structured_logging.py` | Add `audit_event` helper that emits structured audit log records with required fields (subject, tool, repo, action, provenance_refs, correlation_id, timestamp). |
| 5 | `mcp-memory-local/docker-compose.yml` | Add `POLICY_FILE`, `POLICY_HOT_RELOAD`, `GATEWAY_TOOL_TIMEOUT_*`, `GATEWAY_MAX_SOURCES` env vars to gateway service. |

### Policy bundle schema (default_policy.json)

```json
{
  "version": "1.0",
  "persona_classification": {
    "human": ["public", "internal"],
    "agent": ["public", "internal"],
    "external": ["public"]
  },
  "tool_authorization": {
    "default_action": "deny",
    "roles": {
      "reader": {
        "allowed_tools": [
          "search_repo_memory",
          "get_context_bundle",
          "explain_context_bundle",
          "validate_pack",
          "list_standards",
          "get_standard",
          "get_schema"
        ]
      },
      "writer": {
        "allowed_tools": [
          "index_repo",
          "index_all"
        ]
      }
    },
    "default_role": "reader"
  },
  "budgets": {
    "max_bundle_chars": 40000,
    "max_sources": 50,
    "default_k": 12,
    "tool_timeouts": {
      "search_repo_memory": 10,
      "get_context_bundle": 30,
      "explain_context_bundle": 5,
      "validate_pack": 10,
      "index_repo": 120,
      "index_all": 300,
      "list_standards": 5,
      "get_standard": 5,
      "get_schema": 5
    },
    "cache_ttl_seconds": 300
  }
}
```

### Policy type definitions

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class PersonaPolicy:
    """Persona -> allowed classification levels."""
    allowed_classifications: dict[str, list[str]]
    # e.g. {"human": ["public", "internal"], "external": ["public"]}

@dataclass(frozen=True)
class ToolPolicy:
    """Per-tool authorization rules."""
    default_action: str  # "deny" or "allow"
    roles: dict[str, list[str]]  # role_name -> list of allowed tool names
    default_role: str  # role assigned when no explicit role claim

@dataclass(frozen=True)
class BudgetPolicy:
    """Request budget controls."""
    max_bundle_chars: int = 40000
    max_sources: int = 50
    default_k: int = 12
    tool_timeouts: dict[str, int] = field(default_factory=dict)
    cache_ttl_seconds: int = 300

@dataclass(frozen=True)
class PolicyBundle:
    """Complete policy configuration."""
    version: str
    persona: PersonaPolicy
    tool_auth: ToolPolicy
    budgets: BudgetPolicy

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyBundle":
        """Parse from JSON dict."""
        ...

    @classmethod
    def defaults(cls) -> "PolicyBundle":
        """Return default policy matching current hardcoded behavior."""
        ...
```

### ToolAuthz

```python
class ToolAuthz:
    """Per-tool authorization enforcement."""

    def __init__(self, policy: ToolPolicy):
        self.policy = policy
        # Pre-compute role -> tool set for fast lookup
        self._role_tools: dict[str, set[str]] = {
            role: set(tools) for role, tools in policy.roles.items()
        }

    def authorize(self, tool_name: str, role: str | None = None) -> bool:
        """Check if the given role is authorized to call the tool.

        Returns True if authorized, False if denied.
        Uses default_role when role is None.
        """
        effective_role = role or self.policy.default_role
        allowed = self._role_tools.get(effective_role, set())
        if tool_name in allowed:
            return True
        if self.policy.default_action == "allow":
            return True
        return False
```

### AuditLogger

```python
class AuditLogger:
    """Structured audit log for tool call events."""

    def __init__(self, logger):
        self.logger = logger

    def log_tool_call(
        self,
        tool: str,
        action: str,  # "invoke", "deny", "error"
        subject: str,  # caller identity (role or "anonymous")
        repo: str | None = None,
        provenance_refs: list[str] | None = None,
        correlation_id: str = "",
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        """Emit a structured audit log record."""
        record = {
            "audit": True,
            "tool": tool,
            "action": action,
            "subject": subject,
            "repo": repo or "",
            "provenance_refs": provenance_refs or [],
            "correlation_id": correlation_id,
        }
        if duration_ms is not None:
            record["duration_ms"] = duration_ms
        if error:
            record["error"] = error
        self.logger.info("audit_event", extra=record)
```

### PolicyLoader

```python
class PolicyLoader:
    """Loads PolicyBundle from file or defaults. Supports non-prod hot reload."""

    def __init__(self, policy_file: str | None = None, hot_reload: bool = False):
        self._policy_file = policy_file
        self._hot_reload = hot_reload
        self._policy: PolicyBundle | None = None
        self._file_mtime: float = 0.0

    def load(self) -> PolicyBundle:
        """Load policy from file, or return defaults if no file configured."""
        if not self._policy_file:
            self._policy = PolicyBundle.defaults()
            return self._policy
        # Read and parse file
        ...

    @property
    def policy(self) -> PolicyBundle:
        """Get current policy, reloading from file if hot_reload enabled and file changed."""
        if self._hot_reload and self._policy_file:
            # Check file mtime, reload if changed
            ...
        if not self._policy:
            return self.load()
        return self._policy
```

### Minimal safe change strategy

1. **Policy-driven, backward compatible.** Default policy file exactly replicates current hardcoded behavior (same persona/classification map, same budgets). Removing the policy file or env vars falls back to defaults. Current behavior is preserved unless explicitly overridden.

2. **Deny-by-default for write tools.** `index_repo` and `index_all` are restricted to `writer` role. All read-only tools are available to the default `reader` role. This matches the natural security boundary -- indexing is a write operation.

3. **Additive auth layer.** Authorization checks are added to MCP dispatch and HTTP proxy endpoints. Existing internal auth (`X-Internal-Token`) is unchanged. The new layer operates at the gateway boundary only.

4. **Audit logging is observability, not blocking.** Audit log records are emitted alongside operational logs via the existing structured logging infrastructure. No new log transport or storage -- uses existing JSON stdout logging. Audit records are distinguished by `"audit": true` field.

5. **No schema migrations.** No DB changes. Policy is file-based, not DB-stored.

6. **Hot reload is non-prod only.** `POLICY_HOT_RELOAD=true` is only effective when `POLICY_FILE` is set. Default is `false`. File mtime comparison avoids polling overhead.

### Order of operations

1. **Create policy types** -- `policy/types.py` with `PersonaPolicy`, `ToolPolicy`, `BudgetPolicy`, `PolicyBundle` dataclasses. Include `from_dict()` and `defaults()` class methods.

2. **Create default policy file** -- `mcp-memory-local/policy/default_policy.json` matching current hardcoded behavior.

3. **Create policy loader** -- `policy/loader.py` with `PolicyLoader`. File-based loading with optional hot reload.

4. **Create tool authz** -- `policy/authz.py` with `ToolAuthz`. Deny-by-default, role-based allow lists.

5. **Create audit logger** -- `shared/src/audit_log.py` with `AuditLogger`. Structured records with required fields.

6. **Refactor server.py (Gateway)** -- Replace `PERSONA_CLASSIFICATION` with `PolicyLoader.policy.persona`. Add `PolicyLoader` init in lifespan. Replace hardcoded budget constants with policy-driven values. Wire `AuditLogger`.

7. **Update mcp_tools.py** -- Add `ToolAuthz.authorize()` call before dispatch. Add `AuditLogger.log_tool_call()` after dispatch. Enforce per-tool timeouts from `BudgetPolicy.tool_timeouts`.

8. **Update mcp_errors.py** -- Add `AuthorizationError` exception class and mapping.

9. **Update docker-compose** -- Add `POLICY_FILE`, `POLICY_HOT_RELOAD`, `GATEWAY_MAX_SOURCES` env vars to gateway service.

10. **Write tests** -- Policy type tests, loader tests, authz matrix tests, audit log tests, budget tests, integration tests (files 7-12 above).

11. **Validate** -- Run full test suite including existing contract tests and MCP tests to confirm no regression.

### Deployment steps

1. Merge with default policy (behavioral no-op -- persona map, budgets, and read-tool access match current behavior). Only change: `index_repo` and `index_all` require `writer` role (previously unrestricted).
2. Run existing contract tests + MCP tests + new policy tests.
3. Verify all 9 MCP tools respond correctly for `reader` role (7 allowed, 2 denied).
4. Verify `index_repo` and `index_all` work when called with `writer` role.
5. Verify audit log records appear in gateway stdout for each tool call.
6. Verify policy hot reload works in dev (change file, observe new behavior without restart).

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Deny-by-default blocks legitimate tool calls | Medium | High | Default policy grants `reader` role access to all 7 read-only tools. Only `index_repo`/`index_all` restricted. MCP tool tests validate allow/deny matrix. |
| Policy file parsing failure on startup | Low | High | `PolicyLoader.load()` falls back to `PolicyBundle.defaults()` on parse error and logs warning. Gateway starts with safe defaults. |
| Hot reload causes mid-request policy inconsistency | Low | Medium | Policy is loaded atomically (read file, parse, replace reference). No partial updates. `frozen=True` dataclasses ensure immutability after load. |
| Per-tool timeout too aggressive for large repos | Medium | Medium | Default timeouts match or exceed current behavior (30s for get_context_bundle, 120s for index_repo). Configurable via policy file. |
| Audit logging volume impacts performance | Low | Low | Audit records are one JSON line per tool call. No DB writes. Follows existing structured logging pattern. |
| Refactoring PERSONA_CLASSIFICATION breaks classification filter | Medium | Medium | Default policy `persona_classification` map is identical to current hardcoded dict. Contract tests and existing integration tests verify parity. |
| mcp_tools.py authz check breaks MCP dispatch flow | Medium | High | AuthorizationError is mapped to MCP error response via mcp_errors.py. Denied calls return structured error, not unhandled exception. All 9 tools tested in authz matrix. |
| max_sources budget interacts with k parameter | Low | Medium | `max_sources` caps the upper bound of `k`. If `k > max_sources`, `k` is clamped to `max_sources`. Validation tests cover this interaction. |

### Hidden dependencies

- **MCP dispatch path.** `mcp_tools.py:dispatch_tool()` is the single entry point for all MCP tool calls. Auth check must be inserted before the `kind`/`target` dispatch. Error handling must catch `AuthorizationError` and map it correctly.
- **HTTP endpoint path.** Gateway HTTP endpoints (`/tools/*`, `/proxy/*`) do not go through MCP dispatch. Auth checks for HTTP path must be added separately or via middleware.
- **Policy file location.** `POLICY_FILE` env var must resolve inside the container. Docker-compose volume mount needed if policy file is external.
- **Existing test fixtures.** Contract tests (`tests/contracts/`) call tools via HTTP without role claims. These must continue to pass with default policy (reader role allows all read tools).

### Rollback strategy

Per CONSTITUTION.md v0.4:

1. **Config rollback:** Remove `POLICY_FILE`, `POLICY_HOT_RELOAD`, `GATEWAY_MAX_SOURCES` env vars. Gateway falls back to hardcoded defaults (same as pre-Phase 4 behavior).
2. **Code rollback:** `git revert` the policy commits. New `policy/` directory deleted. `server.py`, `mcp_tools.py`, `mcp_errors.py` revert to prior state. `audit_log.py` deleted. No schema changes to revert.
3. **No schema rollback needed.** No DDL changes in this cycle.
4. **Rollback time:** ~5 min for code revert, ~2 min for docker compose restart.

---

## SECTION C -- Validation Steps

### Acceptance criteria (from source proposal Phase 4)

1. Unauthorized tool calls are denied with structured error responses.
2. Sensitive chunks are excluded according to persona/classification rules.
3. Audit log records are queryable and include correlation IDs.
4. Policy changes are traceable to reviewed Git commits and deployment pipeline records.

### Closure artifacts required

1. **Regression pass:** Existing `tests/contracts/` and `tests/mcp/` tests pass after gateway refactor.
2. **Policy type tests pass:** `test_types.py` validates `PolicyBundle`, `PersonaPolicy`, `ToolPolicy`, `BudgetPolicy` creation, serialization, and `from_dict()` round-trip.
3. **Policy loader tests pass:** `test_loader.py` validates startup load from file, fallback to defaults on missing/invalid file, and hot reload detection (file mtime change triggers reload, no change returns cached policy).
4. **Auth matrix tests pass:** `test_authz.py` validates complete allow/deny matrix:
   - `reader` role: 7 read tools allowed, `index_repo` denied, `index_all` denied.
   - `writer` role: `index_repo` allowed, `index_all` allowed, read tools denied (writer is a scoped role).
   - No role / unknown role: falls back to `default_role` (reader).
   - `default_action=deny`: unknown tool name denied for any role.
5. **Audit log tests pass:** `test_audit_log.py` validates:
   - `log_tool_call()` emits JSON with required fields: `audit=true`, `tool`, `action`, `subject`, `correlation_id`, `timestamp`.
   - `action="invoke"` for successful calls includes `repo`, `duration_ms`.
   - `action="deny"` for unauthorized calls includes `tool`, `subject`.
   - `action="error"` for failed calls includes `error` field (sanitized).
   - `provenance_refs` list included when provided.
6. **Budget tests pass:** `test_budget.py` validates:
   - Per-tool timeout from policy is applied (mock httpx client asserts timeout value).
   - `max_sources` clamps `k` when `k > max_sources`.
   - Oversized `k` rejected when `k > max_sources` and `max_sources < 100`.
7. **Integration test pass:** `test_integration.py` validates end-to-end:
   - Tool call with `reader` role returns results.
   - Tool call with `reader` role on `index_repo` returns structured deny error.
   - Audit log records emitted for both allowed and denied calls.
   - Policy-driven classification filtering produces same results as prior hardcoded filtering for default policy.
8. **MCP dispatch auth integration:** MCP tool call to `index_repo` without writer role returns MCP error response (not unhandled exception). MCP tool call to `search_repo_memory` with default/reader role succeeds.
9. **Policy hot reload:** In non-prod mode (`POLICY_HOT_RELOAD=true`), modifying `default_policy.json` persona map is reflected in next tool call without gateway restart. In prod mode (`POLICY_HOT_RELOAD=false`), file changes have no effect until restart.

### Exact commands to produce closure artifacts

```bash
# All commands run from rmembr/ with services up via docker compose

# 1. Regression -- existing contract and MCP tests
python -m pytest tests/contracts/ -v
python -m pytest tests/mcp/ -v

# 2. Policy type tests
python -m pytest tests/policy/test_types.py -v

# 3. Policy loader tests
python -m pytest tests/policy/test_loader.py -v

# 4. Auth matrix tests
python -m pytest tests/policy/test_authz.py -v

# 5. Audit log tests
python -m pytest tests/policy/test_audit_log.py -v

# 6. Budget tests
python -m pytest tests/policy/test_budget.py -v

# 7. Integration tests (requires running services)
docker compose up -d
python -m pytest tests/policy/test_integration.py -v

# 8. MCP dispatch auth (subset of integration)
python -m pytest tests/policy/test_integration.py::test_mcp_deny_index_repo -v
python -m pytest tests/policy/test_integration.py::test_mcp_allow_search -v

# 9. Policy hot reload
python -m pytest tests/policy/test_loader.py::test_hot_reload_detects_change -v
python -m pytest tests/policy/test_loader.py::test_no_reload_when_disabled -v
```

---

## SECTION D -- Auditor Sensitivity

1. **Deny-by-default correctness.** Auditor will verify that the default policy does not accidentally block tools that existing tests and workflows depend on. Mitigation: default policy grants `reader` role all 7 read-only tools. Only `index_repo`/`index_all` are restricted. Auth matrix test covers all 9 tools x 2 roles + unknown role.

2. **Backward compatibility of gateway behavior.** Auditor will verify that default policy produces identical persona/classification filtering, budget behavior, and tool responses as the pre-Phase 4 code. Mitigation: `PolicyBundle.defaults()` returns values matching current hardcoded constants. Integration test compares old and new filtering paths.

3. **Audit log completeness.** Auditor will verify that audit records include all fields needed for security review (subject, tool, repo, correlation_id, provenance_refs). Mitigation: `AuditLogger` has required fields enforced by method signature. Test validates JSON structure.

4. **Policy file security.** Auditor will check that policy file parsing is safe (no code execution, no injection). Mitigation: `PolicyLoader` uses `json.load()` only. Policy DTOs are `frozen=True` dataclasses with typed fields. No `eval()` or `exec()`.

5. **Hot reload atomicity.** Auditor will verify that hot reload cannot produce a partially-loaded policy. Mitigation: Loader reads entire file, parses into new `PolicyBundle`, then atomically replaces the reference. `frozen=True` ensures no mutation after creation.

6. **Auth check placement.** Auditor will verify that auth checks cannot be bypassed via alternative dispatch paths (HTTP proxy, direct handler call). Mitigation: Auth check is in `dispatch_tool()` for MCP path and in a middleware for HTTP proxy endpoints. Both paths documented and tested.

7. **Per-tool timeout interaction with existing timeouts.** Auditor will verify that policy-driven timeouts do not conflict with hardcoded httpx timeouts. Mitigation: Policy timeout replaces the hardcoded timeout value. `httpx.AsyncClient(timeout=policy_timeout)` used consistently.

8. **max_sources budget behavior.** Auditor will verify that `max_sources` correctly interacts with `k` parameter without silent data loss. Mitigation: when `k > max_sources`, `k` is clamped and a warning is logged. No silent truncation -- behavior is explicit and logged.

9. **Scope completeness.** Auditor will verify that declared modification scope (Files to modify table, 5 rows) matches execution steps (Order of operations steps 6-9). Files to create table (13 rows) matches steps 1-5 and 10.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined -- `PolicyBundle` (4 fields: version str required, persona PersonaPolicy required, tool_auth ToolPolicy required, budgets BudgetPolicy required). `PersonaPolicy` (1 field: allowed_classifications dict[str, list[str]] required). `ToolPolicy` (3 fields: default_action str required, roles dict[str, list[str]] required, default_role str required). `BudgetPolicy` (5 fields: max_bundle_chars int default 40000, max_sources int default 50, default_k int default 12, tool_timeouts dict[str, int] default {}, cache_ttl_seconds int default 300). Audit log record: audit bool=true, tool str required, action str required ("invoke"|"deny"|"error"), subject str required, repo str optional, provenance_refs list[str] optional, correlation_id str required, duration_ms float optional, error str optional. Authorization error response: MCP INVALID_PARAMS code with sanitized message "Unauthorized: tool '{name}' requires role '{required_role}'".
- [x] All boundary conditions named -- `default_action="deny"`: unknown tool name denied for all roles. `default_role="reader"`: applied when no role claim present. `max_sources=50`: clamps `k` when `k > max_sources` (log warning). `tool_timeouts` defaults: per-tool values specified in schema (5s-300s range). Hot reload: only when `POLICY_HOT_RELOAD=true` AND `POLICY_FILE` is set. File mtime unchanged -> no reload. Parse error -> retain previous policy and log error.
- [x] All behavioral modes specified -- standard (policy loaded from file, auth enforced, audit logged), default (no policy file, `PolicyBundle.defaults()` used, matches pre-Phase 4 behavior), hot-reload (non-prod, file changes detected by mtime, atomic policy swap), degraded (policy file parse error -> retain last-good policy and log error; if no last-good -> use defaults).
- [x] Rollback procedure cites current CONSTITUTION.md version -- CONSTITUTION.md v0.4; rollback via `git revert` (new `policy/` dir deleted, modified files restored); no schema changes to revert; policy env vars default to absent (falls back to hardcoded behavior).
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at `governance/CONSTITUTION.md` (confirmed v0.4), providers.md at `governance/providers.md` (confirmed version 1.3), source proposal at `governance/proposals/context-gateway-mcp-full-alignment-plan.md` (Phase 4 section confirmed), prior cycle at `governance/plans/CG_MCP/artifacts/CG_MCP_v6_closure.md` (confirmed Phase 3 CLOSED), implementation repo at `C:\gh_src\rmembr` (confirmed `services/gateway/src/server.py`, `services/gateway/src/mcp_tools.py`, `services/gateway/src/mcp_errors.py`, `services/shared/src/auth.py`, `services/shared/src/structured_logging.py` exist and match described state).
- [x] Declared modification scope matches execution steps -- "Files to modify" table (5 rows: server.py, mcp_tools.py, mcp_errors.py, structured_logging.py, docker-compose.yml) aligns with "Order of operations" steps 6-9. "Files to create" table (13 rows) aligns with steps 1-5 and 10. No undeclared file modifications.

READY FOR AUDITOR REVIEW
