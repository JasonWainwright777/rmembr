"""Gateway service — orchestrates Index + Standards, returns context bundles (§5.3, §10)."""

import asyncio
import hashlib
import json
import os
import re
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
from audit_log import AuditLogger
from metrics import METRICS_AVAILABLE, metrics_app, observe_latency, count_call, count_error, update_dependency_health

from src.policy import PolicyLoader, PolicyBundle


logger = setup_logging("gateway")
audit_logger = AuditLogger(logger)

# Priority class ordering for deterministic sort (§10.1 step 9)
PRIORITY_ORDER = {"enterprise_must_follow": 0, "repo_must_follow": 1, "task_specific": 2}

# Internal service URLs
INDEX_URL = os.environ.get("INDEX_URL", "http://index:8081")
STANDARDS_URL = os.environ.get("STANDARDS_URL", "http://standards:8082")

# Policy loader (initialized at module level, loaded in lifespan)
policy_loader = PolicyLoader(
    policy_file=os.environ.get("POLICY_FILE"),
    hot_reload=os.environ.get("POLICY_HOT_RELOAD", "false").lower() == "true",
)

PROXY_TIMEOUT = 120.0
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
HEALTH_PROBE_INTERVAL = 30  # seconds

# DB pool (set in lifespan)
pool = None
_health_probe_task = None


async def _check_index() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{INDEX_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def _check_standards() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{STANDARDS_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def _check_postgres() -> bool:
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
    except Exception:
        pass
    return False


async def _check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/version")
            return resp.status_code == 200
    except Exception:
        return False


async def _health_probe_loop():
    """Background task: probe dependencies every HEALTH_PROBE_INTERVAL seconds."""
    while True:
        try:
            await update_dependency_health(
                _check_index, _check_standards, _check_postgres, _check_ollama
            )
        except Exception:
            pass
        await asyncio.sleep(HEALTH_PROBE_INTERVAL)


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
    expires = datetime.now(timezone.utc) + timedelta(seconds=policy_loader.policy.budgets.cache_ttl_seconds)
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


# Stopwords for keyword matching (common words that add noise)
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "this",
    "that", "these", "those", "i", "we", "you", "he", "she", "it", "they",
    "me", "us", "him", "her", "them", "my", "our", "your", "his", "its",
    "their", "what", "which", "who", "whom", "how", "when", "where", "why",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very", "just",
    "about", "up", "out", "all", "some", "any", "each", "every", "both",
    "few", "more", "most", "other", "into", "over", "after", "before",
    "between", "under", "again", "further", "once", "here", "there",
    "also", "new", "write", "add", "create", "update", "implement",
    "build", "make", "use", "using", "set", "get",
})


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words, removing stopwords and short tokens."""
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - _STOPWORDS


def _select_standards(
    task: str,
    available: list[dict],
    pinned: list[str],
    max_standards: int = 5,
) -> list[dict]:
    """Select relevant standards for a task.

    1. Always include pinned standards
    2. Score remaining by keyword overlap between task and title+domain+id
    3. Return up to max_standards, pinned first then by score descending
    """
    task_tokens = _tokenize(task)
    pinned_set = set(pinned)

    pinned_results = []
    scored_candidates = []

    for std in available:
        std_id = std["id"]
        # Build searchable text from metadata
        std_text = f"{std.get('title', '')} {std.get('domain', '')} {std_id}"
        std_tokens = _tokenize(std_text)

        overlap = task_tokens & std_tokens
        score = len(overlap)

        entry = {**std, "_selection_score": score, "_matched_keywords": sorted(overlap)}

        if std_id in pinned_set:
            entry["_selection_reason"] = "pinned"
            pinned_results.append(entry)
        else:
            entry["_selection_reason"] = "keyword_match" if score > 0 else "none"
            scored_candidates.append(entry)

    # Sort candidates by score descending
    scored_candidates.sort(key=lambda x: x["_selection_score"], reverse=True)

    # Combine: pinned first, then scored matches, up to budget
    result = list(pinned_results)
    remaining_budget = max_standards - len(result)

    for candidate in scored_candidates:
        if remaining_budget <= 0:
            break
        if candidate["_selection_score"] > 0:
            result.append(candidate)
            remaining_budget -= 1

    return result


async def _get_pinned_standards(client: httpx.AsyncClient, repo: str) -> list[str]:
    """Fetch pinned standards from the repo's manifest via the index service."""
    try:
        resp = await client.get(
            f"{INDEX_URL}/internal/manifest/{repo}",
            headers=_internal_headers(),
        )
        if resp.status_code == 200:
            return resp.json().get("references_standards", [])
    except Exception:
        pass
    return []


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
    policy = policy_loader.policy
    allowed = policy.persona.allowed_classifications.get(persona, ["public"])
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
            provenance = chunk.get("provenance", {})
            if provenance.get("provider_name"):
                lines.append(f"*Provider: {provenance['provider_name']}*")
            lines.append("")
            lines.append(chunk.get("snippet", ""))
            lines.append("")

    return "\n".join(lines)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, _health_probe_task
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
    # Load policy bundle
    policy_loader.load()
    # Start dependency health probe background task
    if METRICS_AVAILABLE:
        _health_probe_task = asyncio.create_task(_health_probe_loop())
        logger.info("Dependency health probe started")
    logger.info("Gateway service ready")
    # Start MCP Streamable HTTP session manager if enabled.
    # Must live inside the main lifespan because mounted sub-app lifespans
    # are not propagated by FastAPI.
    from src.mcp_server import _session_manager as mcp_sm
    if mcp_sm:
        async with mcp_sm.run():
            yield
    else:
        yield
    # Cancel health probe task on shutdown
    if _health_probe_task is not None:
        _health_probe_task.cancel()
        try:
            await _health_probe_task
        except asyncio.CancelledError:
            pass
        _health_probe_task = None
    if pool:
        await pool.close()
    logger.info("Gateway service stopped")


