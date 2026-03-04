"""Input validation for all MCP tool parameters (§5.0)."""

import re


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation error on '{field}': {message}")


# Pattern for standard IDs: enterprise/domain/name
_STANDARD_ID_PATTERN = re.compile(r"^[a-z0-9\-]+(/[a-z0-9\-]+)*$")

# Path traversal characters
_PATH_TRAVERSAL_CHARS = re.compile(r"\.\.|[/\\]")

# Allowed filter keys and their expected types
_ALLOWED_FILTER_KEYS = {
    "source_kind": str,
    "classification": str,
    "heading": str,
    "path": str,
}


def validate_repo(repo: str, known_repos: list[str] | None = None) -> str:
    """Validate repo name. Rejects path traversal and optionally checks allowlist."""
    if not repo or not repo.strip():
        raise ValidationError("repo", "must not be empty")
    repo = repo.strip()
    if _PATH_TRAVERSAL_CHARS.search(repo):
        raise ValidationError("repo", "contains invalid characters (path traversal not allowed)")
    if known_repos is not None and repo not in known_repos:
        raise ValidationError("repo", f"unknown repo '{repo}'; allowed: {known_repos}")
    return repo


def validate_query(query: str, max_length: int = 2000) -> str:
    """Validate search query string."""
    if not query or not query.strip():
        raise ValidationError("query", "must not be empty")
    query = query.strip()
    if len(query) > max_length:
        raise ValidationError("query", f"exceeds maximum length of {max_length} characters")
    return query


def validate_k(k: int, min_val: int = 1, max_val: int = 100) -> int:
    """Validate result count parameter."""
    if not isinstance(k, int):
        raise ValidationError("k", "must be an integer")
    if k < min_val or k > max_val:
        raise ValidationError("k", f"must be between {min_val} and {max_val}")
    return k


def validate_namespace(namespace: str, allowed: list[str] | None = None) -> str:
    """Validate namespace parameter."""
    if not namespace or not namespace.strip():
        raise ValidationError("namespace", "must not be empty")
    namespace = namespace.strip()
    if allowed is not None and namespace not in allowed:
        raise ValidationError("namespace", f"unknown namespace '{namespace}'; allowed: {allowed}")
    return namespace


def validate_standard_id(standard_id: str) -> str:
    """Validate standard ID against path-based pattern."""
    if not standard_id or not standard_id.strip():
        raise ValidationError("id", "must not be empty")
    standard_id = standard_id.strip()
    if not _STANDARD_ID_PATTERN.match(standard_id):
        raise ValidationError(
            "id",
            "must match pattern: lowercase alphanumeric segments separated by '/' "
            "(e.g., 'enterprise/terraform/module-versioning')",
        )
    return standard_id


def validate_filters(filters: dict | None) -> dict | None:
    """Validate filter dict against allowed keys and types."""
    if filters is None:
        return None
    if not isinstance(filters, dict):
        raise ValidationError("filters", "must be a dictionary")
    for key, value in filters.items():
        if key not in _ALLOWED_FILTER_KEYS:
            raise ValidationError("filters", f"unknown filter key '{key}'; allowed: {list(_ALLOWED_FILTER_KEYS.keys())}")
        expected_type = _ALLOWED_FILTER_KEYS[key]
        if not isinstance(value, expected_type):
            raise ValidationError("filters", f"filter '{key}' must be of type {expected_type.__name__}")
    return filters
