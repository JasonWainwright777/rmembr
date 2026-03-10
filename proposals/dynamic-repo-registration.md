# Proposal: Dynamic Repository Registration via MCP

## Problem Statement

Adding a new repository to rMEMbr currently requires:

1. Editing the `GITHUB_REPOS` environment variable in `.env`
2. Restarting the Docker stack (`docker compose up -d`)
3. Manually triggering an index

This is a friction point for adoption. When onboarding a new repo, the user should be able to register it through the MCP tools their AI assistant already has access to — no env var editing, no container restarts.

## Proposed Solution

Add a `repo_registry` database table and three new MCP tools (`register_repo`, `unregister_repo`, `list_repos`) so repos can be added and removed at runtime. The GitHub provider merges env-var repos (backward compatible) with database-registered repos at enumeration time.

---

## Architecture

### Current Flow

```
.env GITHUB_REPOS → docker-compose → GitHubProvider.__init__() → static repo list
```

The repo list is read once at container startup and never changes.

### Proposed Flow

```
MCP register_repo → gateway proxy → index service → repo_registry table
                                                          ↓
GitHubProvider.enumerate_repos() → merge(env_var_repos + db_repos) → index
```

The provider reads from both sources on every enumeration call, so newly registered repos are immediately discoverable.

### Key Design Decisions

- **Additive, not replacing** — `GITHUB_REPOS` env var continues to work for backward compatibility and bootstrapping
- **Database is the dynamic source** — `repo_registry` table stores runtime-added repos
- **Provider-scoped** — each registration is tied to a provider (e.g., `github`), so the system knows how to fetch content
- **Validation on register** — the system validates the repo exists and has a `.ai/memory/manifest.yaml` before accepting registration

---

## Database Schema

### Migration 5: `repo_registry` table

```sql
CREATE TABLE IF NOT EXISTS repo_registry (
    id          BIGSERIAL PRIMARY KEY,
    provider    TEXT NOT NULL,               -- 'github' or 'filesystem'
    namespace   TEXT NOT NULL DEFAULT 'default',
    repo_name   TEXT NOT NULL,               -- logical name (e.g., 'my-service')
    external_id TEXT NOT NULL,               -- provider-specific locator (e.g., 'owner/repo')
    enabled     BOOLEAN NOT NULL DEFAULT true,
    registered_by TEXT,                      -- who registered it (for audit)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, namespace, repo_name)
);
CREATE INDEX idx_repo_registry_provider ON repo_registry (provider, enabled);
```

### Why a separate table (not reusing `memory_packs`)?

- `memory_packs` is populated _after_ indexing succeeds — we need to know about a repo _before_ indexing
- Separation of concerns: registry = "what repos exist", memory_packs = "what's been indexed"
- Enables `enabled: false` soft-delete without losing index data

---

## Tasks

### Task 1: Add `repo_registry` database migration

**What:** Add Migration 5 to `services/index/src/migrations.py` creating the `repo_registry` table.

**Files:**
- `services/index/src/migrations.py` — add migration function and register it

**Acceptance Criteria:**
- [ ] Table is created on service startup (idempotent — `IF NOT EXISTS`)
- [ ] Unique constraint on `(provider, namespace, repo_name)` prevents duplicates
- [ ] Index on `(provider, enabled)` for efficient lookups
- [ ] Existing deployments auto-migrate without data loss

