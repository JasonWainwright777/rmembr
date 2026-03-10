# Plan: GitHub-Backed Standards Service

## Problem

The standards service reads standard files directly from local disk (`REPOS_ROOT/enterprise-standards/.ai/memory/enterprise/**/*.md`). The local files are stale — the real enterprise-standards repo on GitHub (`JasonWainwright777/enterprise-standards`) has been updated (e.g., CUBI content in the Bicep standard) but the local copy doesn't reflect it.

The user wants to stop using local sample repos entirely and have everything come from GitHub.

## Current Architecture

- **Standards service** (`services/standards/src/server.py`): A file server that scans the local filesystem
- **`REPOS_ROOT=/repos`** with `./repos:/repos:ro` volume mount in docker-compose
- **`STANDARDS_REPO=enterprise-standards`** — points at the local directory
- **`ACTIVE_PROVIDERS=filesystem,github`** — filesystem still active for indexing
- **`GITHUB_REPOS=JasonWainwright777/rmembr`** — enterprise-standards not listed

## Why Not Other Approaches?

| Option | Verdict | Reason |
|--------|---------|--------|
| **B. Read from Postgres (memory_chunks)** | Eliminated | Index service chunks markdown into ~500-token pieces. `get_standard` needs full file content. Reassembling chunks is fragile and lossy. |
| **C. Standards queries Index service** | Eliminated | Same problem — index search returns chunks, not full documents. |
| **D. Git clone/pull sync** | Overkill | Operational complexity (cron/webhook, git binary in container, SSH keys). Heavy for ~20 markdown files. |
| **A. GitHub API directly** | Winner | Minimal new code, reuses proven pattern from `GitHubProvider`, removes local filesystem dependency. |

## Design: Option A — GitHub API Directly

The `GitHubProvider` in the index service already demonstrates the exact pattern: use the GitHub Trees/Blobs API with `httpx`, decode base64 content, cache in the `github_cache` Postgres table. The standards service does the same thing but simpler — it doesn't chunk or embed, just fetches and serves whole files.

---

## Implementation Steps

### Step 1: Add Postgres and GitHub Config to Standards Service

**File:** `docker-compose.yml`

**Changes to `standards` service:**
- Add environment variables:
  - `GITHUB_TOKEN` (same token the index service uses)
  - `GITHUB_API_URL` (default `https://api.github.com`)
  - `GITHUB_STANDARDS_REPO` (value: `JasonWainwright777/enterprise-standards`)
  - `GITHUB_DEFAULT_BRANCH` (default: `main`)
  - `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Add `depends_on: postgres: condition: service_healthy`
- Remove `volumes: ./repos:/repos:ro`
- Remove `REPOS_ROOT` and `STANDARDS_REPO` env vars (no longer needed)

**File:** `.env`
- Add `GITHUB_STANDARDS_REPO=JasonWainwright777/enterprise-standards`
- Add `JasonWainwright777/enterprise-standards` to `GITHUB_REPOS` (for index service too)
- Change `ACTIVE_PROVIDERS=github` (remove `filesystem`)

---

### Step 2: Create GitHub Client in Standards Service

**File:** `services/standards/src/server.py`

Replace filesystem functions (`_get_standards_root`, `_resolve_version_path`) with a GitHub-backed client. Model on the pattern in `services/index/src/providers/github.py`.

**Key components:**

```python
class GitHubStandardsClient:
    """Fetches enterprise standards from GitHub with Postgres-backed caching."""

    def __init__(self, pool, owner_repo, branch="main"):
        self._pool = pool
        self._owner_repo = owner_repo
        self._branch = branch
        self._client = httpx.AsyncClient(headers={...}, timeout=30.0)
        # In-memory tree cache: {path: {sha, title, domain}}
        self._tree_cache: dict[str, dict] = {}
        self._tree_etag: str | None = None

    async def list_standards(self, domain=None, version="local") -> list[dict]:
        """Fetch tree, parse front matter, return standard metadata."""

    async def get_standard(self, standard_id, version="local") -> dict | None:
        """Fetch full markdown content for a standard."""

    async def get_schema(self, standard_id, version="local") -> dict | None:
        """Fetch schema file for a standard."""
```

**Tree fetching:**
- Call `GET /repos/{owner_repo}/git/trees/{branch}:.ai` with `recursive=1`
- Filter for `memory/enterprise/**/*.md` paths
- Use ETag-based caching (304 = no changes)
- Cache tree and blob SHAs in `github_cache` table (reuse existing table from migration 3)

**Blob fetching:**
- Call `GET /repos/{owner_repo}/git/blobs/{sha}`
- Decode base64 content
- Cache in `github_cache` table with `cache_type='blob'`

**Front matter parsing:**
- Parse YAML front matter from cached blob content
- Extract `title`, `domain` for `list_standards` metadata
- Cache parsed metadata in memory (refreshes when tree ETag changes)

---

### Step 3: Modify the Three Endpoints

**`/tools/list_standards`:**
- Instead of `root.rglob("*.md")`, use tree API to get all `.md` files under `.ai/memory/enterprise/`
- For each file, fetch blob content (cached) and parse front matter
- Return `{id, version, title, domain}` as before

**`/tools/get_standard`:**
- Resolve standard ID to a path using the cached tree listing (instead of filesystem `exists()`)
- Fetch blob content by SHA from cache or GitHub API
- Return `{id, version, path, content}`

**`/tools/get_schema`:**
- Same approach: resolve schema path from tree listing, fetch blob content

---

### Step 4: Startup, Health Check, and DB Pool

**Lifespan function:**
- Create asyncpg connection pool (copy pattern from `services/index/src/db.py`)
- Create `httpx.AsyncClient` with GitHub auth headers
- Do an initial tree fetch to warm the cache

**Health endpoint:**
- Check GitHub API reachability instead of `root.exists()`
- Check Postgres connection

---

### Step 5: Update .env and docker-compose

**`.env` changes:**
```env
ACTIVE_PROVIDERS=github
GITHUB_REPOS=JasonWainwright777/rmembr,JasonWainwright777/enterprise-standards
GITHUB_STANDARDS_REPO=JasonWainwright777/enterprise-standards
```

**docker-compose.yml:** See Step 1 above.

---

### Step 6: Update Setup Documentation

**File:** `prompts/setup-rmembr-on-new-repo.md`

Add a section explaining:
- Enterprise standards are served from GitHub, not local files
- To add a new standards repo, set `GITHUB_STANDARDS_REPO` in `.env`
- The standards service caches content in Postgres — no local file sync needed

---

## Migration Notes

- **No DB migration needed** — reuses existing `github_cache` table (index migration 3)
- **Both services share Postgres** — standards service connects to the same DB
- **Startup ordering** — `depends_on: postgres: condition: service_healthy` ensures DB is ready
- **Rate limits** — enterprise-standards has ~10-20 files. Cold start = ~20 API calls. Subsequent calls use ETag caching (0-2 API calls). Well within GitHub's 5000/hour limit.

## Scope Estimate

- **~80 lines** new GitHub client code in `server.py`
- **~30 lines** modified endpoint logic
- **~10 lines** docker-compose changes
- **~40 lines** removed (filesystem-specific code)
- Net change is small and confined to `server.py` + `docker-compose.yml` + `.env`

## Risk & Rollback

- **Low risk**: If GitHub API is unreachable, standards service degrades gracefully (cached data still served from Postgres)
- **Rollback**: Re-add `REPOS_ROOT` env var and `repos` volume mount to restore filesystem mode
- **No breaking API changes** — endpoint signatures unchanged
