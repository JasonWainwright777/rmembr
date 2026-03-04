"""Inter-service authentication via X-Internal-Token (§11.2)."""

import os
from functools import wraps

from starlette.requests import Request
from starlette.responses import JSONResponse


def get_internal_token() -> str:
    """Load the internal service token from environment."""
    token = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
    if not token:
        raise RuntimeError("INTERNAL_SERVICE_TOKEN environment variable is not set")
    return token


async def verify_internal_token(request: Request) -> JSONResponse | None:
    """Verify X-Internal-Token header. Returns error response if invalid, None if OK."""
    expected = get_internal_token()
    provided = request.headers.get("X-Internal-Token", "")
    if not provided:
        return JSONResponse(
            {"error": "missing X-Internal-Token header"},
            status_code=401,
        )
    if provided != expected:
        return JSONResponse(
            {"error": "invalid X-Internal-Token"},
            status_code=401,
        )
    return None


class InternalAuthMiddleware:
    """ASGI middleware that enforces X-Internal-Token on all requests except /health."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            # Skip auth for health endpoint
            if request.url.path == "/health":
                await self.app(scope, receive, send)
                return
            error_response = await verify_internal_token(request)
            if error_response:
                await error_response(scope, receive, send)
                return
        await self.app(scope, receive, send)
