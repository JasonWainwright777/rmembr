# CG_MCP_v9 -- Phase 5: VS Code / Generic MCP Client Interoperability

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md
prior_cycle: CG_MCP_v7 (Phase 4 -- Policy, Security, and Tenancy Hardening, CLOSED)
prior_version: CG_MCP_v8 (FIX REQUIRED per AUDIT_CG_MCP_v8.md)
implementation_repo: C:\gh_src\rmembr

---

## Audit Resolution Map

| # | Required change (from AUDIT_CG_MCP_v8.md) | How addressed | Location in v8 |
|---|-------------------------------------------|---------------|-----------------|
| 1 | Normalize all MCP source path references to actual repo paths under `mcp-memory-local/services/gateway/src/` | Replaced all `gateway/src/` references with `mcp-memory-local/services/gateway/src/` throughout Sections A, B, C, D, and Spec Completeness Gate. Also normalized `scripts/mcp-cli.py` to `mcp-memory-local/scripts/mcp-cli.py` and bare `docker-compose.yml` to `mcp-memory-local/docker-compose.yml` in the "Current state" section. | Lines 27-33 (Current state), line 281 (Hidden dependencies), line 384 (Spec Completeness Gate) |
| 2 | Re-run and document a single path-integrity sweep for all referenced implementation files | Added "Path Integrity Sweep" subsection in Section A listing every referenced implementation file with its canonical path, confirming a single consistent path scheme across the plan. | New subsection after "Current state" |

---

## Scope

This cycle covers **Phase 5** from the source proposal: VS Code and generic MCP client interoperability. The source proposal defines five tasks:

1. Provide `docs/integration/vscode-mcp.md` with exact configuration and troubleshooting.
2. Provide reference configs for at least one additional MCP host/client.
3. Validate tool discovery, invocation, and response rendering in supported clients.
4. Add smoke test harness that simulates MCP client startup + tool call sequence.
5. Pin primary support target to VS Code 1.102+ with explicit compatibility statement for N and N-1.

### Current state (confirmed via codebase read)

**What already exists and should be preserved:**

- **MCP server** (`mcp-memory-local/services/gateway/src/mcp_server.py`): SSE transport via Starlette sub-app, gated by `MCP_ENABLED` env var. Mounts at `/mcp/sse` and `/mcp/messages/`. Request ID propagation from MCP client headers.
- **MCP tool registration** (`mcp-memory-local/services/gateway/src/mcp_tools.py`): 9 tools registered with JSON Schema `inputSchema`. Dispatch maps tools to gateway handlers or proxy calls. `McpToolError` wraps errors for MCP protocol.
- **MCP error sanitization** (`mcp-memory-local/services/gateway/src/mcp_errors.py`): Strips internal URLs, tokens, container paths, stack traces. Maps `ValidationError`, `LookupError`, `RuntimeError` to MCP error codes.
- **Existing MCP tests** (`tests/mcp/`): `test_mcp_tools.py` (unit), `test_mcp_parity.py` (HTTP vs MCP parity), `test_mcp_transport_gating.py` (stdio gating), `test_mcp_integration.py` (discovery + invocation via HTTP JSON-RPC), `test_mcp_soak.py` (15-min soak).
- **Docker-compose** (`mcp-memory-local/docker-compose.yml`): `MCP_ENABLED` and `MCP_STDIO_ENABLED` env vars on gateway service. Gateway exposed on port 8080.
- **Existing docs**: `docs/USAGE.md` (CLI usage), `docs/CONFIGURATION.md`, `docs/TUNING.md`, `docs/contracts/gateway-mcp-tools.md` (tool schemas).
- **CLI** (`mcp-memory-local/scripts/mcp-cli.py`): HTTP-based CLI calling gateway directly. Not an MCP client.

**What does NOT exist yet:**

- No VS Code MCP configuration docs or sample `.vscode/mcp.json`.
- No `docs/integration/` directory.
- No reference config for a second MCP client (e.g., Claude Code, Cursor, Continue).
- No automated smoke test that simulates the full MCP client lifecycle (initialize -> list tools -> call tool -> verify response).
- No explicit VS Code version compatibility statement.
- No UAT checklist document.

