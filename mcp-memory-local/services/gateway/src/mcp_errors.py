"""MCP error mapping — translates internal exceptions to MCP error codes.

Sanitizes all error responses to prevent leaking internal service URLs,
token values, or stack traces.
"""

import re

from mcp.types import INVALID_PARAMS, INTERNAL_ERROR

# Patterns that must never appear in MCP error messages
_SANITIZE_PATTERNS = [
    re.compile(r"https?://[a-zA-Z0-9._-]+:\d+[^\s]*"),  # internal service URLs
    re.compile(r"INTERNAL_SERVICE_TOKEN\S*"),  # token references
    re.compile(r"/app/[^\s]+"),  # container paths
    re.compile(r"Traceback \(most recent call last\)[\s\S]*"),  # stack traces
]

_REPLACEMENT = "[redacted]"


def sanitize_message(msg: str) -> str:
    """Remove internal URLs, paths, tokens, and stack traces from error messages."""
    for pattern in _SANITIZE_PATTERNS:
        msg = pattern.sub(_REPLACEMENT, msg)
    return msg.strip()


def map_validation_error(exc) -> tuple[int, str]:
    """Map a ValidationError to MCP error code and sanitized message."""
    return INVALID_PARAMS, sanitize_message(str(exc))


def map_lookup_error(exc: LookupError) -> tuple[int, str]:
    """Map a LookupError (not found) to MCP error code and sanitized message."""
    return INVALID_PARAMS, sanitize_message(str(exc))


def map_runtime_error(exc: RuntimeError) -> tuple[int, str]:
    """Map a RuntimeError (upstream failure) to MCP internal error."""
    return INTERNAL_ERROR, sanitize_message(str(exc))


def map_authorization_error(exc) -> tuple[int, str]:
    """Map an AuthorizationError to MCP error code and sanitized message."""
    return INVALID_PARAMS, sanitize_message(str(exc))


def map_exception(exc: Exception) -> tuple[int, str]:
    """Map any exception to the appropriate MCP error code and sanitized message."""
    # Import here to avoid circular imports at module level
    from validation import ValidationError
    from src.policy.authz import AuthorizationError

    if isinstance(exc, AuthorizationError):
        return map_authorization_error(exc)
    if isinstance(exc, ValidationError):
        return map_validation_error(exc)
    if isinstance(exc, LookupError):
        return map_lookup_error(exc)
    if isinstance(exc, RuntimeError):
        return map_runtime_error(exc)
    return INTERNAL_ERROR, "Internal server error"
