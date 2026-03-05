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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("INDEX_PORT", "8081"))
    uvicorn.run(app, host="0.0.0.0", port=port)