### Path Integrity Sweep

All implementation file paths referenced in this plan, verified against the rmembr repo layout:

| # | Canonical path (relative to rmembr repo root) | Section(s) referencing | Verified |
|---|-----------------------------------------------|----------------------|----------|
| 1 | `mcp-memory-local/services/gateway/src/mcp_server.py` | Current state, Hidden dependencies | Yes |
| 2 | `mcp-memory-local/services/gateway/src/mcp_tools.py` | Current state | Yes |
| 3 | `mcp-memory-local/services/gateway/src/mcp_errors.py` | Current state | Yes |
| 4 | `mcp-memory-local/docker-compose.yml` | Current state, Files to modify, Deployment steps | Yes |
| 5 | `mcp-memory-local/scripts/mcp-cli.py` | Current state | Yes |
| 6 | `tests/mcp/test_mcp_tools.py` | Current state, Validation steps | Yes |
| 7 | `tests/mcp/test_mcp_parity.py` | Current state, Validation steps | Yes |
| 8 | `tests/mcp/test_mcp_transport_gating.py` | Current state, Validation steps | Yes |
| 9 | `tests/mcp/test_mcp_integration.py` | Current state, Validation steps, Auditor Sensitivity | Yes |
| 10 | `tests/mcp/test_mcp_soak.py` | Current state | Yes |
| 11 | `docs/USAGE.md` | Current state, Files to modify, Rollback | Yes |
| 12 | `docs/CONFIGURATION.md` | Current state, Files to modify, Rollback | Yes |
| 13 | `docs/TUNING.md` | Current state | Yes |
| 14 | `docs/contracts/gateway-mcp-tools.md` | Current state | Yes |
| 15 | `tests/contracts/` | Validation steps | Yes |
| 16 | `tests/policy/` | Validation steps | Yes |

**Path convention:** Source code under `mcp-memory-local/services/`. Tests, docs, and configs at repo root level (`tests/`, `docs/`). Docker-compose and scripts under `mcp-memory-local/`. This convention is used consistently throughout this plan.

---

## SECTION A -- Execution Plan

### Micro-task list

| # | Task | Source proposal ref | Time est. | Risk | Validation artifact |
|---|------|---------------------|-----------|------|---------------------|
| 1 | Create VS Code MCP integration doc | Task 1 | 45 min | Low | Doc review: fresh setup from doc completes |
| 2 | Create sample `.vscode/mcp.json` config | Task 1 | 15 min | Low | VS Code loads config without error |
| 3 | Create reference config for Claude Code (second MCP client) | Task 2 | 30 min | Low | Doc review: second client setup completes |
| 4 | Create automated smoke test harness | Task 4 | 45 min | Medium | Smoke tests pass against running services |
| 5 | Create UAT checklist doc | Task 3 | 30 min | Low | Checklist exists and is executable |
| 6 | Add VS Code version compatibility statement to docs | Task 5 | 15 min | Low | Statement present in integration doc |
| 7 | Validate and fix any MCP server issues found during testing | Task 3 | 30 min | Medium | All smoke tests pass, both clients connect |

### Files to create (in rmembr repo)

| # | Path | Purpose |
|---|------|---------|
| 1 | `docs/integration/vscode-mcp.md` | VS Code MCP setup guide: prerequisites, configuration, troubleshooting, compatibility statement |
| 2 | `docs/integration/claude-code-mcp.md` | Claude Code MCP setup guide: `claude_desktop_config.json` or `.mcp.json` config, troubleshooting |
| 3 | `docs/integration/uat-checklist.md` | Manual UAT checklist for MCP client validation (VS Code + second client) |
| 4 | `.vscode/mcp.json` | Sample VS Code MCP server configuration pointing to local gateway |
| 5 | `tests/mcp/test_mcp_smoke.py` | Automated smoke test: initialize -> list tools -> call each tool -> verify response shape |
| 6 | `tests/mcp/conftest.py` | Shared MCP test fixtures (session helper, skip markers, tool call helper) |

