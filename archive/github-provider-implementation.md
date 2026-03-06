# GitHub Provider Implementation Plan

## Context

The rmembr POC currently uses a `FilesystemProvider` that reads `.ai/memory/` packs from a local `repos/` directory mounted into Docker. This plan adds a `GitHubProvider` that reads `.ai/memory/` packs directly from GitHub repositories via the GitHub REST API, authenticated with a Personal Access Token (PAT).

Once the GitHub provider is working, the filesystem provider can be disabled via `ACTIVE_PROVIDERS=github`.

## Scope

- Personal GitHub account (`github.com`) only — no GitHub Enterprise Server support needed yet
- Private repos only
- PAT authentication (classic or fine-grained)
- Two-layer indexing cache (tree ETag + blob SHA) to minimize API calls
- Rate limit awareness (log warnings, fail gracefully) but no retry/backoff system

## Decisions

- **Repo discovery**: The provider needs a configured list of repos to index. It does not scan the entire GitHub account. Rationale: avoids unnecessary API calls, and most repos won't have `.ai/memory/` packs.
- **Content fetching**: GitHub REST API (Trees + Blobs) per file, with a two-layer cache to minimize API calls. The `.ai` subtree is fetched with conditional requests (ETag/304), and blob content is cached by SHA. An unchanged repo costs 1 free API call (304). A repo with 1 changed file costs 1 free tree call + 1 blob fetch.
- **Tree scope**: Scoped to `.ai` subtree (`GET /repos/{owner}/{repo}/git/trees/{branch}:.ai?recursive=1`), not the full repo. This means changes outside `.ai/` don't invalidate the cache. Scoped to `.ai` (not `.ai/memory`) so future additions alongside `memory/` are covered.
- **Provider parameter**: The `index_repo` endpoint already accepts `"provider": "github"` in the request body (see `server.py:103`). The CLI needs a `--provider` flag to pass this through.

## Prerequisites

- A GitHub fine-grained PAT with **Contents: Read-only** and **Metadata: Read-only** permissions
- Token is set as a **host environment variable** (not stored in `.env` or any file in the repo):
  ```powershell
  [System.Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'github_pat_xxxxx', 'User')
  ```
  Docker Compose picks up host env vars automatically. If `GITHUB_TOKEN` is not in `.env`, the host value is used. This keeps the PAT out of all committed files.
- At least one GitHub repo with a `.ai/memory/` directory (rmembr itself qualifies)

---

## Phase 1: GitHubProvider Core

Build the provider class that implements the `LocationProvider` protocol.

### Task 1.1: Create `github.py` provider file

**File**: `mcp-memory-local/services/index/src/providers/github.py`

**What to build**:

A `GitHubProvider` class implementing:

- `name` property returning `"github"`
- `__init__` reads config from environment:
  - `GITHUB_TOKEN` (required) — PAT for authentication
  - `GITHUB_REPOS` (required) — comma-separated list of `owner/repo` strings (e.g., `jasonmcaffee/rmembr,jasonmcaffee/other-repo`)
  - `GITHUB_API_URL` (optional, default `https://api.github.com`) — for future GHE support
  - `GITHUB_DEFAULT_BRANCH` (optional, default `main`) — branch to read from
- Uses `httpx.AsyncClient` for API calls (already in requirements.txt)

**Acceptance criteria**:

- [ ] Class exists at the specified path
- [ ] Reads all 4 env vars, raises a clear error at init if `GITHUB_TOKEN` is empty
- [ ] `GITHUB_REPOS` empty or missing results in `enumerate_repos` yielding nothing (not an error)
- [ ] `httpx.AsyncClient` is created once in `__init__`, not per-request

### Task 1.2: Implement `enumerate_repos`

**What to build**:

`async enumerate_repos() -> AsyncIterator[RepoDescriptor]`

For each repo in `GITHUB_REPOS`:

1. Call `GET /repos/{owner}/{repo}/contents/.ai/memory/manifest.yaml` with auth header
2. If 404 → skip this repo (no `.ai/memory/` pack), log a warning
3. If 200 → decode the base64 content, parse with the shared `parse_manifest` function
4. Yield a `RepoDescriptor` with:
   - `namespace` from manifest `scope_namespace`
   - `repo` set to the repo name (not `owner/repo` — just the repo portion, e.g., `rmembr`)
   - `provider_name` = `"github"`
   - `external_id` = `owner/repo` (full qualified name, used later to fetch files)
   - `metadata` from manifest (same fields as `FilesystemProvider`)

