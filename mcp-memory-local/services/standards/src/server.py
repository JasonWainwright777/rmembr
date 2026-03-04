"""Standards service — serves canonical enterprise standards (§5.2)."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import sys
sys.path.insert(0, "/app/shared/src")
from validation import validate_standard_id, ValidationError
from structured_logging import setup_logging, get_request_id, request_id_var, new_request_id, TimedOperation
from auth import InternalAuthMiddleware


logger = setup_logging("standards")


def _get_standards_root() -> Path:
    """Get the root path for enterprise standards."""
    repos_root = Path(os.environ.get("REPOS_ROOT", "/repos"))
    standards_repo = os.environ.get("STANDARDS_REPO", "enterprise-standards")
    return repos_root / standards_repo / ".ai" / "memory"


def _resolve_version_path(base_path: Path, standard_id: str, version: str) -> Path | None:
    """Resolve a standard ID + version to a file path.

    Version resolution strategy (§Phase 2):
    - version="local" -> look in base standards path
    - version="v3" etc -> look in versioned subdirectory
    """
    parts = standard_id.split("/")
    # Try versioned path first: enterprise-standards/.ai/memory/v3/terraform/module-versioning/
    if version != "local":
        versioned = base_path / version / "/".join(parts[1:]) if len(parts) > 1 else base_path / version / parts[0]
        if versioned.exists():
            return versioned
        # Also try as a file
        for ext in [".md", ".yaml", ".json"]:
            candidate = versioned.with_suffix(ext)
            if candidate.exists():
                return candidate

    # Fall back to unversioned path
    unversioned = base_path / "/".join(parts)
    if unversioned.exists():
        return unversioned
    for ext in [".md", ".yaml", ".json"]:
        candidate = unversioned.with_suffix(ext)
        if candidate.exists():
            return candidate

    # Try as directory with index file
    if unversioned.is_dir():
        for name in ["index.md", "README.md", "standard.md"]:
            candidate = unversioned / name
            if candidate.exists():
                return candidate

    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Standards service starting")
    root = _get_standards_root()
    logger.info(f"Standards root: {root}, exists: {root.exists()}")
    logger.info("Standards service ready")
    yield
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
    root = _get_standards_root()
    return {
        "status": "healthy" if root.exists() else "degraded",
        "service": "standards",
        "standards_root_exists": root.exists(),
    }


@app.post("/tools/get_standard")
async def tool_get_standard(request: Request):
    """MCP tool: get_standard(id, version) -> markdown content."""
    body = await request.json()
    try:
        standard_id = validate_standard_id(body.get("id", ""))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    version = body.get("version", os.environ.get("DEFAULT_STANDARDS_VERSION", "local"))
    root = _get_standards_root()

    with TimedOperation(logger, "get_standard", f"Fetching {standard_id}@{version}"):
        resolved = _resolve_version_path(root, standard_id, version)

    if resolved is None:
        return JSONResponse(
            {"error": f"Standard '{standard_id}' not found (version={version})"},
            status_code=404,
        )

    content = resolved.read_text(encoding="utf-8")
    return {
        "id": standard_id,
        "version": version,
        "path": str(resolved),
        "content": content,
    }


@app.post("/tools/list_standards")
async def tool_list_standards(request: Request):
    """MCP tool: list_standards(domain?, version) -> list of standard IDs."""
    body = await request.json()
    domain = body.get("domain")
    version = body.get("version", os.environ.get("DEFAULT_STANDARDS_VERSION", "local"))
    root = _get_standards_root()

    if not root.exists():
        return {"standards": [], "count": 0}

    # Determine which directory to search
    if version != "local":
        search_root = root / version
        if not search_root.exists():
            return {"standards": [], "count": 0}
        # Versioned dirs don't include "enterprise/" prefix in their path,
        # so we prepend "enterprise/" to reconstruct canonical IDs
        id_prefix = "enterprise/"
    else:
        # For "local", search the unversioned enterprise/ directory
        search_root = root / "enterprise"
        if not search_root.exists():
            return {"standards": [], "count": 0}
        id_prefix = "enterprise/"

    standards = []
    # Collect version dirs to skip when listing "local"
    version_dirs = {d.name for d in root.iterdir() if d.is_dir() and d.name.startswith("v")}

    for md_file in sorted(search_root.rglob("*.md")):
        relative = md_file.relative_to(search_root)
        parts = list(relative.parts)

        # Skip version subdirectories when listing from enterprise/
        if parts and parts[0] in version_dirs:
            continue

        if parts and parts[-1] in ("README.md", "index.md", "standard.md"):
            parts = parts[:-1]
        else:
            # Remove .md extension from last part
            parts[-1] = parts[-1].rsplit(".", 1)[0]

        if not parts:
            continue

        std_id = id_prefix + "/".join(parts)

        if domain and not std_id.startswith(domain):
            continue

        standards.append({"id": std_id, "version": version})

    return {"standards": standards, "count": len(standards)}


@app.post("/tools/get_schema")
async def tool_get_schema(request: Request):
    """MCP tool: get_schema(id, version) -> JSON/YAML schema content."""
    body = await request.json()
    try:
        standard_id = validate_standard_id(body.get("id", ""))
    except ValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    version = body.get("version", os.environ.get("DEFAULT_STANDARDS_VERSION", "local"))
    root = _get_standards_root()

    # Look for schema files specifically
    parts = standard_id.split("/")
    for ext in [".schema.json", ".schema.yaml", ".json", ".yaml"]:
        if version != "local":
            candidate = root / version / "/".join(parts[1:]) if len(parts) > 1 else root / version / parts[0]
        else:
            candidate = root / "/".join(parts)
        candidate = candidate.with_suffix(ext)
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            return {"id": standard_id, "version": version, "path": str(candidate), "content": content}

    return JSONResponse(
        {"error": f"Schema '{standard_id}' not found (version={version})"},
        status_code=404,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("STANDARDS_PORT", "8082"))
    uvicorn.run(app, host="0.0.0.0", port=port)