### Files to modify (in rmembr repo)

| # | Path | Change |
|---|------|--------|
| 1 | `docs/USAGE.md` | Add "MCP Client Integration" section linking to `docs/integration/vscode-mcp.md` and `docs/integration/claude-code-mcp.md`. |
| 2 | `docs/CONFIGURATION.md` | Add `MCP_ENABLED` and `MCP_STDIO_ENABLED` documentation with behavior description. |
| 3 | `mcp-memory-local/docker-compose.yml` | No structural changes. Ensure `MCP_ENABLED` default comment documents that it must be `true` for MCP clients. |

### VS Code MCP configuration (`.vscode/mcp.json`)

```json
{
  "servers": {
    "rmembr": {
      "type": "sse",
      "url": "http://localhost:8080/mcp/sse",
      "headers": {}
    }
  }
}
```

**Behavioral notes:**
- VS Code 1.102+ reads `.vscode/mcp.json` and auto-discovers MCP servers.
- The `sse` type connects to the gateway's SSE endpoint.
- No auth headers required for local development (gateway does not enforce auth on MCP endpoints currently).
- `MCP_ENABLED=true` must be set in docker-compose or `.env` for the MCP server to be active.

### Claude Code MCP configuration

Claude Code reads MCP server configs from `.mcp.json` in the project root or `claude_desktop_config.json` in the user config directory.

```json
{
  "mcpServers": {
    "rmembr": {
      "url": "http://localhost:8080/mcp/sse",
      "transport": "sse"
    }
  }
}
```

### Smoke test harness (`test_mcp_smoke.py`)

```python
"""Automated smoke test: full MCP client lifecycle.

Simulates: initialize -> list tools -> call each tool -> verify response.
Skipped if gateway/MCP not available. Designed to run in CI or locally.
"""

class TestMcpSmoke:
    """Full lifecycle smoke test for MCP client interoperability."""

    def test_initialize_handshake(self):
        """MCP initialize returns valid protocol version and capabilities."""
        # POST /mcp with initialize method
        # Assert: protocolVersion present, serverInfo.name == "rmembr-context-gateway"
        ...

    def test_list_tools_returns_all_nine(self):
        """tools/list returns exactly 9 tools with valid schemas."""
        # Assert: 9 tools, each has name, description, inputSchema
        ...

    def test_call_each_read_tool(self):
        """Call each of the 7 read-only tools and verify structured response."""
        # For each tool: call with minimal valid params, assert no error or expected error
        ...

    def test_call_write_tool_denied(self):
        """index_repo/index_all denied for default (reader) role."""
        # Assert: structured MCP error response (not crash)
        ...

    def test_response_rendering_text_content(self):
        """Tool responses are TextContent with valid JSON."""
        # Assert: result content is list of TextContent, text field is parseable JSON
        ...

    def test_error_responses_sanitized(self):
        """Error responses contain no internal URLs/tokens/paths."""
        # Trigger validation error, assert sanitized
        ...

    def test_session_lifecycle(self):
        """Full session: initialize -> list -> call -> (repeated) without crash."""
        # 10 sequential tool calls in same session
        ...
```

### Shared test fixtures (`conftest.py`)

```python
"""Shared fixtures for MCP tests."""

class McpTestClient:
    """Helper for MCP JSON-RPC interactions."""

    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url
        self.session_id = None
        self._next_id = 1

    def initialize(self) -> dict:
        """Send initialize request, store session_id."""
        ...

    def list_tools(self) -> list[dict]:
        """Send tools/list, return tool definitions."""
        ...

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Send tools/call, return result or error."""
        ...
```

### UAT checklist structure (`uat-checklist.md`)

