"""RetrievalEngine: orchestrates search -> rank -> normalize pipeline."""

import asyncio
import logging

from src.embeddings import embed_query

from .types import RankingConfig, RetrievalResult, ScoreComponents, ProvenanceInfo
from .ranker import Ranker

logger = logging.getLogger("index")


class RetrievalEngine:
    """Orchestrates search -> rank -> normalize pipeline."""

    def __init__(self, config: RankingConfig):
        self.config = config
        self._ranker = Ranker(config)

    async def search(
        self,
        pool,
        repo: str,
        query: str,
        k: int = 8,
        ref: str = "local",
        namespace: str = "default",
        filters: dict | None = None,
        changed_files: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Execute search and return normalized, ranked results."""
        try:
            # 1. Embed query
            query_embedding = await embed_query(query)

            # 2. Fetch raw candidates from DB (with provenance columns)
            raw_rows = await self._fetch_candidates(
                pool, repo, query_embedding, k, ref, namespace, filters
            )

            # 3. Normalize into RetrievalResult DTOs
            results = [self._normalize(row) for row in raw_rows]

            # 4. Apply ranking pipeline
            ranked = self._ranker.rank(results, changed_files=changed_files)

            # 5. Return top-k after ranking
            return ranked[:k]

        except (asyncio.TimeoutError, OSError) as e:
            logger.warning(f"RetrievalEngine.search degraded: {type(e).__name__}: {e}")
            return []
        except Exception as e:
            # Catch asyncpg errors and other DB issues
            if "Connection" in type(e).__name__ or "Postgres" in type(e).__name__:
                logger.warning(f"RetrievalEngine.search degraded: {type(e).__name__}: {e}")
                return []
            raise

    async def _fetch_candidates(self, pool, repo, embedding, k, ref, namespace, filters):
        """Fetch candidate chunks from DB with provenance columns."""
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

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
                provider_name, external_id, updated_at,
                1 - (embedding <=> ${param_idx}::vector) AS similarity
            FROM memory_chunks
            WHERE {where_clause}
            ORDER BY embedding <=> ${param_idx}::vector
            LIMIT ${param_idx + 1}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query_sql, *params)

        return rows

    def _normalize(self, row) -> RetrievalResult:
        """Convert DB row to RetrievalResult."""
        updated_at = row.get("updated_at")
        indexed_at_str = updated_at.isoformat() if updated_at else None

        return RetrievalResult(
            id=row["id"],
            path=row["path"],
            anchor=row["anchor"],
            heading=row["heading"],
            snippet=row["chunk_text"][:500],
            source_kind=row["source_kind"],
            classification=row["classification"],
            score=ScoreComponents(semantic=float(row["similarity"])),
            provenance=ProvenanceInfo(
                provider_name=row.get("provider_name"),
                external_id=row.get("external_id"),
                content_hash=row.get("content_hash", ""),
                indexed_at=indexed_at_str,
            ),
        )