app = FastAPI(title="MCP Memory Gateway", lifespan=lifespan)

# Mount /metrics endpoint when prometheus_client is available
if METRICS_AVAILABLE and metrics_app is not None:
    app.mount("/metrics", metrics_app)


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


async def handle_health() -> dict:
    """Health check handler — returns dependency status."""
    index_ok = await _check_index()
    standards_ok = await _check_standards()
    pg_ok = await _check_postgres()

    all_ok = index_ok and standards_ok and pg_ok
    return {
        "status": "healthy" if all_ok else "degraded",
        "service": "gateway",
        "index": index_ok,
        "standards": standards_ok,
        "postgres": pg_ok,
    }


@app.get("/health")
async def health():
    """Health check with dependency status."""
    return await handle_health()


async def handle_get_context_bundle(params: dict) -> dict:
    """Handler: get_context_bundle -> assembled context bundle (§10.1).

    Raises ValidationError on bad input.
    Returns dict with bundle_id, bundle, markdown, cached.
    Raises RuntimeError on upstream service failure (502-equivalent).
    """
    policy = policy_loader.policy
    repo = validate_repo(params.get("repo", ""))
    task = validate_query(params.get("task", ""))
    raw_k = params.get("k", policy.budgets.default_k)
    # Clamp k to max_sources budget
    if raw_k > policy.budgets.max_sources:
        logger.warning(
            f"Requested k={raw_k} exceeds max_sources={policy.budgets.max_sources}, clamping",
            extra={"tool": "get_context_bundle"},
        )
        raw_k = policy.budgets.max_sources
    k = validate_k(raw_k)
    namespace = validate_namespace(params.get("namespace", "default"))
    filters = validate_filters(params.get("filters"))

    persona = params.get("persona", "human")
    ref = params.get("ref", "local")
    standards_version = params.get("standards_version", "local")
    changed_files = params.get("changed_files")

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

    bundle_timeout = policy.budgets.tool_timeouts.get("get_context_bundle", 30)
    with TimedOperation(logger, "get_context_bundle", f"Building bundle for {repo}"):
        async with httpx.AsyncClient(timeout=float(bundle_timeout)) as client:
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
                raise RuntimeError(f"Index service error: {index_resp.text}")

            pointers = index_resp.json().get("pointers", [])

            # Step 6: Select and fetch relevant standards
            standards_content = []
            standards_refs = []
            standards_selection = []
            max_standards = policy.budgets.max_standards

            # 6a: Get all available standards with metadata
            standards_list_resp = await client.post(
                f"{STANDARDS_URL}/tools/list_standards",
                headers=_internal_headers(),
                json={"version": standards_version},
            )

            if standards_list_resp.status_code == 200:
                available_standards = standards_list_resp.json().get("standards", [])

                # 6b: Get pinned standards from repo manifest
                pinned = await _get_pinned_standards(client, repo)

                # 6c: Select relevant standards
                selected = _select_standards(task, available_standards, pinned, max_standards)
                standards_selection = [
                    {
                        "id": s["id"],
                        "reason": s.get("_selection_reason", "unknown"),
                        "score": s.get("_selection_score", 0),
                        "matched_keywords": s.get("_matched_keywords", []),
                    }
                    for s in selected
                ]

                # 6d: Fetch content only for selected standards
                for std in selected:
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
        budgeted = _apply_budget(sorted_chunks, policy.budgets.max_bundle_chars)

    bundle = {
        "bundle_id": bundle_id,
        "repo": repo,
        "task": task,
        "persona": persona,
        "ref": ref,
        "namespace": namespace,
        "standards_version": standards_version,
        "standards_content": standards_content,
        "standards_selection": standards_selection,
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


@app.post("/tools/get_context_bundle")
async def tool_get_context_bundle(request: Request):
    """MCP tool: get_context_bundle -> assembled context bundle (§10.1)."""
    body = await request.json()
    try:
        return await handle_get_context_bundle(body)
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=502)