```markdown
# MCP Client UAT Checklist

## Prerequisites
- [ ] Docker compose services running (`docker compose up -d`)
- [ ] Ollama model pulled
- [ ] At least one repo indexed
- [ ] MCP_ENABLED=true in .env or docker-compose

## VS Code (primary target: 1.102+)
- [ ] `.vscode/mcp.json` present in workspace
- [ ] VS Code discovers rmembr MCP server in MCP panel
- [ ] Tool list shows 9 tools
- [ ] search_repo_memory returns results
- [ ] get_context_bundle returns bundle with markdown
- [ ] explain_context_bundle works with returned bundle_id
- [ ] validate_pack returns valid/invalid status
- [ ] list_standards returns standards list
- [ ] get_standard returns standard content
- [ ] Error on invalid input shows clean error (no internal URLs)

## Claude Code (secondary client)
- [ ] .mcp.json present in project root
- [ ] Claude Code discovers rmembr MCP server
- [ ] Tool list shows 9 tools
- [ ] search_repo_memory returns results
- [ ] get_context_bundle returns bundle

## Automated smoke
- [ ] python -m pytest tests/mcp/test_mcp_smoke.py -v passes
```

### Minimal safe change strategy

1. **Documentation-first, code-light.** This phase is primarily documentation and test infrastructure. The MCP server already works (Phase 1). Phase 5 is about proving interoperability and providing setup guides.

2. **No MCP server changes expected.** The smoke tests may reveal issues requiring fixes (task 7 budget), but the plan assumes the existing MCP server is functional. Any fixes will be minimal and scoped to what smoke tests reveal.

3. **Sample configs are additive.** `.vscode/mcp.json` and Claude Code config are new files. They do not modify any existing config.

4. **Smoke test reuses existing test patterns.** `test_mcp_smoke.py` follows the same structure as `test_mcp_integration.py` but is a comprehensive lifecycle test. Shared fixtures in `conftest.py` reduce duplication with existing MCP tests.

5. **No schema migrations, no new dependencies.** Documentation and test files only. Tests use `httpx` (already a test dependency).

### Order of operations

1. **Create `docs/integration/` directory and VS Code doc** -- `docs/integration/vscode-mcp.md` with prerequisites, step-by-step setup, configuration reference, troubleshooting, and VS Code version compatibility statement (1.102+ primary, N and N-1 best-effort).

2. **Create sample `.vscode/mcp.json`** -- Minimal config pointing to local gateway SSE endpoint.

3. **Create Claude Code integration doc** -- `docs/integration/claude-code-mcp.md` with `.mcp.json` config and setup steps.

4. **Create shared MCP test fixtures** -- `tests/mcp/conftest.py` with `McpTestClient` helper class and skip markers (refactored from existing `test_mcp_integration.py` inline helpers).

5. **Create smoke test harness** -- `tests/mcp/test_mcp_smoke.py` with full lifecycle tests: initialize, list tools, call each tool, verify response shapes, error sanitization, session stability.

6. **Create UAT checklist** -- `docs/integration/uat-checklist.md` with manual validation steps for VS Code and Claude Code.

7. **Update existing docs** -- Add MCP client integration section to `docs/USAGE.md`. Add MCP env var documentation to `docs/CONFIGURATION.md`.

8. **Validate** -- Run full test suite including existing contract tests, MCP tests, and new smoke tests. Execute UAT checklist manually against running services.

### Deployment steps

