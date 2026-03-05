"""Fault-path tests: timeout/degraded-index scenarios yield partial well-formed responses."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))

import pytest

from src.retrieval.types import RankingConfig, RetrievalResult
from src.retrieval.engine import RetrievalEngine


def _make_db_row(id=1, similarity=0.85):
    return {
        "id": id,
        "path": ".ai/memory/doc.md",
        "anchor": "overview",
        "heading": "Overview",
        "chunk_text": "content",
        "source_kind": "repo_memory",
        "classification": "internal",
        "content_hash": "abc",
        "provider_name": "filesystem",
        "external_id": "fs://doc",
        "updated_at": datetime.now(timezone.utc),
        "similarity": similarity,
    }


@pytest.fixture
def mock_embed():
    with patch("src.retrieval.engine.embed_query", new_callable=AsyncMock) as mock:
        mock.return_value = [0.1] * 768
        yield mock


class TestDbConnectionTimeout:
    @pytest.mark.asyncio
    async def test_timeout_returns_empty_list(self, mock_embed):
        """DB connection timeout -> engine returns [] and doesn't raise."""
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=asyncio.TimeoutError("connection timed out"))
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert results == []
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_os_error_returns_empty_list(self, mock_embed):
        """OS-level connection error -> engine returns []."""
        pool = MagicMock()
        conn = AsyncMock()
        conn.fetch = AsyncMock(side_effect=OSError("Connection refused"))
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert results == []


class TestDbPartialResults:
    @pytest.mark.asyncio
    async def test_fewer_than_k_rows(self, mock_embed):
        """DB returns fewer rows than requested k -> engine returns all as valid DTOs."""
        rows = [_make_db_row(id=1, similarity=0.9)]
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=rows)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query", k=10)

        assert len(results) == 1
        assert isinstance(results[0], RetrievalResult)
        assert results[0].provenance.provider_name == "filesystem"

    @pytest.mark.asyncio
    async def test_nullable_provenance_fields_valid(self, mock_embed):
        """Rows with NULL provider_name/external_id still produce valid DTOs."""
        row = _make_db_row()
        row["provider_name"] = None
        row["external_id"] = None
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[row])
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert len(results) == 1
        assert results[0].provenance.provider_name is None
        assert results[0].provenance.external_id is None
        # Still serializable
        d = results[0].to_dict()
        assert "provenance" in d


class TestEmptyResultSchema:
    @pytest.mark.asyncio
    async def test_schema_identical_for_0_1_k_results(self, mock_embed):
        """JSON schema is identical whether 0, 1, or k results are returned."""
        engine = RetrievalEngine(RankingConfig())

        # 0 results
        conn0 = AsyncMock()
        conn0.fetch = AsyncMock(return_value=[])
        pool0 = MagicMock()
        pool0.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn0),
            __aexit__=AsyncMock(return_value=False),
        ))
        results_0 = await engine.search(pool0, "repo", "query")

        # 1 result
        conn1 = AsyncMock()
        conn1.fetch = AsyncMock(return_value=[_make_db_row(id=1)])
        pool1 = MagicMock()
        pool1.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn1),
            __aexit__=AsyncMock(return_value=False),
        ))
        results_1 = await engine.search(pool1, "repo", "query")

        # k results
        connk = AsyncMock()
        connk.fetch = AsyncMock(return_value=[_make_db_row(id=i) for i in range(5)])
        poolk = MagicMock()
        poolk.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=connk),
            __aexit__=AsyncMock(return_value=False),
        ))
        results_k = await engine.search(poolk, "repo", "query", k=5)

        # All return lists
        assert isinstance(results_0, list)
        assert isinstance(results_1, list)
        assert isinstance(results_k, list)

        assert len(results_0) == 0
        assert len(results_1) == 1
        assert len(results_k) == 5

        # All non-empty results have same dict keys
        if results_1:
            keys_1 = set(results_1[0].to_dict().keys())
        if results_k:
            keys_k = set(results_k[0].to_dict().keys())
            assert keys_1 == keys_k
