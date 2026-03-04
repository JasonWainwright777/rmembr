"""Vector search over memory chunks (§5.1)."""

from src.embeddings import embed_query  # noqa: index service local import


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
    query_embedding = await embed_query(query)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Build filter conditions
    conditions = ["repo = $1", "ref = $2", "namespace = $3"]
    params: list = [repo, ref, namespace]
    param_idx = 4

    if filters:
        for key, value in filters.items():
            conditions.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1

    where_clause = " AND ".join(conditions)
    params.append(embedding_str)
    params.append(k)

    query_sql = f"""
        SELECT
            id, path, anchor, heading, chunk_text,
            source_kind, classification, content_hash,
            1 - (embedding <=> ${param_idx}::vector) AS similarity
        FROM memory_chunks
        WHERE {where_clause}
        ORDER BY embedding <=> ${param_idx}::vector
        LIMIT ${param_idx + 1}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query_sql, *params)

    return [
        {
            "id": row["id"],
            "path": row["path"],
            "anchor": row["anchor"],
            "heading": row["heading"],
            "snippet": row["chunk_text"][:500],
            "source_kind": row["source_kind"],
            "classification": row["classification"],
            "similarity": float(row["similarity"]),
        }
        for row in rows
    ]


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
    results = await search_repo_memory(pool, repo, task, k=k, ref=ref, namespace=namespace)

    if changed_files:
        # Boost results that match changed file paths
        for result in results:
            for cf in changed_files:
                if cf in result["path"]:
                    result["similarity"] = min(1.0, result["similarity"] + 0.1)
                    result["boosted"] = True
                    break

        results.sort(key=lambda r: r["similarity"], reverse=True)

    return results