1. Merge documentation and test files (no behavioral change to running services).
2. Set `MCP_ENABLED=true` in `.env` or `mcp-memory-local/docker-compose.yml` and restart services.
3. Run new smoke tests: `python -m pytest tests/mcp/test_mcp_smoke.py -v`.
4. Open project in VS Code 1.102+, verify MCP server discovery and tool invocation.
5. Configure Claude Code with `.mcp.json`, verify tool discovery and invocation.
6. Execute UAT checklist and record results.

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| VS Code MCP client rejects SSE transport or config format | Medium | High | `.vscode/mcp.json` format verified against VS Code 1.102+ MCP documentation. SSE transport is the standard MCP transport for remote servers. Troubleshooting section covers common failures. |
| Smoke tests reveal MCP server bugs not caught by existing tests | Medium | Medium | Task 7 reserves 30 min for fixing issues. Fixes are scoped to what smoke tests reveal. Any fix that exceeds minor scope is deferred to next cycle. |
| Claude Code MCP config format differs from documented | Low | Low | Claude Code config is well-documented. Config is simple (URL + transport type). Troubleshooting section included. |
| Shared conftest.py refactor breaks existing MCP tests | Low | Medium | Existing tests continue to use their own inline helpers initially. `conftest.py` adds new fixtures; existing tests are migrated only if they import from conftest. No forced migration. |
| MCP_ENABLED=false by default causes confusion | Low | Low | Docs explicitly state `MCP_ENABLED=true` is required. Setup guide includes this step prominently. |
| VS Code version N-2 or older does not support MCP | Low | Low | Compatibility statement pins 1.102+ as primary target. N-1 is best-effort. Older versions are explicitly unsupported. |

### Hidden dependencies

- **MCP_ENABLED env var.** Gateway MCP server is disabled by default. All MCP client configs and smoke tests require `MCP_ENABLED=true`. Docs and tests must make this prerequisite explicit.
- **SSE endpoint path.** VS Code and Claude Code configs reference `/mcp/sse`. This path is set in `mcp-memory-local/services/gateway/src/mcp_server.py:46`. Any change to the path would break client configs.
- **Port 8080.** Gateway is exposed on port 8080 in `mcp-memory-local/docker-compose.yml`. Client configs hardcode `localhost:8080`. If port changes, configs need updating.
- **Existing MCP test markers.** `test_mcp_integration.py` uses `skip_no_mcp` marker that checks MCP endpoint availability. New smoke tests should use the same skip logic (via shared conftest).
- **Phase 4 auth.** If Phase 4 per-tool authorization is active, smoke tests must account for `reader` role defaults. Default role should allow all read tools. Write tool tests should expect denial.

### Rollback strategy

Per CONSTITUTION.md v0.4:

1. **Config rollback:** Delete `.vscode/mcp.json`. No runtime impact -- it's a sample config file.
2. **Doc rollback:** Delete `docs/integration/` directory. No runtime impact.
3. **Test rollback:** Delete `tests/mcp/test_mcp_smoke.py` and `tests/mcp/conftest.py`. Existing MCP tests are unchanged.
4. **Code rollback:** Revert minor edits to `docs/USAGE.md` and `docs/CONFIGURATION.md`. No schema changes, no service code changes.
5. **Rollback time:** ~2 min for `git revert`. No service restart needed.

---

## SECTION C -- Validation Steps

### Acceptance criteria (from source proposal Phase 5)

1. Fresh environment setup completes from docs without tribal knowledge.
2. VS Code 1.102+ MCP client can list and invoke gateway tools successfully.
3. At least one non-VS Code MCP client also passes smoke flow.

### Closure artifacts required

1. **Regression pass:** Existing `tests/contracts/`, `tests/mcp/`, and `tests/policy/` tests pass.
2. **Smoke test pass:** `test_mcp_smoke.py` passes all tests:
   - `test_initialize_handshake`: MCP initialize returns `protocolVersion` and `serverInfo.name == "rmembr-context-gateway"`.
   - `test_list_tools_returns_all_nine`: `tools/list` returns exactly 9 tools, each with `name`, `description`, `inputSchema`.
   - `test_call_each_read_tool`: All 7 read-only tools callable with minimal valid params, return structured response or expected validation error (e.g., repo not found).
   - `test_call_write_tool_denied`: `index_repo` and `index_all` return structured MCP error for default role (if Phase 4 authz active) or succeed (if authz not yet deployed).
   - `test_response_rendering_text_content`: Tool responses are `TextContent` with parseable JSON `text` field.
   - `test_error_responses_sanitized`: Validation error responses contain no internal URLs, tokens, or container paths.
   - `test_session_lifecycle`: 10 sequential tool calls in same session complete without crash or session corruption.
