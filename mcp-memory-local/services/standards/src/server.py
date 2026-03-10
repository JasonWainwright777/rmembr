"""Standards service — serves enterprise standards from GitHub (§5.2)."""

import base64
import json
import os
import re
from contextlib import asynccontextmanager

import asyncpg
import httpx
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import sys
sys.path.insert(0, "/app/shared/src")
from validation import validate_standard_id, ValidationError
from structured_logging import setup_logging, get_request_id, request_id_var, new_request_id, TimedOperation
from auth import InternalAuthMiddleware


logger = setup_logging("standards")

# Module-level state (set in lifespan)
pool = None
_github: "GitHubStandardsClient | None" = None


def _parse_front_matter_text(text: str) -> dict:
    """Extract title and domain from YAML front matter in markdown text."""
    result = {"title": "", "domain": ""}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
            result["title"] = fm.get("title", "")
            result["domain"] = fm.get("domain", "")
        except Exception:
            pass
    return result


class GitHubStandardsClient:
    """Fetches enterprise standards from GitHub with Postgres-backed caching."""

    def __init__(self, db_pool, owner_repo: str, branch: str = "main"):
        self._pool = db_pool
        self._owner_repo = owner_repo
        self._branch = branch
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        self._api_url = api_url
        token = os.environ.get("GITHUB_TOKEN", "")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )
        # In-memory tree: {relative_path: sha}  e.g. {"enterprise/bicep/infrastructure-as-code.md": "abc123"}
        self._tree: dict[str, str] = {}
        # In-memory metadata cache: {std_id: {title, domain}}
        self._metadata: dict[str, dict] = {}
        self._tree_loaded = False

    async def _refresh_tree(self) -> None:
        """Fetch the .ai/memory tree from GitHub, using ETag caching."""
        cache_key = f"standards:{self._owner_repo}:{self._branch}"

        # Check DB for cached ETag
        old_etag = None
        old_tree = None
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT etag, blob_shas FROM github_cache "
                        "WHERE cache_type = 'tree_etag' AND cache_key = $1",
                        cache_key,
                    )
                if row:
                    old_etag = row["etag"]
                    old_tree = json.loads(row["blob_shas"]) if row["blob_shas"] else {}
            except Exception:
                logger.warning("Failed to read standards tree cache", exc_info=True)

        # Fetch tree from GitHub
        url = f"{self._api_url}/repos/{self._owner_repo}/git/trees/{self._branch}:.ai"
        headers = {}
        if old_etag:
            headers["If-None-Match"] = old_etag

        resp = await self._client.get(url, params={"recursive": "1"}, headers=headers)

        if resp.status_code == 304 and old_tree:
            # Tree unchanged — use cached version
            self._tree = {k: v for k, v in old_tree.items() if not k.startswith("_")}
            self._tree_loaded = True
            logger.info("Standards tree unchanged (304)")
            return

        if resp.status_code != 200:
            if old_tree:
                # Fall back to cached tree on error
                self._tree = {k: v for k, v in old_tree.items() if not k.startswith("_")}
                self._tree_loaded = True
                logger.warning(f"GitHub tree fetch failed ({resp.status_code}), using cached tree")
                return
            logger.error(f"GitHub tree fetch failed: {resp.status_code} {resp.text}")
            self._tree_loaded = True
            return

        tree_data = resp.json()
        new_etag = resp.headers.get("ETag")
        new_tree: dict[str, str] = {}

        for entry in tree_data.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = entry["path"]  # e.g. "memory/enterprise/bicep/infrastructure-as-code.md"
            if path.startswith("memory/enterprise/") and path.endswith(".md"):
                # Strip "memory/" prefix to get relative path
                rel = path[len("memory/"):]  # "enterprise/bicep/infrastructure-as-code.md"
                new_tree[rel] = entry["sha"]
            # Also capture schema files
            elif path.startswith("memory/enterprise/") and (
                path.endswith(".schema.json") or path.endswith(".schema.yaml")
                or path.endswith(".json") or path.endswith(".yaml")
            ):
                rel = path[len("memory/"):]
                new_tree[rel] = entry["sha"]

        self._tree = new_tree
        self._tree_loaded = True
        # Clear metadata cache when tree changes
        self._metadata.clear()

        # Persist to DB
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO github_cache (cache_type, cache_key, etag, blob_shas)
                        VALUES ('tree_etag', $1, $2, $3::jsonb)
                        ON CONFLICT (cache_type, cache_key) DO UPDATE SET
                            etag = EXCLUDED.etag,
                            blob_shas = EXCLUDED.blob_shas,
                            updated_at = now()
                        """,
                        cache_key, new_etag, json.dumps(new_tree),
                    )
            except Exception:
                logger.warning("Failed to write standards tree cache", exc_info=True)

        logger.info(f"Standards tree loaded: {len(new_tree)} files from {self._owner_repo}")

    async def _ensure_tree(self) -> None:
        """Ensure tree is loaded (lazy init)."""
        if not self._tree_loaded:
            await self._refresh_tree()

    async def _fetch_blob(self, sha: str) -> str | None:
        """Fetch blob content by SHA, with DB caching."""
        # Check DB cache first
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT content FROM github_cache "
                        "WHERE cache_type = 'blob' AND cache_key = $1",
                        sha,
                    )
                if row:
                    return row["content"]
            except Exception:
                logger.warning("Failed to read blob cache", exc_info=True)

        # Fetch from GitHub
        url = f"{self._api_url}/repos/{self._owner_repo}/git/blobs/{sha}"
        resp = await self._client.get(url)
        if resp.status_code != 200:
            logger.error(f"Blob fetch failed for {sha}: {resp.status_code}")
            return None

        data = resp.json()
        text = base64.b64decode(data["content"]).decode("utf-8")

        # Cache in DB
        if self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO github_cache (cache_type, cache_key, content)
                        VALUES ('blob', $1, $2)
                        ON CONFLICT (cache_type, cache_key) DO NOTHING
                        """,
                        sha, text,
                    )
            except Exception:
                logger.warning("Failed to write blob cache", exc_info=True)

        return text

    def _path_to_id(self, rel_path: str) -> str:
        """Convert a relative tree path to a standard ID.

        e.g. "enterprise/bicep/infrastructure-as-code.md" -> "enterprise/bicep/infrastructure-as-code"
        """
        # Strip extension
        path = rel_path
        for ext in (".md", ".schema.json", ".schema.yaml", ".json", ".yaml"):
            if path.endswith(ext):
                path = path[:-len(ext)]
                break
        # Handle index files
        for idx in ("/index", "/README", "/standard"):
            if path.endswith(idx):
                path = path[:-len(idx)]
                break
        return path

    def _id_to_paths(self, standard_id: str) -> list[str]:
        """Convert a standard ID to candidate tree paths.

        e.g. "enterprise/bicep/infrastructure-as-code" ->
             ["enterprise/bicep/infrastructure-as-code.md",
              "enterprise/bicep/infrastructure-as-code/index.md", ...]
        """
        candidates = [
            f"{standard_id}.md",
            f"{standard_id}/index.md",
            f"{standard_id}/README.md",
            f"{standard_id}/standard.md",
        ]
        return candidates

    async def list_standards(self, domain: str | None = None) -> list[dict]:
        """List all standards with metadata."""
        await self._ensure_tree()

        standards = []
        seen_ids = set()

        for rel_path, sha in sorted(self._tree.items()):
            # Only list .md files under enterprise/
            if not rel_path.startswith("enterprise/") or not rel_path.endswith(".md"):
                continue

            std_id = self._path_to_id(rel_path)
            if std_id in seen_ids:
                continue
            seen_ids.add(std_id)

            if domain and not std_id.startswith(f"enterprise/{domain}"):
                continue

            # Get metadata (cached in memory)
            if std_id not in self._metadata:
                content = await self._fetch_blob(sha)
                if content:
                    self._metadata[std_id] = _parse_front_matter_text(content)
                else:
                    self._metadata[std_id] = {"title": "", "domain": ""}

            fm = self._metadata[std_id]
            standards.append({
                "id": std_id,
                "version": "local",
                "title": fm["title"] or std_id,
                "domain": fm["domain"] or "",
            })

        return standards

    async def get_standard(self, standard_id: str) -> dict | None:
        """Fetch full content of a standard."""
        await self._ensure_tree()

        for candidate in self._id_to_paths(standard_id):
            if candidate in self._tree:
                sha = self._tree[candidate]
                content = await self._fetch_blob(sha)
                if content:
                    return {
                        "id": standard_id,
                        "version": "local",
                        "path": f"github:{self._owner_repo}/{candidate}",
                        "content": content,
                    }
        return None

    async def get_schema(self, standard_id: str) -> dict | None:
        """Fetch schema file for a standard."""
        await self._ensure_tree()

        parts = standard_id
        for ext in [".schema.json", ".schema.yaml", ".json", ".yaml"]:
            candidate = f"{parts}{ext}"
            if candidate in self._tree:
                sha = self._tree[candidate]
                content = await self._fetch_blob(sha)
                if content:
                    return {
                        "id": standard_id,
                        "version": "local",
                        "path": f"github:{self._owner_repo}/{candidate}",
                        "content": content,
                    }
        return None

    async def is_available(self) -> bool:
        """Check if GitHub API is reachable."""
        try:
            resp = await self._client.get(
                f"{self._api_url}/repos/{self._owner_repo}",
            )
            return resp.status_code == 200
        except Exception:
            return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, _github
    logger.info("Standards service starting")

    # Create DB pool for caching
    try:
        pool = await asyncpg.create_pool(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            database=os.environ.get("POSTGRES_DB", "memory"),
            user=os.environ.get("POSTGRES_USER", "memory"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            min_size=1,
            max_size=3,
        )
        logger.info("Standards DB pool created")
    except Exception as e:
        logger.error(f"Failed to create DB pool: {e}")
        pool = None

    # Initialize GitHub client
    owner_repo = os.environ.get("GITHUB_STANDARDS_REPO", "")
    branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")

    if owner_repo:
        _github = GitHubStandardsClient(pool, owner_repo, branch)
        # Warm cache on startup
        try:
            await _github._refresh_tree()
            logger.info(f"Standards GitHub client ready: {owner_repo}")
        except Exception as e:
            logger.error(f"Failed to load standards tree from GitHub: {e}")
    else:
        logger.warning("GITHUB_STANDARDS_REPO not set — standards service has no source")

    logger.info("Standards service ready")
    yield
    if pool:
        await pool.close()
    logger.info("Standards service stopped")


app = FastAPI(title="MCP Memory Standards", lifespan=lifespan)
app.add_middleware(InternalAuthMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", "")
    if rid:
        request_id_var.set(rid)
    else:
        new_request_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = get_request_id()
    return response


@app.get("/health")
async def health():
    github_ok = _github is not None and _github._tree_loaded and len(_github._tree) > 0
    return {
        "status": "healthy" if github_ok else "degraded",
        "service": "standards",
        "github_connected": _github is not None,
        "standards_loaded": len(_github._tree) if _github else 0,
    }


@app.post("/tools/get_standard")
async def tool_get_standard(request: Request):
    """MCP tool: get_standard(id, version) -> markdown content."""
    body = await request.json()
    try:
        standard_id = validate_standard_id(body.get("id", ""))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if not _github:
        return JSONResponse({"error": "Standards source not configured"}, status_code=503)

    with TimedOperation(logger, "get_standard", f"Fetching {standard_id}"):
        result = await _github.get_standard(standard_id)

    if result is None:
        return JSONResponse(
            {"error": f"Standard '{standard_id}' not found"},
            status_code=404,
        )

    return result


@app.post("/tools/list_standards")
async def tool_list_standards(request: Request):
    """MCP tool: list_standards(domain?, version) -> list of standard IDs."""
    body = await request.json()
    domain = body.get("domain")

    if not _github:
        return {"standards": [], "count": 0}

    with TimedOperation(logger, "list_standards", "Listing standards"):
        standards = await _github.list_standards(domain)

    return {"standards": standards, "count": len(standards)}


@app.post("/tools/get_schema")
async def tool_get_schema(request: Request):
    """MCP tool: get_schema(id, version) -> JSON/YAML schema content."""
    body = await request.json()
    try:
        standard_id = validate_standard_id(body.get("id", ""))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    if not _github:
        return JSONResponse({"error": "Standards source not configured"}, status_code=503)

    result = await _github.get_schema(standard_id)
    if result is None:
        return JSONResponse(
            {"error": f"Schema '{standard_id}' not found"},
            status_code=404,
        )

    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("STANDARDS_PORT", "8082"))
    uvicorn.run(app, host="0.0.0.0", port=port)
