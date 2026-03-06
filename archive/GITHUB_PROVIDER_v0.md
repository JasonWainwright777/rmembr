# GITHUB_PROVIDER_v0 — Execution Plan

governance_constitution_version: AI Company Constitution v0.4
governance_providers_version: 1.3

Cycle: GITHUB_PROVIDER
Mode: FULL
Date: 2026-03-06
Builder: Claude Sonnet 4.6

---

## SECTION A — Execution Plan

### Scope

Add a `GitHubProvider` to the rMEMbr Index service that reads `.ai/memory/` packs directly
from GitHub repositories via the GitHub REST API (authenticated PAT). The filesystem provider
is unchanged and remains the default. The GitHub provider activates only when `GITHUB_TOKEN`
is present in the environment.

Target repo: `C:\gh_src\rmembr`

### Files Changed

| File (relative to rMEMbr repo root) | Action |
|--------------------------------------|--------|
| `mcp-memory-local/services/index/src/providers/github.py` | New |
| `mcp-memory-local/services/index/src/providers/__init__.py` | Edit — export GitHubProvider |
| `mcp-memory-local/services/index/src/server.py` | Edit — conditionally register GitHubProvider |
| `mcp-memory-local/services/index/src/migrations.py` | Edit — add github_cache migration |
| `mcp-memory-local/docker-compose.yml` | Edit — add GitHub env vars to index service |
| `mcp-memory-local/.env.example` | Edit — add GitHub section (commented out) |
| `mcp-memory-local/scripts/mcp-cli.py` | Edit — add --provider flag to index-repo |
| `mcp-memory-local/tests/test_github_provider.py` | New — 14 unit tests (mocked HTTP) |
| `mcp-memory-local/tests/test_github_provider_integration.py` | New — integration tests |
| `mcp-memory-local/docs/CONFIGURATION.md` | Edit — add GitHub provider env var table |
| `.ai/memory/system-architecture.md` | Edit — update Provider Framework section |
| `.ai/memory/configuration.md` | Edit — add GitHub env vars |

### Order of Operations

All phases are in the rMEMbr repo. No CodeFactory files are modified during execution.

**Phase 1 — GitHubProvider core class**
1.1 Create `github.py` with `GitHubProvider` class skeleton:
    - `__init__`: reads GITHUB_TOKEN (required), GITHUB_REPOS, GITHUB_API_URL, GITHUB_DEFAULT_BRANCH
    - Raises ValueError at init if GITHUB_TOKEN is empty string (not if env var is absent —
      absent means the provider will simply not be registered; empty string is a misconfiguration)
    - Creates one `httpx.AsyncClient` instance at init (not per-request)
    - `pool` parameter accepted at init (optional, default None); used by cache phase

1.2 Implement `enumerate_repos`:
    - For each repo in GITHUB_REPOS: GET /repos/{owner}/{repo}/contents/.ai/memory/manifest.yaml
    - 404 -> log warning, skip
    - 200 -> parse manifest (reuse shared parse_manifest), yield RepoDescriptor
      - `repo` field = repo name only (not owner/repo)
      - `external_id` = full owner/repo string
      - `provider_name` = "github"
    - Non-200/non-404 -> raise exception with status code + repo name
    - Auth header: Authorization: Bearer <GITHUB_TOKEN>

1.3 Implement `enumerate_documents`:
    - GET /repos/{owner}/{repo}/git/trees/{branch}:.ai?recursive=1
    - Filter tree entries: paths matching memory/**/*.md and memory/**/*.yaml, excluding manifest.yaml
    - Yield DocumentDescriptor per file:
      - `path` = .ai/{tree_relative_path} (forward slashes, repo-root-relative)
      - `anchor` = None
      - `external_id` = blob SHA from tree response

1.4 Implement `fetch_content`:
    - GET /repos/{owner}/{repo}/git/blobs/{sha} using doc.external_id
    - Decode base64 -> UTF-8 text
    - Compute SHA-256 content hash (same method as FilesystemProvider)
    - Return DocumentContent with text, content_hash, and doc
    - Non-200 -> raise exception with status code, repo, path

**Phase 2 — Wiring and configuration**
2.1 Register GitHubProvider in `server.py` lifespan:
    - After FilesystemProvider registration
    - Only if os.environ.get("GITHUB_TOKEN") is truthy
    - Pass pool: `registry.register(GitHubProvider(pool=pool))`
    - No warning if GITHUB_TOKEN absent (silent skip)