3. **VS Code validation:** UAT checklist "VS Code" section completed. VS Code 1.102+ discovers server, lists 9 tools, successfully invokes `search_repo_memory` and `get_context_bundle`.
4. **Second client validation:** UAT checklist "Claude Code" section completed. Claude Code discovers server and invokes at least one tool successfully.
5. **Fresh setup validation:** A developer (or simulated fresh setup) follows `docs/integration/vscode-mcp.md` from scratch and successfully invokes a tool without additional guidance. Acceptance: zero undocumented steps required.
6. **Compatibility statement present:** `docs/integration/vscode-mcp.md` contains explicit statement: "Primary target: VS Code 1.102+. Best-effort support: current stable N and N-1."
7. **Existing HTTP workflows unaffected:** `tests/mcp/test_mcp_integration.py::TestHttpEndpointsStillWork` passes (health, validation errors, explain-bundle).

### Exact commands to produce closure artifacts

```bash
# All commands run from rmembr/ with services up (MCP_ENABLED=true)

# 1. Regression -- existing tests
python -m pytest tests/contracts/ -v
python -m pytest tests/mcp/test_mcp_tools.py tests/mcp/test_mcp_parity.py tests/mcp/test_mcp_transport_gating.py -v
python -m pytest tests/mcp/test_mcp_integration.py -v

# 2. Smoke tests
python -m pytest tests/mcp/test_mcp_smoke.py -v

# 3. VS Code validation (manual)
# Open project in VS Code 1.102+
# Verify MCP panel shows rmembr server
# Invoke search_repo_memory and get_context_bundle from MCP panel
# Record results in UAT checklist

# 4. Claude Code validation (manual)
# Configure .mcp.json in project root
# Verify Claude Code discovers rmembr server
# Invoke at least one tool
# Record results in UAT checklist

# 5. Fresh setup validation (manual)
# Follow docs/integration/vscode-mcp.md from scratch
# Record any undocumented steps needed

# 6. Compatibility statement
grep -q "1.102" docs/integration/vscode-mcp.md && echo "PASS" || echo "FAIL"

# 7. HTTP regression
python -m pytest tests/mcp/test_mcp_integration.py::TestHttpEndpointsStillWork -v
```

---

## SECTION D -- Auditor Sensitivity

