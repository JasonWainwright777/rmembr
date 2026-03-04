"""Gateway service — orchestrates Index + Standards, returns context bundles (§5.3, §10)."""

import hashlib
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

import sys
sys.path.insert(0, "/app/shared/src")
from validation import (
    validate_repo, validate_query, validate_k, validate_namespace,
    validate_filters, ValidationError,
)
from structured_logging import setup_logging, get_request_id, request_id_var, new_request_id, TimedOperation


logger = setup_logging("gateway")

# Persona -> max classification mapping (§11.4)
PERSONA_CLASSIFICATION = {
    "human": ["public", "internal"],
    "agent": ["public", "internal"],
    "external": ["public"],
}

# Priority class ordering for deterministic sort (§10.1 step 9)
PRIORITY_ORDER = {"enterprise_must_follow": 0, "repo_must_follow": 1, "task_specific": 2}

# Internal service URLs
INDEX_URL = os.environ.get("INDEX_URL", "http://index:8081")
STANDARDS_URL = os.environ.get("STANDARDS_URL", "http://standards:8082")

# Size budgets (§10.2)
MAX_BUNDLE_CHARS = int(os.environ.get("GATEWAY_MAX_BUNDLE_CHARS", "40000"))
DEFAULT_K = int(os.environ.get("GATEWAY_DEFAULT_K", "12"))
CACHE_TTL = int(os.environ.get("BUNDLE_CACHE_TTL_SECONDS", "300"))
PROXY_TIMEOUT = 120.0

# DB pool (set in lifespan)
pool = None


def _internal_headers() -> dict:
    """Headers for internal service calls."""
    token = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
    return {
        "X-Internal-Token": token,
        "X-Request-ID": get_request_id(),
        "Content-Type": "application/json",
    }


def _cache_key(namespace: str, repo: str, task: str, ref: str, standards_version: str) -> str:
    """Compute cache key for bundle caching (§10.1 step 4)."""
    task_hash = hashlib.sha256(task.encode()).hexdigest()[:16]
    raw = f"{namespace}:{repo}:{task_hash}:{ref}:{standards_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _get_cached_bundle(key: str) -> dict | None:
    """Check bundle_cache for a non-expired entry."""
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT bundle_json FROM bundle_cache WHERE cache_key = $1 AND expires_at > now() LIMIT 1",
            key,
        )
        if row:
            return json.loads(row["bundle_json"])
    return None


async def _store_cached_bundle(key: str, bundle: dict) -> None:
    """Store a bundle in the cache with TTL."""
    if not pool:
        return
    expires = datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL)
    bundle_json = json.dumps(bundle)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bundle_cache (cache_key, bundle_json, expires_at)
            VALUES ($1, $2::jsonb, $3)
            ON CONFLICT (cache_key) DO UPDATE SET
                bundle_json = EXCLUDED.bundle_json,
                expires_at = EXCLUDED.expires_at,
                created_at = now()
            """,
            key, bundle_json, expires,
        )


async def _store_bundle_record(bundle: dict) -> None:
    """Persist bundle for explain_context_bundle lookups."""
    if not pool:
        return
    bundle_id = bundle["bundle_id"]
    # Use bundle_id as a unique cache_key for lookups
    bundle_json = json.dumps(bundle)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)  # Keep for 24h
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bundle_cache (cache_key, bundle_json, expires_at)
            VALUES ($1, $2::jsonb, $3)
            ON CONFLICT (cache_key) DO NOTHING
            """,
            f"bundle:{bundle_id}", bundle_json, expires,
        )


async def _get_bundle_record(bundle_id: str) -> dict | None:
    """Retrieve a stored bundle by its ID."""
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT bundle_json FROM bundle_cache WHERE cache_key = $1 LIMIT 1",
            f"bundle:{bundle_id}",
        )
        if row:
            return json.loads(row["bundle_json"])
    return None


def _classify_chunk(chunk: dict, standards_refs: list[str]) -> str:
    """Assign priority class to a chunk."""
    if chunk.get("source_kind") == "enterprise_standard":
        return "enterprise_must_follow"
    for std_ref in standards_refs:
        if std_ref in chunk.get("path", ""):
            return "repo_must_follow"
    return "task_specific"


def _filter_by_classification(chunks: list[dict], persona: str) -> list[dict]:
    """Filter chunks by classification level for the given persona (§11.4)."""
    allowed = PERSONA_CLASSIFICATION.get(persona, ["public"])
    return [c for c in chunks if c.get("classification", "internal") in allowed]


def _deterministic_sort(chunks: list[dict]) -> list[dict]:
    """Sort chunks deterministically (§10.1 step 9)."""
    return sorted(
        chunks,
        key=lambda c: (
            PRIORITY_ORDER.get(c.get("_priority_class", "task_specific"), 2),
            -c.get("similarity", 0),
            c.get("path", ""),
        ),
    )