**Acceptance criteria**:

- [ ] Repos without `.ai/memory/manifest.yaml` are skipped with a log warning, not an error
- [ ] Repos that return a non-200/non-404 status raise an exception with the status code and repo name
- [ ] `RepoDescriptor.repo` is just the repo name portion (e.g., `rmembr`), not `owner/repo`
- [ ] `RepoDescriptor.external_id` is the full `owner/repo` string
- [ ] Auth header is `Authorization: Bearer <GITHUB_TOKEN>`

### Task 1.3: Implement `enumerate_documents`

**What to build**:

`async enumerate_documents(repo: RepoDescriptor) -> AsyncIterator[DocumentDescriptor]`

1. Call `GET /repos/{owner}/{repo}/git/trees/{branch}:.ai?recursive=1` to get the `.ai` subtree only
2. Filter to paths matching `memory/**/*.md` and `memory/**/*.yaml` (paths in the subtree response are relative to `.ai/`)
3. Exclude `manifest.yaml`
4. Yield a `DocumentDescriptor` for each file with:
   - `repo` = the input `RepoDescriptor`
   - `path` = `.ai/{tree_path}` (reconstruct the repo-root-relative path, e.g., `.ai/memory/instructions.md`)
   - `anchor` = `None`
   - `external_id` = the file's `sha` from the tree response (used for content fetch and cache lookup)

**Why the `.ai` subtree**: Using `{branch}:.ai` scopes the tree to only the `.ai/` directory. Changes outside `.ai/` don't change this tree's SHA or ETag, so they don't invalidate the cache. This is critical for avoiding unnecessary API calls — most commits in a repo don't touch `.ai/`.

**Acceptance criteria**:

- [ ] Only `.md` and `.yaml` files under `.ai/memory/` are yielded
- [ ] `manifest.yaml` is excluded
- [ ] Files in nested subdirectories under `.ai/memory/` are included (e.g., `.ai/memory/topics/auth.md`)
- [ ] The `path` field uses forward slashes and is relative to the repo root
- [ ] If the `.ai/memory/` directory doesn't exist in the tree, yields nothing

### Task 1.4: Implement `fetch_content`

**What to build**:

`async fetch_content(doc: DocumentDescriptor) -> DocumentContent`

1. Call `GET /repos/{owner}/{repo}/git/blobs/{sha}` using `doc.external_id` (the blob SHA)
2. Decode the base64 content to UTF-8 text
3. Compute SHA-256 content hash
4. Return `DocumentContent` with `text`, `content_hash`, and `doc`

**Why the Blobs API**: We already have the SHA from the tree. The Blobs API returns raw content by SHA, avoids path encoding issues, and works for files of any size (up to 100MB).

**Acceptance criteria**:

- [ ] Content is decoded from base64 correctly (the Blobs API returns base64-encoded content)
- [ ] `content_hash` is SHA-256 of the decoded UTF-8 text (same as `FilesystemProvider`)
- [ ] Non-200 responses raise an exception with the status code, repo, and path
- [ ] The `doc` field on the returned `DocumentContent` is the same object passed in

---

## Phase 2: Registration and Configuration

Wire the provider into the Index service and make it configurable.

### Task 2.1: Register `GitHubProvider` in server startup

**File**: `mcp-memory-local/services/index/src/server.py`

**What to change**:

In the `lifespan` function, after registering `FilesystemProvider`:

1. Import `GitHubProvider`
2. Only instantiate and register if `GITHUB_TOKEN` is set in the environment (skip silently if not configured)
3. Register with `registry.register(GitHubProvider())`

**Acceptance criteria**:

- [ ] If `GITHUB_TOKEN` is not set, the service starts normally with only the filesystem provider — no error, no warning
- [ ] If `GITHUB_TOKEN` is set, `GitHubProvider` is registered and appears in the `Active providers` log line
- [ ] If `ACTIVE_PROVIDERS=github` and `GITHUB_TOKEN` is not set, the service logs a warning from the registry (existing behavior — registry logs unknown providers)

### Task 2.2: Add environment variables to docker-compose and .env.example

**Files**:
- `mcp-memory-local/docker-compose.yml` — add env vars to the `index` service
- `mcp-memory-local/.env.example` — add commented-out GitHub section

**What to add**:

```yaml
# docker-compose.yml — index service environment
GITHUB_TOKEN: ${GITHUB_TOKEN:-}
GITHUB_REPOS: ${GITHUB_REPOS:-}
GITHUB_API_URL: ${GITHUB_API_URL:-https://api.github.com}
GITHUB_DEFAULT_BRANCH: ${GITHUB_DEFAULT_BRANCH:-main}
ACTIVE_PROVIDERS: ${ACTIVE_PROVIDERS:-filesystem}
```

```bash
# .env.example
# --- GitHub Provider ---
# GITHUB_TOKEN is read from the host environment variable — do NOT store it here.
# Set it once on your machine:
#   Windows: [System.Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'github_pat_xxx', 'User')
#   Linux/macOS: export GITHUB_TOKEN=github_pat_xxx (add to ~/.bashrc or ~/.zshrc)
# GITHUB_REPOS=owner/repo1,owner/repo2
# GITHUB_API_URL=https://api.github.com
# GITHUB_DEFAULT_BRANCH=main
# ACTIVE_PROVIDERS=filesystem
```

**Acceptance criteria**:

- [ ] All 4 GitHub env vars are passed through to the index container
- [ ] `ACTIVE_PROVIDERS` is passed through (it was already in docker-compose, verify it's still there)
- [ ] `.env.example` has the GitHub section commented out with clear examples
- [ ] Default values mean the system behaves identically to before if no GitHub vars are set

### Task 2.3: Add `--provider` flag to CLI

**File**: `mcp-memory-local/scripts/mcp-cli.py`

**What to change**:

- Add `--provider` argument to the `index-repo` subcommand (default: `"filesystem"`)
- Pass `"provider": args.provider` in the request body

**Acceptance criteria**:

- [ ] `python scripts/mcp-cli.py index-repo rmembr` still works (defaults to filesystem)
- [ ] `python scripts/mcp-cli.py index-repo rmembr --provider github` passes `"provider": "github"` in the body
- [ ] The `index-all` command does not need a `--provider` flag (it uses all active providers via the registry)

---

## Phase 3: Error Handling and Rate Limit Awareness

### Task 3.1: Add rate limit header logging

**File**: `mcp-memory-local/services/index/src/providers/github.py`

**What to build**:

After each GitHub API response, check the rate limit headers:
- `X-RateLimit-Remaining`
- `X-RateLimit-Limit`
- `X-RateLimit-Reset` (Unix timestamp)

Log a warning when `X-RateLimit-Remaining` drops below 100.

**Acceptance criteria**:

- [ ] Rate limit headers are read after every API call
- [ ] A warning is logged when remaining < 100, including the reset timestamp
- [ ] If rate limit headers are missing (shouldn't happen, but defensive), no error

### Task 3.2: Handle common GitHub API errors

**File**: `mcp-memory-local/services/index/src/providers/github.py`

**What to build**:

Handle these HTTP status codes explicitly:
- `401` → raise with message "GitHub authentication failed — check GITHUB_TOKEN"
- `403` with `X-RateLimit-Remaining: 0` → raise with message "GitHub API rate limit exceeded — resets at {reset_time}"
- `403` without rate limit → raise with message "GitHub access denied for {repo} — check PAT permissions"
- `404` → handled per-method (skip in enumerate, raise in fetch)

**Acceptance criteria**:

- [ ] Each error case produces a clear, actionable message
- [ ] 401 during `enumerate_repos` fails the entire enumeration (not just one repo) — the token is bad
- [ ] 403 rate limit includes the human-readable reset time
- [ ] Errors include the repo name and/or file path for context

---

## Phase 4: Indexing Cache

Minimize GitHub API usage during `index-repo` by caching tree ETags and blob content. This cache is only used during indexing — search and bundle assembly always hit Postgres (which already has the chunk text and embeddings).

### How it works

```
index-repo called
    │
    ▼
Fetch .ai subtree with If-None-Match: <cached ETag>
    │
    ├── 304 Not Modified (FREE, no rate limit cost)
    │   └── Skip entire repo — nothing in .ai/ changed
    │
    └── 200 OK (1 API call)
        ├── Store new ETag in cache
        ├── Compare each blob SHA against cached blob SHAs
        │   ├── SHA matches → use cached content, skip fetch
        │   └── SHA differs → fetch blob (1 API call per changed file)
        │       └── Store blob content + SHA in cache
        └── Pass file contents to chunker → embedder → Postgres
```

**Cost summary per `index-repo` call:**

| Scenario | API calls | Rate limit cost |
|----------|-----------|-----------------|
| Nothing in `.ai/` changed | 1 (tree) | 0 (304 is free) |
| 1 file changed | 1 (tree) + 1 (blob) | 1 (tree 200) + 1 (blob) = 2 |
| All files changed (e.g., 10) | 1 (tree) + 10 (blobs) | 11 |
| First index (no cache) | 1 (tree) + N (blobs) | N + 1 |

### Task 4.1: Create `github_cache` table in migrations

**File**: `mcp-memory-local/services/index/src/migrations.py`

**What to build**:

Add a new migration that creates the `github_cache` table:

```sql
CREATE TABLE IF NOT EXISTS github_cache (
    id          BIGSERIAL PRIMARY KEY,
    cache_type  TEXT NOT NULL,          -- 'tree_etag' or 'blob'
    cache_key   TEXT NOT NULL,          -- tree: 'owner/repo:branch' | blob: blob SHA
    etag        TEXT,                   -- ETag header value (tree entries only)
    content     TEXT,                   -- file content (blob entries only)
    tree_sha    TEXT,                   -- tree SHA (tree entries only, for debugging)
    blob_shas   JSONB,                 -- {path: sha} map (tree entries only)
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT idx_github_cache_key UNIQUE (cache_type, cache_key)
);
```

Two types of rows:
- **`tree_etag`** rows: keyed by `owner/repo:branch`, store the ETag and a `{path: sha}` map of all blob SHAs in the `.ai` subtree
- **`blob`** rows: keyed by the blob SHA, store the decoded file content

**Acceptance criteria**:

- [ ] Table is created on service startup (idempotent — `IF NOT EXISTS`)
- [ ] Unique constraint on `(cache_type, cache_key)` enables upsert
- [ ] Migration does not affect existing tables
- [ ] Migration number follows the existing numbering convention in `migrations.py`

### Task 4.2: Implement tree cache in `enumerate_documents`

**File**: `mcp-memory-local/services/index/src/providers/github.py`

**What to change**:

`enumerate_documents` should:

1. Build the cache key: `{owner/repo}:{branch}`
2. Look up the existing `tree_etag` row from `github_cache`
3. If found, send the tree request with `If-None-Match: <cached_etag>` header
4. If 304 → the `.ai` subtree hasn't changed. Compare blob SHAs from the cached `blob_shas` JSON against what the caller already has. Yield `DocumentDescriptor`s using the cached blob SHAs.
5. If 200 → new tree. Store/update the ETag, tree SHA, and `{path: sha}` map in `github_cache`. Yield `DocumentDescriptor`s from the new tree.
6. If no cache row exists → normal 200 flow, create the cache row.

The provider needs a database pool reference to read/write cache. Add `pool` as an optional `__init__` parameter (set during server startup after pool is created).

**Acceptance criteria**:

- [ ] First call for a repo creates a `tree_etag` cache row
- [ ] Second call with unchanged `.ai/` sends `If-None-Match` and gets 304
- [ ] 304 response does not count against GitHub rate limit (verify via `X-RateLimit-Remaining` not decrementing)
- [ ] Changed `.ai/` returns 200, updates the cache row
- [ ] Cache key uses `owner/repo:branch` format
- [ ] `blob_shas` JSONB stores `{"memory/instructions.md": "abc123", ...}` (paths relative to `.ai/`)

### Task 4.3: Implement blob cache in `fetch_content`

**File**: `mcp-memory-local/services/index/src/providers/github.py`

**What to change**:

`fetch_content` should:

1. Check `github_cache` for a `blob` row with `cache_key = doc.external_id` (the blob SHA)
2. If found → return `DocumentContent` using cached `content`, skip the API call entirely
3. If not found → fetch from GitHub API, store the content in a new `blob` cache row, then return

Blob cache rows never need invalidation — a git blob SHA is a content hash. The same SHA always means the same content.

**Acceptance criteria**:

- [ ] First fetch for a blob SHA calls the GitHub API and creates a cache row
- [ ] Second fetch for the same SHA returns cached content with zero API calls
- [ ] Content hash in the returned `DocumentContent` matches the original (computed from cached content, not the git SHA)
- [ ] Different files with different SHAs are cached independently
- [ ] Cache row `content` is the decoded UTF-8 text, not base64

### Task 4.4: Pass database pool to GitHubProvider

**File**: `mcp-memory-local/services/index/src/server.py`

**What to change**:

In the `lifespan` function, pass the database pool to `GitHubProvider` so it can read/write the cache:

```python
if os.environ.get("GITHUB_TOKEN"):
    from src.providers.github import GitHubProvider
    registry.register(GitHubProvider(pool=pool))
```

**Acceptance criteria**:

- [ ] `GitHubProvider.__init__` accepts an optional `pool` parameter
- [ ] If `pool` is `None`, caching is disabled — all requests go to GitHub API (graceful degradation)
- [ ] Cache read/write failures are logged as warnings but don't fail the indexing operation

---

## Phase 5: Testing

### Task 5.1: Unit tests for GitHubProvider with mocked HTTP

**File**: `mcp-memory-local/tests/test_github_provider.py`

**What to test** (all using mocked httpx responses, no real API calls):

1. **`enumerate_repos` happy path**: Mock tree + manifest responses for 2 repos. Verify 2 `RepoDescriptor`s yielded with correct fields.
2. **`enumerate_repos` skip missing pack**: Mock 404 for manifest on one repo. Verify it's skipped, the other is yielded.
3. **`enumerate_documents` happy path**: Mock tree response with mix of `.md`, `.yaml`, `.py`, and `manifest.yaml` files. Verify only non-manifest `.md`/`.yaml` under `.ai/memory/` are yielded.
4. **`enumerate_documents` nested files**: Mock tree with `.ai/memory/topics/auth.md`. Verify it's included.
5. **`fetch_content` happy path**: Mock blob response with base64-encoded text. Verify decoded text and content hash.
6. **`fetch_content` non-UTF8**: Mock blob with binary content. Verify it raises a clear error.
7. **401 handling**: Mock 401 response. Verify the error message mentions GITHUB_TOKEN.
8. **403 rate limit**: Mock 403 with `X-RateLimit-Remaining: 0`. Verify error message mentions rate limit.
9. **Rate limit warning**: Mock response with `X-RateLimit-Remaining: 50`. Verify warning is logged.
10. **Tree cache hit (304)**: Mock 304 response. Verify no blob fetches occur and cached blob SHAs are used.
11. **Tree cache miss (200, new tree)**: Mock 200 with new tree. Verify cache row is created/updated.
12. **Blob cache hit**: Pre-populate blob cache row. Verify `fetch_content` returns cached content with zero API calls.
13. **Blob cache miss**: No cache row. Verify blob is fetched, cached, and returned.
14. **Cache degradation**: Set `pool=None`. Verify all operations still work (just no caching).

**Acceptance criteria**:

- [ ] All 14 test cases pass
- [ ] No real HTTP calls are made (fully mocked)
- [ ] Tests can run without `GITHUB_TOKEN` set

### Task 5.2: Integration test with real GitHub API

**File**: `mcp-memory-local/tests/test_github_provider_integration.py`

**What to test**:

1. Set `GITHUB_TOKEN` and `GITHUB_REPOS` to point at the `rmembr` repo
2. Call `enumerate_repos` → verify `rmembr` is returned with correct manifest fields
3. Call `enumerate_documents` → verify `.ai/memory/instructions.md` and other expected files are returned
4. Call `fetch_content` on one document → verify text content is non-empty and contains expected heading
5. Run full indexing: call `index_repo` with the GitHub provider's `RepoDescriptor` → verify chunks are created in Postgres

**Acceptance criteria**:

- [ ] Tests are skipped (not failed) if `GITHUB_TOKEN` is not set — use `pytest.mark.skipif`
- [ ] Test 5 verifies that the `provider_name` column in `memory_chunks` is `"github"` (not `"filesystem"`)
- [ ] Test 5 verifies that `external_id` in `memory_chunks` is the `owner/repo` string

### Task 5.3: End-to-end CLI test

**Manual test steps** (to be run once after all code is complete):

1. Ensure `GITHUB_TOKEN` is set as a host environment variable (not in `.env`). Set `.env`:
   ```bash
   # GITHUB_TOKEN is read from host environment — not stored here
   GITHUB_REPOS=<your-username>/rmembr
   ACTIVE_PROVIDERS=github
   ```
2. Rebuild and restart: `docker compose up -d --build`
3. Index via GitHub:
   ```bash
   python scripts/mcp-cli.py index-repo rmembr --provider github
   ```
   Expected: non-zero `chunks_new` or `skipped_unchanged`
4. Search:
   ```bash
   python scripts/mcp-cli.py search rmembr "how does chunking work"
   ```
   Expected: results returned with correct snippets
5. Get bundle:
   ```bash
   python scripts/mcp-cli.py get-bundle rmembr "add a GitHub provider" --persona agent
   ```
   Expected: bundle includes Provider Framework chunk
6. Switch back to filesystem:
   ```bash
   # Set ACTIVE_PROVIDERS=filesystem in .env
   docker compose up -d --force-recreate index
   python scripts/mcp-cli.py index-repo rmembr
   ```
   Expected: filesystem provider works as before

**Acceptance criteria**:

- [ ] Steps 3–5 succeed with real GitHub data
- [ ] Step 6 confirms filesystem provider still works after the change
- [ ] The indexed content from GitHub matches the content from filesystem (same chunks, same search results) since both read the same `.ai/memory/` files

---

## Phase 6: Documentation

### Task 6.1: Update `.env.example` with inline comments

Already covered in Task 2.2.

### Task 6.2: Update `docs/CONFIGURATION.md`

Add a "GitHub Provider" row group to the environment variables table with all 4 env vars, defaults, and descriptions.

**Acceptance criteria**:

- [ ] All 4 GitHub env vars are in the table
- [ ] The `ACTIVE_PROVIDERS` row mentions `github` as a valid value
- [ ] A note explains that `GITHUB_TOKEN` requires a fine-grained PAT with **Contents: Read-only** and **Metadata: Read-only** for private repos
- [ ] A note explains that the token should be set as a host environment variable, not in `.env`

### Task 6.3: Update `.ai/memory/` files

Update the following memory pack files to reflect the new provider:

- `system-architecture.md` — update Provider Framework section to mention GitHubProvider
- `configuration.md` — add GitHub env vars

**Acceptance criteria**:

- [ ] Memory pack files are accurate for the new state of the code
- [ ] No references to "current only implementation" for FilesystemProvider — now there are two

### Task 6.4: Copy updated memory pack to `repos/rmembr/` and reindex

Since the memory pack under `repos/rmembr/` is a manual copy (not a symlink), sync the updated `.ai/memory/` files and reindex.

```bash
cp -r .ai/memory/* mcp-memory-local/repos/rmembr/.ai/memory/
python scripts/mcp-cli.py index-repo rmembr
```

**Acceptance criteria**:

- [ ] `repos/rmembr/.ai/memory/` matches root `.ai/memory/`
- [ ] Reindex shows `chunks_updated` or `chunks_new` > 0 reflecting the doc changes

---

## Execution Order

```
Phase 1 (core provider):       1.1 → 1.2 → 1.3 → 1.4
Phase 2 (wiring):              2.1 → 2.2 → 2.3
Phase 3 (error handling):      3.1 → 3.2
Phase 4 (caching):             4.1 → 4.4 → 4.2 → 4.3
Phase 5 (testing):             5.1 → 5.2 → 5.3
Phase 6 (docs):                6.2 → 6.3 → 6.4
```

Phases 1 and 2 are sequential (2 depends on 1). Phase 3 can overlap with Phase 2. Phase 4 depends on Phase 1 (provider exists) and the database pool (Phase 2). Task 4.1 (migration) must come before 4.4 (pool wiring), which must come before 4.2/4.3 (cache logic). Phase 5 should start after Phase 4 is complete. Phase 6 can happen any time after Phase 5.

## Files Changed (Summary)

| File | Action |
|------|--------|
| `services/index/src/providers/github.py` | **New** — GitHubProvider class with caching |
| `services/index/src/providers/__init__.py` | Edit — add GitHubProvider to exports |
| `services/index/src/server.py` | Edit — conditionally register GitHubProvider with pool |
| `services/index/src/migrations.py` | Edit — add `github_cache` table migration |
| `mcp-memory-local/docker-compose.yml` | Edit — add GitHub env vars to index service |
| `mcp-memory-local/.env.example` | Edit — add GitHub section |
| `scripts/mcp-cli.py` | Edit — add `--provider` flag to `index-repo` |
| `tests/test_github_provider.py` | **New** — unit tests (including cache tests) |
| `tests/test_github_provider_integration.py` | **New** — integration tests |
| `docs/CONFIGURATION.md` | Edit — add GitHub provider docs |
| `.ai/memory/system-architecture.md` | Edit — update provider section |
| `.ai/memory/configuration.md` | Edit — add GitHub env vars |
