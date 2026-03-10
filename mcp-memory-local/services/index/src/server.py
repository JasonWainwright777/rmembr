"""Index service — FastAPI server with MCP tools (§5.1)."""

import os

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.db import create_pool
from src.migrations import run_migrations
from src.ingest import index_repo as do_index_repo, index_all as do_index_all, set_registry
from src.search import search_repo_memory as do_search, resolve_context as do_resolve, set_engine
from src.retrieval import RetrievalEngine, RankingConfig
from src.providers import ProviderRegistry
from src.providers.filesystem import FilesystemProvider
from src.providers.github import GitHubProvider

# Use shared library imports via path
import sys
sys.path.insert(0, "/app/shared/src")
from validation import validate_repo, validate_query, validate_k, validate_namespace, validate_filters, ValidationError
from structured_logging import setup_logging, get_request_id, request_id_var, TimedOperation
from auth import InternalAuthMiddleware


logger = setup_logging("index")
pool = None
registry = None
retrieval_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, registry, retrieval_engine
    logger.info("Index service starting")
    pool = await create_pool()
    await run_migrations(pool)

    # Initialize retrieval engine with ranking config from env
    ranking_config = RankingConfig.from_env()
    retrieval_engine = RetrievalEngine(ranking_config)
    set_engine(retrieval_engine)
    logger.info(f"RetrievalEngine initialized with config: path_boost={ranking_config.path_boost_weight}, freshness_boost={ranking_config.freshness_boost_weight}, freshness_window={ranking_config.freshness_window_hours}h")

    # Initialize provider registry
    registry = ProviderRegistry()
    registry.register(FilesystemProvider())
    if os.environ.get("GITHUB_TOKEN"):
        registry.register(GitHubProvider(pool=pool))
    set_registry(registry)
    active = registry.active_providers()
    logger.info(f"Active providers: {[p.name for p in active]}")

    logger.info("Index service ready")
    yield
    if pool:
        await pool.close()
    logger.info("Index service stopped")