def _apply_budget(chunks: list[dict], max_chars: int) -> list[dict]:
    """Truncate bundle to fit within size budget (§10.2)."""
    result = []
    total = 0
    for chunk in chunks:
        snippet = chunk.get("snippet", "")
        if total + len(snippet) > max_chars:
            remaining = max_chars - total
            if remaining > 100:
                chunk = {**chunk, "snippet": snippet[:remaining] + "...(truncated)"}
                result.append(chunk)
            break
        result.append(chunk)
        total += len(snippet)
    return result


def _render_markdown(bundle: dict) -> str:
    """Render bundle as markdown for human consumption."""
    lines = [f"# Context Bundle: {bundle['repo']}", ""]
    lines.append(f"**Task:** {bundle['task']}")
    lines.append(f"**Ref:** {bundle['ref']}")
    lines.append(f"**Persona:** {bundle['persona']}")
    lines.append("")

    if bundle.get("standards_content"):
        lines.append("## Enterprise Standards")
        lines.append("")
        for std in bundle["standards_content"]:
            lines.append(f"### {std['id']}")
            content = std.get("content", "")
            if len(content) > 2000:
                content = content[:2000] + "\n\n...(truncated)"
            lines.append(content)
            lines.append("")

    if bundle.get("chunks"):
        lines.append("## Relevant Context")
        lines.append("")
        for chunk in bundle["chunks"]:
            priority = chunk.get("_priority_class", "task_specific")
            lines.append(f"### [{priority}] {chunk.get('heading', 'untitled')}")
            lines.append(f"*Source: {chunk.get('path', 'unknown')}#{chunk.get('anchor', '')}*")
            lines.append(f"*Similarity: {chunk.get('similarity', 0):.3f}*")
            lines.append("")
            lines.append(chunk.get("snippet", ""))
            lines.append("")

    return "\n".join(lines)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    logger.info("Gateway service starting")
    try:
        pool = await asyncpg.create_pool(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            database=os.environ.get("POSTGRES_DB", "memory"),
            user=os.environ.get("POSTGRES_USER", "memory"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            min_size=1,
            max_size=5,
        )
        # Ensure unique constraint on cache_key for upsert
        async with pool.acquire() as conn:
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_bundle_cache_key_unique ON bundle_cache (cache_key)"
            )
        logger.info("Gateway DB pool created")
    except Exception as e:
        logger.error(f"Failed to create DB pool: {e}")
        pool = None
    logger.info("Gateway service ready")
    yield
    if pool:
        await pool.close()
    logger.info("Gateway service stopped")