**Tests:**
- Unit test: migration runs without error on fresh DB
- Unit test: migration is idempotent (running twice doesn't fail)

---

### Task 2: Add `register_repo` endpoint to index service

**What:** Add `POST /tools/register_repo` endpoint that validates and stores a repo registration.

**Input Schema:**
```json
{
    "provider": "github",
    "repo": "owner/repo-name",
    "namespace": "default"
}
```

**Logic:**
1. Parse `repo` — for GitHub provider, expect `owner/repo` format
2. **Validate the repo exists** — call GitHub API to check `.ai/memory/manifest.yaml` exists at the default branch
3. If valid, upsert into `repo_registry` with `enabled = true`
4. Derive `repo_name` from the manifest's `scope.repo` field (or fall back to the repo slug)
5. Return success with the registered repo details

**Files:**
- `services/index/src/server.py` — add endpoint
- `services/index/src/providers/github.py` — add `validate_repo(owner_repo: str) -> dict` method

**Acceptance Criteria:**
- [ ] Returns 200 with repo details on successful registration
- [ ] Returns 400 if `provider` is not a known active provider
- [ ] Returns 404 if repo doesn't exist or has no `.ai/memory/manifest.yaml`
- [ ] Returns 409 if repo is already registered (with existing details)
- [ ] Duplicate registration with same details is idempotent (upsert)
- [ ] `owner/repo` format is validated (must contain exactly one `/`)
- [ ] Registration does NOT auto-index — that's a separate explicit step

**Tests:**
- Unit test: successful registration stores row in `repo_registry`
- Unit test: missing manifest returns 404
- Unit test: invalid provider returns 400
- Unit test: duplicate registration returns 409 with existing data
- Integration test: register + index_repo works end-to-end

---

### Task 3: Add `unregister_repo` endpoint to index service

**What:** Add `POST /tools/unregister_repo` endpoint that soft-disables a repo.

**Input Schema:**
```json
{
    "provider": "github",
    "repo": "repo-name",
    "namespace": "default",
    "purge": false
}
```

**Logic:**
1. Set `enabled = false` and update `updated_at` (soft delete)
2. If `purge: true`, also delete from `memory_packs` and `memory_chunks` (hard delete of indexed data)
3. Cannot unregister env-var repos — return error explaining this

**Files:**
- `services/index/src/server.py` — add endpoint

**Acceptance Criteria:**
- [ ] Soft-disable sets `enabled = false` without deleting index data
- [ ] `purge: true` deletes `memory_chunks` and `memory_packs` rows for the repo
- [ ] Returns 404 if repo is not in `repo_registry`
- [ ] Returns 403 if attempting to unregister an env-var-sourced repo (with explanation)
- [ ] Already-disabled repo returns 200 (idempotent)

**Tests:**
- Unit test: soft-disable sets enabled=false
- Unit test: purge removes chunks and pack data
- Unit test: env-var repo returns 403
- Unit test: unknown repo returns 404

---

### Task 4: Add `list_repos` endpoint to index service

**What:** Add `POST /tools/list_repos` endpoint returning all known repos and their status.

**Output Schema:**
```json
{
    "repos": [
        {
            "repo_name": "rmembr",
            "provider": "github",
            "external_id": "JasonWainwright777/rmembr",
            "namespace": "default",
            "source": "env_var",
            "enabled": true,
            "indexed": true,
            "last_indexed": "2026-03-10T21:00:00Z"
        },
        {
            "repo_name": "my-service",
            "provider": "github",
            "external_id": "JasonWainwright777/my-service",
            "namespace": "default",
            "source": "registered",
            "enabled": true,
            "indexed": false,
            "last_indexed": null
        }
    ]
}
```

**Logic:**
1. Query `repo_registry` for all rows (enabled and disabled)
2. Query env-var repos from active providers
3. Merge, deduplicate, and annotate each with:
   - `source`: `"env_var"` or `"registered"`
   - `indexed`: whether a `memory_packs` row exists
   - `last_indexed`: from `memory_packs.last_indexed_ref` timestamp

**Files:**
- `services/index/src/server.py` — add endpoint

**Acceptance Criteria:**
- [ ] Returns both env-var and database-registered repos
- [ ] Each entry shows `source` so users know where it came from
- [ ] `indexed` flag accurately reflects whether the repo has been indexed
- [ ] Disabled repos appear with `enabled: false`
- [ ] Empty system returns empty list (not an error)

**Tests:**
- Unit test: empty system returns empty list
- Unit test: env-var repos appear with `source: "env_var"`
- Unit test: registered repos appear with `source: "registered"`
- Unit test: indexed status correctly reflects memory_packs presence

---

### Task 5: Modify GitHubProvider to merge env-var and DB repos

**What:** Update `enumerate_repos()` to load repos from both the env var and the `repo_registry` table.

**Current code** (`providers/github.py` line 107):
```python
async def enumerate_repos(self):
    for owner_repo in self._repo_list():  # only reads env var
        ...
```

**Proposed change:**
```python
async def enumerate_repos(self):
    repo_sources = set()
    # 1. Env-var repos (backward compat)
    for owner_repo in self._repo_list():
        repo_sources.add(owner_repo)
    # 2. DB-registered repos
    async with self._pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT external_id FROM repo_registry WHERE provider = 'github' AND enabled = true"
        )
        for row in rows:
            repo_sources.add(row["external_id"])
    # 3. Enumerate merged set
    for owner_repo in sorted(repo_sources):
        ...
```

**Files:**
- `services/index/src/providers/github.py` — modify `enumerate_repos()`, accept `pool` in constructor

**Acceptance Criteria:**
- [ ] Env-var repos still work exactly as before (no behavioral change)
- [ ] DB-registered repos are enumerated alongside env-var repos
- [ ] Duplicate repos (in both env var and DB) are deduplicated
- [ ] Disabled repos (`enabled = false`) are excluded
- [ ] Provider works correctly with zero DB-registered repos (pure env-var mode)

**Tests:**
- Unit test: env-var-only mode works unchanged
- Unit test: DB-only repos are enumerated
- Unit test: mixed sources are merged and deduplicated
- Unit test: disabled repos are excluded

---

### Task 6: Add MCP tool definitions to gateway

**What:** Register `register_repo`, `unregister_repo`, and `list_repos` as MCP tools proxied to the index service.

**Files:**
- `services/gateway/src/mcp_tools.py` — add tool definitions and dispatch entries

**Tool Definitions:**

| Tool | Description | Parameters |
|------|-------------|------------|
| `register_repo` | Register a GitHub repository for indexing | `provider` (string), `repo` (string, e.g. `owner/repo`), `namespace` (string, optional) |
| `unregister_repo` | Remove a repository from the index | `provider` (string), `repo` (string), `namespace` (string, optional), `purge` (bool, optional) |
| `list_repos` | List all known repositories and their index status | _(no required params)_ |

**Acceptance Criteria:**
- [ ] All three tools appear in `list_tools` MCP response
- [ ] Tools proxy correctly to index service endpoints
- [ ] Parameter validation matches index service expectations
- [ ] Tool descriptions are clear enough for an AI assistant to use correctly

**Tests:**
- Integration test: MCP `list_tools` includes the three new tools
- Integration test: `register_repo` via MCP creates a DB entry
- Integration test: `list_repos` via MCP returns registered repos

---

### Task 7: Update setup documentation

**What:** Update `prompts/setup-rmembr-on-new-repo.md` to document the new MCP-based registration flow as the primary onboarding method.

**Changes:**
- Add "Step 3b: Register via MCP" as an alternative to editing env vars
- Update the MCP tools table to include `register_repo`, `unregister_repo`, `list_repos`
- Add example: *"Register my repo in rMEMbr: `owner/my-repo`"*

**Acceptance Criteria:**
- [ ] New flow is documented as the recommended approach
- [ ] Env-var approach is still documented as a fallback / bootstrap method
- [ ] MCP tools table includes the three new tools with descriptions

---

## Security Considerations

### 1. Repo validation before registration

The system must verify the repo exists and contains `.ai/memory/manifest.yaml` before accepting registration. This prevents:
- **Phantom repos** — registering non-existent repos that waste indexing cycles
- **Typosquatting** — accidentally pointing to the wrong `owner/repo`

**Mitigation:** `register_repo` calls the GitHub API to validate the repo and manifest before storing.

### 2. GitHub token scope

The existing `GITHUB_TOKEN` is used for all GitHub API calls. Dynamically registered repos must be accessible with the same token.

**Mitigation:** If the token can't read the repo (403/404 from GitHub), registration fails with a clear error. The system never stores a repo it can't access.

### 3. No arbitrary code execution

Repo memory packs contain markdown files that are chunked, embedded, and served as context. They are never executed. Registration of a malicious repo cannot lead to code execution — the content is treated as text.

**Mitigation:** Existing content pipeline (chunk → embed → store) is read-only and text-only. No `eval`, no template rendering, no shell execution on pack content.

### 4. Internal service authentication

All gateway-to-index communication uses `X-Internal-Token` headers. The new endpoints follow the same pattern — they are not directly exposed to external callers.

**Mitigation:** New endpoints use the same `_require_internal_token()` guard as existing internal endpoints.

### 5. Namespace isolation

Registered repos are scoped to a namespace. A repo registered in namespace `team-a` cannot be queried from namespace `team-b`.

**Mitigation:** All queries (search, bundle, list) already filter by namespace. Registration stores the namespace and respects the same boundaries.

### 6. Preventing mass registration / abuse

An AI assistant could theoretically register hundreds of repos in a loop.

**Mitigations:**
- **Rate limit:** Cap at 10 registrations per minute (429 after that)
- **Max repos:** Configurable `MAX_REGISTERED_REPOS` env var (default 50) — registration fails when the limit is reached
- **Audit trail:** `registered_by` column records who registered the repo (future: tie to MCP client identity)

### 7. Unregister protection for env-var repos

Env-var repos represent the baseline configuration set by the system administrator. They cannot be unregistered via MCP — only disabled repos from the `repo_registry` can be removed.

**Mitigation:** `unregister_repo` checks the source and returns 403 for env-var repos with a message explaining they must be removed from the environment configuration.

### 8. No secrets in registration

The `register_repo` tool accepts an `owner/repo` string, not tokens or credentials. Authentication to GitHub is handled by the pre-configured `GITHUB_TOKEN` in the environment.

**Mitigation:** The MCP tool schema does not accept any credential parameters. The AI assistant never sees or handles the GitHub token.

---

## Rollout Plan

1. **Phase 1** (Tasks 1-4): Database migration + index service endpoints. Can be deployed without breaking changes — no existing behavior is modified.
2. **Phase 2** (Task 5): Provider modification. Low risk — additive merge with env-var list. If `repo_registry` table is empty, behavior is identical to today.
3. **Phase 3** (Tasks 6-7): MCP tools + docs. Feature becomes user-facing.

Each phase is independently deployable and backward compatible.

---

## Out of Scope

- **Auto-discovery** (e.g., scan a GitHub org for all repos with `.ai/memory/`) — future enhancement
- **Per-repo GitHub tokens** — all repos use the same token today
- **Webhook-triggered indexing** — repos are indexed on demand, not on push
- **RBAC on registration** — who can register repos is not gated beyond MCP client access