app = FastAPI(title="MCP Memory Index", lifespan=lifespan)
app.add_middleware(InternalAuthMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Extract or generate X-Request-ID."""
    rid = request.headers.get("X-Request-ID", "")
    if rid:
        request_id_var.set(rid)
    else:
        from structured_logging import new_request_id
        new_request_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = get_request_id()
    return response


@app.get("/health")
async def health():
    """Health check with dependency status."""
    pg_ok = False
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            pg_ok = True
    except Exception:
        pass

    status = "healthy" if pg_ok else "degraded"
    return {"status": status, "service": "index", "postgres": pg_ok}


@app.post("/tools/index_repo")
async def tool_index_repo(request: Request):
    """MCP tool: index_repo(repo, ref) -> indexing results."""
    body = await request.json()
    try:
        repo = validate_repo(body.get("repo", ""))
        ref = body.get("ref", "local")
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    provider_name = body.get("provider", "filesystem")
    try:
        provider = registry.get(provider_name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    # Find the repo descriptor from the provider
    repo_desc = None
    async for rd in provider.enumerate_repos():
        if rd.repo == repo:
            repo_desc = rd
            break
    if repo_desc is None:
        return JSONResponse({"error": f"Repo '{repo}' not found via provider '{provider_name}'"}, status_code=404)

    with TimedOperation(logger, "index_repo", f"Indexing {repo}"):
        result = await do_index_repo(pool, repo_desc, ref)
    return result


@app.post("/tools/index_all")
async def tool_index_all(request: Request):
    """MCP tool: index_all(ref) -> indexing results for all repos."""
    body = await request.json()
    ref = body.get("ref", "local")

    with TimedOperation(logger, "index_all", "Indexing all repos"):
        result = await do_index_all(pool, registry, ref)
    return result


@app.post("/tools/search_repo_memory")
async def tool_search_repo_memory(request: Request):
    """MCP tool: search_repo_memory -> semantic search results."""
    body = await request.json()
    try:
        repo = validate_repo(body.get("repo", ""))
        query = validate_query(body.get("query", ""))
        k = validate_k(body.get("k", 8))
        namespace = validate_namespace(body.get("namespace", "default"))
        filters = validate_filters(body.get("filters"))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    ref = body.get("ref", "local")

    with TimedOperation(logger, "search_repo_memory", f"Searching {repo}"):
        results = await do_search(pool, repo, query, k, ref, namespace, filters)
    return {"results": results, "count": len(results)}


@app.post("/tools/resolve_context")
async def tool_resolve_context(request: Request):
    """MCP tool: resolve_context -> ranked context pointers."""
    body = await request.json()
    try:
        repo = validate_repo(body.get("repo", ""))
        task = validate_query(body.get("task", ""))
        k = validate_k(body.get("k", 12))
        namespace = validate_namespace(body.get("namespace", "default"))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    ref = body.get("ref", "local")
    changed_files = body.get("changed_files")

    with TimedOperation(logger, "resolve_context", f"Resolving context for {repo}"):
        results = await do_resolve(pool, repo, task, k, ref, namespace, changed_files)
    return {"pointers": results, "count": len(results)}


@app.post("/tools/register_repo")
async def tool_register_repo(request: Request):
    """MCP tool: register_repo — register a GitHub repo for indexing."""
    body = await request.json()
    provider_name = body.get("provider", "github")
    repo_input = (body.get("repo") or "").strip()
    namespace = body.get("namespace", "default")

    if not repo_input:
        return JSONResponse({"error": "repo is required"}, status_code=400)

    # Validate provider exists
    try:
        provider = registry.get(provider_name)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    # For GitHub provider, validate owner/repo format
    if provider_name == "github":
        parts = repo_input.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return JSONResponse(
                {"error": "GitHub repos must be in 'owner/repo' format"},
                status_code=400,
            )
        external_id = repo_input
        repo_name = parts[1]

        # Validate the repo exists and has a manifest
        try:
            valid = await provider.validate_repo(external_id)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if not valid:
            return JSONResponse(
                {"error": f"Repo '{external_id}' not found or missing .ai/memory/manifest.yaml"},
                status_code=404,
            )
    else:
        external_id = repo_input
        repo_name = repo_input

    # Check max registered repos limit
    max_repos = int(os.environ.get("MAX_REGISTERED_REPOS", "50"))
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM repo_registry WHERE enabled = true"
        )
        if count >= max_repos:
            return JSONResponse(
                {"error": f"Registration limit reached ({max_repos} repos). Set MAX_REGISTERED_REPOS to increase."},
                status_code=429,
            )

        # Upsert into repo_registry
        row = await conn.fetchrow(
            """
            INSERT INTO repo_registry (provider, namespace, repo_name, external_id, enabled, registered_by)
            VALUES ($1, $2, $3, $4, true, $5)
            ON CONFLICT (provider, namespace, repo_name) DO UPDATE SET
                external_id = EXCLUDED.external_id,
                enabled = true,
                updated_at = now()
            RETURNING id, provider, namespace, repo_name, external_id, enabled, created_at, updated_at
            """,
            provider_name, namespace, repo_name, external_id,
            body.get("registered_by", "mcp"),
        )

    logger.info(f"Registered repo: {provider_name}/{repo_name} -> {external_id}")
    return {
        "status": "registered",
        "repo_name": row["repo_name"],
        "provider": row["provider"],
        "external_id": row["external_id"],
        "namespace": row["namespace"],
        "message": f"Repo registered. Run index_repo to index it.",
    }


@app.post("/tools/unregister_repo")
async def tool_unregister_repo(request: Request):
    """MCP tool: unregister_repo — soft-disable or purge a registered repo."""
    body = await request.json()
    repo_name = (body.get("repo") or "").strip()
    namespace = body.get("namespace", "default")
    provider_name = body.get("provider", "github")
    purge = body.get("purge", False)

    if not repo_name:
        return JSONResponse({"error": "repo is required"}, status_code=400)

    # Check if this is an env-var repo (cannot unregister)
    if provider_name == "github":
        try:
            provider = registry.get("github")
            env_repos = {r.split("/")[-1] for r in provider._repo_list()}
            if repo_name in env_repos:
                return JSONResponse(
                    {"error": f"Repo '{repo_name}' is configured via GITHUB_REPOS env var and cannot be unregistered via MCP. Remove it from the environment configuration instead."},
                    status_code=403,
                )
        except ValueError:
            pass

    async with pool.acquire() as conn:
        # Check repo exists in registry
        row = await conn.fetchrow(
            "SELECT id FROM repo_registry WHERE provider = $1 AND namespace = $2 AND repo_name = $3",
            provider_name, namespace, repo_name,
        )
        if not row:
            return JSONResponse(
                {"error": f"Repo '{repo_name}' not found in registry"},
                status_code=404,
            )

        # Soft-disable
        await conn.execute(
            "UPDATE repo_registry SET enabled = false, updated_at = now() WHERE id = $1",
            row["id"],
        )

        result = {"status": "disabled", "repo": repo_name}

        # Purge if requested
        if purge:
            deleted_chunks = await conn.fetchval(
                "DELETE FROM memory_chunks WHERE repo = $1 AND namespace = $2 RETURNING COUNT(*)",
                repo_name, namespace,
            )
            await conn.execute(
                "DELETE FROM memory_packs WHERE repo = $1 AND namespace = $2",
                repo_name, namespace,
            )
            await conn.execute(
                "DELETE FROM repo_registry WHERE id = $1",
                row["id"],
            )
            result["status"] = "purged"
            result["chunks_deleted"] = deleted_chunks or 0

    logger.info(f"Unregistered repo: {repo_name} (purge={purge})")
    return result


@app.post("/tools/list_repos")
async def tool_list_repos(request: Request):
    """MCP tool: list_repos — list all known repos and their index status."""
    repos = {}

    # 1. Env-var repos from active providers
    for provider in registry.active_providers():
        if provider.name == "github":
            for owner_repo in provider._repo_list():
                rname = owner_repo.split("/")[-1]
                repos[f"{provider.name}:{rname}"] = {
                    "repo_name": rname,
                    "provider": provider.name,
                    "external_id": owner_repo,
                    "namespace": "default",
                    "source": "env_var",
                    "enabled": True,
                    "indexed": False,
                    "last_indexed": None,
                }

    # 2. DB-registered repos
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT provider, namespace, repo_name, external_id, enabled, created_at FROM repo_registry"
        )
        for row in rows:
            key = f"{row['provider']}:{row['repo_name']}"
            if key in repos:
                # Already in env var — mark as both
                repos[key]["source"] = "env_var+registered"
            else:
                repos[key] = {
                    "repo_name": row["repo_name"],
                    "provider": row["provider"],
                    "external_id": row["external_id"],
                    "namespace": row["namespace"],
                    "source": "registered",
                    "enabled": row["enabled"],
                    "indexed": False,
                    "last_indexed": None,
                }

        # 3. Check index status from memory_packs
        packs = await conn.fetch(
            "SELECT repo, namespace, updated_at FROM memory_packs"
        )
        pack_map = {r["repo"]: r for r in packs}
        for entry in repos.values():
            pack = pack_map.get(entry["repo_name"])
            if pack:
                entry["indexed"] = True
                entry["last_indexed"] = pack["updated_at"].isoformat() if pack["updated_at"] else None

    return {"repos": list(repos.values()), "count": len(repos)}


@app.get("/internal/manifest/{repo}")
async def get_manifest(repo: str):
    """Internal endpoint: return manifest metadata for a repo (pinned standards, etc.)."""
    if not pool:
        return JSONResponse({"error": "Database not available"}, status_code=503)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT references_standards FROM memory_packs WHERE repo = $1 LIMIT 1",
            repo,
        )
    if not row:
        return {"repo": repo, "references_standards": []}

    import json
    refs = row["references_standards"]
    # refs is already parsed from JSONB by asyncpg
    if isinstance(refs, str):
        refs = json.loads(refs)
    return {"repo": repo, "references_standards": refs or []}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("INDEX_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)