1. **Documentation completeness.** Auditor will verify that `docs/integration/vscode-mcp.md` contains sufficient detail for a fresh setup without tribal knowledge. Mitigation: doc includes prerequisites, step-by-step setup, configuration reference, troubleshooting FAQ, and explicit compatibility statement. Fresh setup validation (closure #5) proves completeness.

2. **Smoke test coverage.** Auditor will verify that the smoke test harness covers the full MCP lifecycle (init -> discover -> invoke -> error handling -> session stability). Mitigation: 7 distinct test cases covering handshake, tool listing, read tools, write tool denial, response format, error sanitization, and session stability.

3. **Second client validation.** Auditor will verify that the non-VS Code client (Claude Code) genuinely validates interoperability and is not just a trivial pass-through. Mitigation: Claude Code uses a different config format (`.mcp.json` vs `.vscode/mcp.json`) and different MCP client implementation. UAT checklist requires tool discovery and invocation, not just connection.

4. **No MCP server code changes without test.** Auditor will check that any MCP server fixes discovered during task 7 are covered by the new smoke tests or existing tests. Mitigation: task 7 is explicitly scoped to "fix what smoke tests reveal." Any fix must have a corresponding test assertion.

5. **Sample config security.** Auditor will verify that `.vscode/mcp.json` and Claude Code config do not contain secrets or hardcoded tokens. Mitigation: configs use `localhost` URL only. No auth headers or tokens. Comment in docs warns about production config differences.

6. **Compatibility statement specificity.** Auditor will verify that the VS Code version pin is specific and actionable (not vague). Mitigation: "Primary target: VS Code 1.102+" with explicit N and N-1 best-effort statement, matching the locked decision in the source proposal.

7. **conftest.py does not break existing tests.** Auditor will verify that the shared `conftest.py` does not introduce side effects that break existing `tests/mcp/` tests. Mitigation: `conftest.py` only adds new fixtures. Existing tests are not modified to depend on it unless they already use compatible patterns. Existing tests run as regression artifact #1.

8. **Path consistency.** Auditor will verify that all implementation file paths use a single canonical scheme. Mitigation: Path Integrity Sweep table documents every referenced file with its canonical path relative to the rmembr repo root. Convention: service source under `mcp-memory-local/services/`, tests and docs at repo root level.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined -- Smoke test assertions: `initialize` response must contain `result.protocolVersion` (str, required) and `result.serverInfo.name` (str, required, value "rmembr-context-gateway"). `tools/list` response must contain `result.tools` (array, required, length 9). Each tool: `name` (str, required), `description` (str, required), `inputSchema` (object, required). `tools/call` response: `result.content` (array of `{type: "text", text: str}`, required) on success; `error.code` (int, required) and `error.message` (str, required) on failure. `.vscode/mcp.json`: `servers` (object, required), each entry: `type` (str, required, "sse"), `url` (str, required). Claude Code `.mcp.json`: `mcpServers` (object, required), each entry: `url` (str, required), `transport` (str, required, "sse").
- [x] All boundary conditions named -- VS Code version: 1.102+ primary, N and N-1 best-effort, older unsupported. `MCP_ENABLED` must be `true` for any MCP functionality (default `false`). Smoke test skip: tests skipped when gateway unreachable or MCP not enabled. Session lifecycle: 10 sequential calls minimum without crash. "Minor fix" boundary for task 7: fix is minor if it changes fewer than 20 lines in existing MCP server files; larger fixes deferred to next cycle. Fresh setup: zero undocumented steps = pass; any undocumented step = fail (doc must be updated).
- [x] All behavioral modes specified -- standard (MCP_ENABLED=true, gateway serves MCP endpoints, clients connect via SSE), disabled (MCP_ENABLED=false, gateway serves HTTP only, MCP endpoints return 404, smoke tests skip), CI (smoke tests run against live services in CI, skip if services unavailable via pytest markers).
- [x] Rollback procedure cites current CONSTITUTION.md version -- CONSTITUTION.md v0.4; rollback via `git revert` (delete `docs/integration/`, `.vscode/mcp.json`, `tests/mcp/test_mcp_smoke.py`, `tests/mcp/conftest.py`; revert `docs/USAGE.md` and `docs/CONFIGURATION.md` edits); no schema changes; no service code changes expected (task 7 fixes are minor); rollback time ~2 min.
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at `governance/CONSTITUTION.md` (confirmed v0.4), providers.md at `governance/providers.md` (confirmed version 1.3), source proposal at `governance/proposals/context-gateway-mcp-full-alignment-plan.md` (Phase 5 section confirmed), prior cycle closure at `governance/plans/CG_MCP/artifacts/CG_MCP_v7_closure.md` (confirmed Phase 4 CLOSED), implementation repo at `C:\gh_src\rmembr` (confirmed `mcp-memory-local/services/gateway/src/mcp_server.py`, `mcp-memory-local/services/gateway/src/mcp_tools.py`, `tests/mcp/test_mcp_integration.py` exist and match described state, `docs/USAGE.md` and `docs/CONFIGURATION.md` exist).
- [x] Declared modification scope matches execution steps -- "Files to modify" table (3 rows: USAGE.md, CONFIGURATION.md, docker-compose.yml) aligns with "Order of operations" step 7. "Files to create" table (6 rows) aligns with steps 1-6. No undeclared file modifications (task 7 MCP server fixes, if any, are bounded by "minor fix" definition and will be declared in closure artifact).
- [x] Path integrity verified -- All 16 implementation file paths listed in the Path Integrity Sweep table use a single canonical scheme: service source under `mcp-memory-local/services/`, infrastructure under `mcp-memory-local/`, tests and docs at repo root. No mixed path conventions remain.

READY FOR AUDITOR REVIEW