async def handle_explain_context_bundle(params: dict) -> dict:
    """Handler: explain_context_bundle -> explanation of a previous bundle.

    Raises ValidationError if bundle_id missing.
    Raises LookupError if bundle not found.
    """
    bundle_id = params.get("bundle_id", "")
    if not bundle_id:
        raise ValidationError("bundle_id", "bundle_id is required")

    bundle = await _get_bundle_record(bundle_id)
    if not bundle:
        raise LookupError(f"Bundle '{bundle_id}' not found")

    explanation = {
        "bundle_id": bundle_id,
        "repo": bundle["repo"],
        "task": bundle["task"],
        "persona": bundle["persona"],
        "total_candidates": bundle["total_candidates"],
        "after_classification_filter": bundle["filtered_count"],
        "after_budget_trim": bundle["returned_count"],
        "standards_included": [s["id"] for s in bundle.get("standards_content", [])],
        "standards_selection": bundle.get("standards_selection", []),
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


@app.post("/tools/explain_context_bundle")
async def tool_explain_context_bundle(request: Request):
    """MCP tool: explain_context_bundle -> explanation of a previous bundle."""
    body = await request.json()
    try:
        return await handle_explain_context_bundle(body)
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except LookupError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


async def handle_validate_pack(params: dict) -> dict:
    """Handler: validate_pack -> validation report for a repo's memory pack.

    Raises ValidationError on bad input.
    """
    repo = validate_repo(params.get("repo", ""))
    ref = params.get("ref", "local")

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


@app.post("/tools/validate_pack")
async def tool_validate_pack(request: Request):
    """MCP tool: validate_pack -> validation report for a repo's memory pack."""
    body = await request.json()
    try:
        return await handle_validate_pack(body)
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# --- Proxy endpoints for CLI access (Index + Standards pass-through) ---

async def handle_proxy(service_url: str, path: str, body: dict) -> dict:
    """Forward a request to an internal service, return parsed response.

    Raises RuntimeError on non-2xx responses from downstream.
    """
    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        resp = await client.post(f"{service_url}{path}", headers=_internal_headers(), json=body)
    if resp.status_code >= 400:
        raise RuntimeError(f"Downstream service error (HTTP {resp.status_code})")
    return resp.json()


async def _proxy_to(service_url: str, path: str, body: dict) -> JSONResponse:
    """Forward a request to an internal service with auth headers (HTTP layer)."""
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


def _mount_mcp():
    """Mount MCP ASGI sub-app if MCP_ENABLED=true."""
    try:
        from src.mcp_server import get_mcp_asgi_app
        mcp_app = get_mcp_asgi_app()
        if mcp_app:
            app.mount("/", mcp_app)
            logger.info("MCP server mounted at /mcp")
    except ImportError:
        logger.warning("MCP SDK not available, MCP server disabled")


if os.environ.get("MCP_ENABLED", "false").lower() == "true":
    _mount_mcp()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("GATEWAY_PORT", "8080"))
    # Use string reference so uvicorn imports the module as "src.server",
    # avoiding dual-module issues where __main__ and src.server diverge.
    uvicorn.run("src.server:app", host="0.0.0.0", port=port)