app = FastAPI(title="MCP Memory Gateway", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Generate X-Request-ID for all inbound calls (§6.3)."""
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
    """Health check with dependency status."""
    index_ok = False
    standards_ok = False
    pg_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{INDEX_URL}/health")
            index_ok = resp.status_code == 200
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{STANDARDS_URL}/health")
            standards_ok = resp.status_code == 200
    except Exception:
        pass
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            pg_ok = True
    except Exception:
        pass

    all_ok = index_ok and standards_ok and pg_ok
    return {
        "status": "healthy" if all_ok else "degraded",
        "service": "gateway",
        "index": index_ok,
        "standards": standards_ok,
        "postgres": pg_ok,
    }


@app.post("/tools/get_context_bundle")
async def tool_get_context_bundle(request: Request):
    """MCP tool: get_context_bundle -> assembled context bundle (§10.1)."""
    body = await request.json()
    try:
        repo = validate_repo(body.get("repo", ""))
        task = validate_query(body.get("task", ""))
        k = validate_k(body.get("k", DEFAULT_K))
        namespace = validate_namespace(body.get("namespace", "default"))
        filters = validate_filters(body.get("filters"))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    persona = body.get("persona", "human")
    ref = body.get("ref", "local")
    standards_version = body.get("standards_version", "local")
    changed_files = body.get("changed_files")

    # Step 4: Check bundle cache
    cache_k = _cache_key(namespace, repo, task, ref, standards_version)
    cached = await _get_cached_bundle(cache_k)
    if cached:
        logger.info("Bundle cache hit", extra={"tool": "get_context_bundle"})
        markdown = _render_markdown(cached)
        return {
            "bundle_id": cached["bundle_id"],
            "bundle": cached,
            "markdown": markdown,
            "cached": True,
        }

    bundle_id = str(uuid.uuid4())

    with TimedOperation(logger, "get_context_bundle", f"Building bundle for {repo}"):
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 5: Call Index for context pointers
            index_resp = await client.post(
                f"{INDEX_URL}/tools/resolve_context",
                headers=_internal_headers(),
                json={
                    "repo": repo,
                    "task": task,
                    "k": k,
                    "ref": ref,
                    "namespace": namespace,
                    "changed_files": changed_files,
                },
            )

            if index_resp.status_code != 200:
                return JSONResponse(
                    {"error": f"Index service error: {index_resp.text}"},
                    status_code=502,
                )

            pointers = index_resp.json().get("pointers", [])

            # Step 6: Fetch standards content
            standards_content = []
            standards_list_resp = await client.post(
                f"{STANDARDS_URL}/tools/list_standards",
                headers=_internal_headers(),
                json={"version": standards_version},
            )

            standards_refs = []
            if standards_list_resp.status_code == 200:
                standards_list = standards_list_resp.json().get("standards", [])
                for std in standards_list[:5]:
                    std_resp = await client.post(
                        f"{STANDARDS_URL}/tools/get_standard",
                        headers=_internal_headers(),
                        json={"id": std["id"], "version": standards_version},
                    )
                    if std_resp.status_code == 200:
                        std_data = std_resp.json()
                        standards_content.append(std_data)
                        standards_refs.append(std["id"])

        # Step 7: Filter by classification
        filtered = _filter_by_classification(pointers, persona)

        # Assign priority classes
        for chunk in filtered:
            chunk["_priority_class"] = _classify_chunk(chunk, standards_refs)

        # Step 9: Deterministic sort
        sorted_chunks = _deterministic_sort(filtered)

        # Step 10: Apply size budget
        budgeted = _apply_budget(sorted_chunks, MAX_BUNDLE_CHARS)

    bundle = {
        "bundle_id": bundle_id,
        "repo": repo,
        "task": task,
        "persona": persona,
        "ref": ref,
        "namespace": namespace,
        "standards_version": standards_version,
        "standards_content": standards_content,
        "chunks": budgeted,
        "total_candidates": len(pointers),
        "filtered_count": len(filtered),
        "returned_count": len(budgeted),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Step 11: Cache the bundle
    await _store_cached_bundle(cache_k, bundle)
    # Also persist for explain_context_bundle
    await _store_bundle_record(bundle)

    markdown = _render_markdown(bundle)

    return {
        "bundle_id": bundle_id,
        "bundle": bundle,
        "markdown": markdown,
        "cached": False,
    }


@app.post("/tools/explain_context_bundle")
async def tool_explain_context_bundle(request: Request):
    """MCP tool: explain_context_bundle -> explanation of a previous bundle."""
    body = await request.json()
    bundle_id = body.get("bundle_id", "")
    if not bundle_id:
        return JSONResponse({"error": "bundle_id is required"}, status_code=400)

    bundle = await _get_bundle_record(bundle_id)
    if not bundle:
        return JSONResponse({"error": f"Bundle '{bundle_id}' not found"}, status_code=404)

    explanation = {
        "bundle_id": bundle_id,
        "repo": bundle["repo"],
        "task": bundle["task"],
        "persona": bundle["persona"],
        "total_candidates": bundle["total_candidates"],
        "after_classification_filter": bundle["filtered_count"],
        "after_budget_trim": bundle["returned_count"],
        "standards_included": [s["id"] for s in bundle.get("standards_content", [])],
        "priority_breakdown": {},
        "chunks_summary": [],
    }

    for chunk in bundle.get("chunks", []):
        pc = chunk.get("_priority_class", "task_specific")
        explanation["priority_breakdown"][pc] = explanation["priority_breakdown"].get(pc, 0) + 1

    for chunk in bundle.get("chunks", []):
        explanation["chunks_summary"].append({
            "path": chunk.get("path"),
            "heading": chunk.get("heading"),
            "priority": chunk.get("_priority_class"),
            "similarity": chunk.get("similarity"),
            "classification": chunk.get("classification"),
        })

    return explanation


@app.post("/tools/validate_pack")
async def tool_validate_pack(request: Request):
    """MCP tool: validate_pack -> validation report for a repo's memory pack."""
    body = await request.json()
    try:
        repo = validate_repo(body.get("repo", ""))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    ref = body.get("ref", "local")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{INDEX_URL}/tools/search_repo_memory",
            headers=_internal_headers(),
            json={"repo": repo, "query": "test", "k": 1, "ref": ref},
        )

    issues = []
    if resp.status_code != 200:
        issues.append(f"Index service returned {resp.status_code}: {resp.text}")

    return {
        "repo": repo,
        "ref": ref,
        "valid": len(issues) == 0,
        "issues": issues,
    }


# --- Proxy endpoints for CLI access (Index + Standards pass-through) ---

async def _proxy_to(service_url: str, path: str, body: dict) -> JSONResponse:
    """Forward a request to an internal service with auth headers."""
    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        resp = await client.post(f"{service_url}{path}", headers=_internal_headers(), json=body)
    return JSONResponse(resp.json(), status_code=resp.status_code)


@app.post("/proxy/index/{tool}")
async def proxy_index(tool: str, request: Request):
    """Proxy to Index service tools (for CLI access)."""
    body = await request.json()
    return await _proxy_to(INDEX_URL, f"/tools/{tool}", body)


@app.post("/proxy/standards/{tool}")
async def proxy_standards(tool: str, request: Request):
    """Proxy to Standards service tools (for CLI access)."""
    body = await request.json()
    return await _proxy_to(STANDARDS_URL, f"/tools/{tool}", body)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("GATEWAY_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
