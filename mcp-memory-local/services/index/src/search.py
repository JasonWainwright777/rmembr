"""Vector search over memory chunks (§5.1).

Delegates to RetrievalEngine for search -> rank -> normalize pipeline.
Preserves backward-compatible dict return signatures.
"""

from src.retrieval import RetrievalEngine, RankingConfig


# Module-level engine instance, set by server.py lifespan
_engine: RetrievalEngine | None = None


def set_engine(engine: RetrievalEngine) -> None:
    """Set the module-level RetrievalEngine instance (called from server.py lifespan)."""
    global _engine
    _engine = engine


def _get_engine() -> RetrievalEngine:
    """Get the module-level engine, creating a default if not set."""
    global _engine
    if _engine is None:
        _engine = RetrievalEngine(RankingConfig())
    return _engine


async def search_repo_memory(
    pool,
    repo: str,
    query: str,
    k: int = 8,
    ref: str = "local",
    namespace: str = "default",
    filters: dict | None = None,
) -> list[dict]:
    """Semantic search over a repo's indexed memory chunks."""
    engine = _get_engine()
    results = await engine.search(
        pool, repo, query, k=k, ref=ref, namespace=namespace, filters=filters
    )
    return [r.to_dict() for r in results]


async def resolve_context(
    pool,
    repo: str,
    task: str,
    k: int = 12,
    ref: str = "local",
    namespace: str = "default",
    changed_files: list[str] | None = None,
) -> list[dict]:
    """Resolve context pointers for a task. Returns ranked chunk pointers.

    Optionally boosts chunks from changed_files paths.
    """
    engine = _get_engine()
    results = await engine.search(
        pool, repo, task, k=k, ref=ref, namespace=namespace, changed_files=changed_files
    )
    return [r.to_dict() for r in results]