2.2 Add env vars to docker-compose.yml and .env.example:
    - docker-compose.yml index service environment block:
        GITHUB_TOKEN: ${GITHUB_TOKEN:-}
        GITHUB_REPOS: ${GITHUB_REPOS:-}
        GITHUB_API_URL: ${GITHUB_API_URL:-https://api.github.com}
        GITHUB_DEFAULT_BRANCH: ${GITHUB_DEFAULT_BRANCH:-main}
    - Verify ACTIVE_PROVIDERS passthrough already present; add if missing
    - .env.example: add commented GitHub section with PAT instructions

2.3 Add --provider flag to mcp-cli.py index-repo subcommand:
    - Default: "filesystem"
    - Passes "provider": args.provider in request body
    - index-all is unchanged

**Phase 3 — Error handling and rate limit awareness**
3.1 Add rate limit header logging after every GitHub API response:
    - Check X-RateLimit-Remaining, X-RateLimit-Limit, X-RateLimit-Reset
    - log.warning when remaining < 100 (include reset timestamp)
    - Missing headers: no error (defensive)

3.2 Handle HTTP error codes explicitly:
    - 401 -> raise "GitHub authentication failed -- check GITHUB_TOKEN"
    - 403 + X-RateLimit-Remaining == 0 -> raise "GitHub API rate limit exceeded -- resets at {reset_time}"
    - 403 without rate limit -> raise "GitHub access denied for {repo} -- check PAT permissions"
    - 401 during enumerate_repos fails entire enumeration (bad token, not per-repo)
    - All error messages include repo name and/or file path

**Phase 4 — Indexing cache (minimize API calls)**
4.1 Add migration 3 to `migrations.py` MIGRATIONS list:
    ```sql
    CREATE TABLE IF NOT EXISTS github_cache (
        id          BIGSERIAL PRIMARY KEY,
        cache_type  TEXT NOT NULL,
        cache_key   TEXT NOT NULL,
        etag        TEXT,
        content     TEXT,
        tree_sha    TEXT,
        blob_shas   JSONB,
        created_at  TIMESTAMPTZ DEFAULT now(),
        updated_at  TIMESTAMPTZ DEFAULT now(),
        CONSTRAINT idx_github_cache_key UNIQUE (cache_type, cache_key)
    );
    ```
    Two row types:
    - tree_etag: cache_key = "owner/repo:branch", stores ETag and blob_shas {path: sha} map
    - blob: cache_key = blob SHA, stores decoded UTF-8 content

4.4 Pass database pool to GitHubProvider (already in 2.1 above; 4.4 confirms pool is live before 4.2/4.3)

4.2 Tree cache in `enumerate_documents`:
    - Build cache key: {owner/repo}:{branch}
    - Look up tree_etag row in github_cache
    - If found: send request with If-None-Match: <cached_etag> header
      - 304 -> yield DocumentDescriptors from cached blob_shas, zero API rate cost
      - 200 -> upsert cache row (new ETag, tree_sha, blob_shas map), yield from new tree
    - If no cache row: normal 200 flow, insert cache row
    - If pool is None: skip cache entirely (all requests go to GitHub API)
    - Cache read/write failures: log warning, do not fail indexing

4.3 Blob cache in `fetch_content`:
    - Lookup: github_cache where cache_type='blob' AND cache_key=doc.external_id
    - Cache hit: return DocumentContent from cached content, zero API calls
    - Cache miss: fetch blob, upsert cache row (content is decoded UTF-8 text, not base64)
    - Blob cache is permanent (git SHA = content hash, never stale)
    - If pool is None: skip cache, always fetch

**Phase 5 — Tests**
5.1 Unit tests (mocked HTTP, no real API calls, no GITHUB_TOKEN required):
    14 test cases covering all behavioral paths — see AD_HOC_GITHUB_PROVIDER.md Task 5.1

5.2 Integration tests:
    - Skipped (not failed) if GITHUB_TOKEN not set (pytest.mark.skipif)
    - Tests 1-5 per AD_HOC_GITHUB_PROVIDER.md Task 5.2
    - Verifies provider_name == "github" in memory_chunks

5.3 End-to-end manual CLI test (to be performed by Founder/Board after code complete):
    Steps per AD_HOC_GITHUB_PROVIDER.md Task 5.3

**Phase 6 — Documentation**
6.2 docs/CONFIGURATION.md: add GitHub provider rows to env var table
6.3 .ai/memory/system-architecture.md and .ai/memory/configuration.md: update for GitHubProvider
6.4 Sync repos/rmembr/.ai/memory/ and reindex

### Deployment Steps

1. Implement phases 1-4 in rMEMbr repo (no Docker restart needed during dev)
2. Implement phase 5 tests; run unit tests: `pytest tests/test_github_provider.py -v`
3. If GITHUB_TOKEN available: run integration tests: `pytest tests/test_github_provider_integration.py -v`
4. Rebuild Docker image: `docker compose up -d --build`
5. Run manual CLI test (phase 5.3)
6. Complete docs (phase 6)
7. Commit all changes to rMEMbr repo
8. Produce closure artifact in CodeFactory governance cycle

---

## SECTION B — Risk Surface

### What Could Break

| Risk | Severity | Notes |
|------|----------|-------|
| GITHUB_TOKEN exposed in committed file | HIGH | Mitigated: token read from host env var only; .env.example comments explicitly warn against storing it |
| PAT with excessive permissions | MEDIUM | Plan requires fine-grained PAT with Contents: Read-only + Metadata: Read-only only |
| Migration 3 conflicts with existing schema | LOW | Uses IF NOT EXISTS and a new table; no changes to memory_packs, memory_chunks, bundle_cache |
| GitHub API rate limit exhaustion | LOW | Two-layer cache keeps steady-state cost at 0-2 calls per index run |
| Non-UTF-8 blob content | LOW | fetch_content raises clear error; no silent corruption |
| Existing FilesystemProvider broken | LOW | No changes to filesystem.py or its registration; GitHubProvider is additive |
| httpx not in requirements.txt | LOW | Proposal notes it is already present; verify before implementation |
| ACTIVE_PROVIDERS=github with GITHUB_TOKEN absent | LOW | Registry logs unknown provider (existing behavior); no crash |
| docker-compose.yml edit breaks existing services | LOW | Only adding env vars to index service with safe defaults (${VAR:-}) |

### Hidden Dependencies

- `httpx.AsyncClient` must be available in the index service container (verify requirements.txt)
- `asyncpg` pool used for cache reads/writes — provider receives pool reference from server.py lifespan
- `parse_manifest` shared function referenced in enumerate_repos — must confirm its import path in the existing codebase before implementation
- `ACTIVE_PROVIDERS` env var passthrough in docker-compose.yml — must verify it already exists before adding GitHub vars

### Rollback Strategy

Per CONSTITUTION.md v0.4 (Non-Negotiable Constraints: no destructive operations without rollback plan):

**Rollback is low-risk because:**
- GitHubProvider registration is conditional on GITHUB_TOKEN env var
- Migration 3 is purely additive (new table, IF NOT EXISTS)
- All existing providers and tables are untouched

**Full rollback procedure:**
1. Remove GITHUB_TOKEN from host environment (or unset in container)
   -> GitHubProvider silently not registered; system reverts to filesystem-only behavior
2. To also remove the github_cache table: `DROP TABLE IF EXISTS github_cache;`
   -> This is the only destructive DB step; it contains only cache data (no primary data)
3. Revert code changes in rMEMbr repo (git revert or reset)
4. Rebuild Docker image: `docker compose up -d --build`

Total rollback time: < 5 minutes (env var unset + container restart).

---

## SECTION C — Validation Steps

### Required Closure Artifacts

The Builder must produce the following before closure is proposed to the Board:

**C1 — Unit test pass log**
```
pytest mcp-memory-local/tests/test_github_provider.py -v
```
All 14 test cases pass. No real HTTP calls made.

**C2 — Integration test pass log (if GITHUB_TOKEN available)**
```
pytest mcp-memory-local/tests/test_github_provider_integration.py -v
```
At minimum tests 1-4 pass. Test 5 (full indexing) confirms provider_name == "github" in memory_chunks.

**C3 — docker compose build success**
```
docker compose up -d --build
```
Exit code 0, no errors in build log.

**C4 — Manual CLI test log**
Steps 3-6 of Phase 5.3 executed with real GITHUB_TOKEN set. Output shows non-zero chunks_new or skipped_unchanged. Search returns results. Step 6 confirms filesystem provider still works.

**C5 — No secrets committed**
```
git log --diff-filter=A -p -- .env* "**/.env*"
```
No PAT values or GITHUB_TOKEN values in any committed file.

---

## SECTION D — Auditor Sensitivity

The following areas are most likely to trigger FIX REQUIRED during independent audit:

1. **Secret handling** — Auditor will check whether GITHUB_TOKEN could be inadvertently
   logged (e.g., in exception messages that echo env vars) or committed. The plan must show
   explicit mitigation: token is never printed, never in .env, never in error message text.

2. **Migration safety** — Auditor will verify migration 3 is non-destructive. Plan specifies
   IF NOT EXISTS and additive-only schema. Any ALTER to existing tables would be flagged.

3. **Pool=None degradation** — Auditor will check whether caching failure (pool=None or
   DB error) causes silent data corruption. Plan specifies: cache failures log warnings and
   fall back to live API calls; they never cause incorrect results.

4. **Rate limit failure mode** — Auditor may ask: what happens if rate limit is hit mid-index?
   Plan specifies: 403 + X-RateLimit-Remaining == 0 raises exception with actionable message.
   The index operation fails cleanly; no partial/corrupt state is written.

5. **Test coverage gap** — Auditor may note that 403 without rate limit (PAT permissions issue)
   is tested in unit tests but not integration tests. This is acceptable as integration tests
   use a valid token by definition; document this in the test file.

6. **CONSTITUTION.md compliance on governance** — Auditor will check that this plan does not
   modify providers.md. This cycle adds no new governed provider to providers.md (GitHubProvider
   is an implementation detail of the rMEMbr Index service, not a governance AI provider).
   The Auditor Sensitivity section must be explicit on this boundary.

---

## Spec Completeness Gate (Builder self-check)

[x] All output schemas defined
    - RepoDescriptor: namespace (str), repo (str, name-only), provider_name ("github"),
      external_id (owner/repo), version_ref (None), metadata (from manifest)
    - DocumentDescriptor: repo (RepoDescriptor), path (.ai/{tree_path}), anchor (None),
      external_id (blob SHA), version_ref (None), content_hash (None at enumerate time)
    - DocumentContent: doc (DocumentDescriptor), text (decoded UTF-8), content_hash (SHA-256)
    - github_cache row: id, cache_type ('tree_etag'|'blob'), cache_key, etag, content,
      tree_sha, blob_shas (JSONB {path: sha}), created_at, updated_at

[x] All boundary conditions named
    - GITHUB_TOKEN absent -> GitHubProvider not registered (silent)
    - GITHUB_TOKEN empty string -> ValueError at __init__ (misconfiguration)
    - GITHUB_REPOS absent/empty -> enumerate_repos yields nothing (not an error)
    - repo without .ai/memory/manifest.yaml -> skip with log warning
    - .ai subtree doesn't exist -> enumerate_documents yields nothing
    - 304 response -> zero rate limit cost; yield from cached blob_shas
    - rate limit warning threshold: X-RateLimit-Remaining < 100
    - pool=None -> caching disabled, all operations still succeed via live API

[x] All behavioral modes specified
    - Standard mode: GITHUB_TOKEN set, pool available -> full caching active
    - Degraded/fallback: pool=None -> no caching, live API calls on every index-repo
    - CI mode: GITHUB_TOKEN not set -> GitHubProvider not registered; unit tests run
      without GITHUB_TOKEN; integration tests skipped (not failed)

[x] Rollback procedure cites current CONSTITUTION.md version
    - Rollback documented in Section B under "Full rollback procedure"
    - References CONSTITUTION.md v0.4 Non-Negotiable Constraints

[x] Governance citations validated against current file paths (not assumed from memory)
    - CONSTITUTION.md: confirmed at governance/CONSTITUTION.md, version v0.4
    - providers.md: confirmed at governance/providers.md, version 1.3
    - AD_HOC_GITHUB_PROVIDER.md: confirmed at governance/proposals/AD_HOC_GITHUB_PROVIDER.md
    - Implementation reference: confirmed at C:\gh_src\rmembr\plans\github-provider-implementation.md
    - providers/__init__.py: confirmed at mcp-memory-local/services/index/src/providers/__init__.py
    - migrations.py: confirmed at mcp-memory-local/services/index/src/migrations.py (2 existing migrations)
    - server.py: confirmed at mcp-memory-local/services/index/src/server.py (FilesystemProvider registered in lifespan)

---

READY FOR AUDITOR REVIEW
