"""Canonical ID utilities for memory chunks and standards."""


def chunk_id(repo: str, path: str, anchor: str, ref: str = "local") -> str:
    """Generate a canonical chunk ID."""
    return f"{repo}:{ref}:{path}#{anchor}"


def standard_id(domain: str, name: str) -> str:
    """Generate a canonical standard ID."""
    return f"enterprise/{domain}/{name}"


def pack_id(repo: str, namespace: str = "default") -> str:
    """Generate a canonical memory pack ID."""
    return f"{namespace}/{repo}"
