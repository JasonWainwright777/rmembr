"""Unit tests for RetrievalEngine with mock DB pool."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))

import pytest

from src.retrieval.types import RankingConfig
from src.retrieval.engine import RetrievalEngine


def _make_db_row(id=1, path=".ai/memory/doc.md", similarity=0.85, provider_name="filesystem",
                 external_id="fs://doc", content_hash="abc123", updated_at=None):
    """Create a mock DB row dict."""
    if updated_at is None:
        updated_at = datetime.now(timezone.utc)
    return {
        "id": id,
        "path": path,
        "anchor": "overview",
        "heading": "Overview",
        "chunk_text": "Test content for the chunk",
        "source_kind": "repo_memory",
        "classification": "internal",
        "content_hash": content_hash,
        "provider_name": provider_name,
        "external_id": external_id,
        "updated_at": updated_at,
        "similarity": similarity,
    }


def _mock_pool(rows):
    """Create a mock asyncpg pool that returns the given rows."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn),
                                                     __aexit__=AsyncMock(return_value=False)))
    return pool


@pytest.fixture
def mock_embed():
    with patch("src.retrieval.engine.embed_query", new_callable=AsyncMock) as mock:
        mock.return_value = [0.1] * 768
        yield mock


class TestRetrievalEngineSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self, mock_embed):
        rows = [_make_db_row(id=1, similarity=0.9), _make_db_row(id=2, similarity=0.8)]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query", k=8)

        assert len(results) == 2
        assert results[0].id == 1
        assert results[0].score.semantic == pytest.approx(0.9)
        assert results[1].id == 2

    @pytest.mark.asyncio
    async def test_provenance_populated(self, mock_embed):
        rows = [_make_db_row(provider_name="filesystem", external_id="fs://doc", content_hash="hash123")]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert results[0].provenance.provider_name == "filesystem"
        assert results[0].provenance.external_id == "fs://doc"
        assert results[0].provenance.content_hash == "hash123"
        assert results[0].provenance.indexed_at is not None

    @pytest.mark.asyncio
    async def test_null_provenance_fields(self, mock_embed):
        row = _make_db_row()
        row["provider_name"] = None
        row["external_id"] = None
        rows = [row]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert results[0].provenance.provider_name is None
        assert results[0].provenance.external_id is None

    @pytest.mark.asyncio
    async def test_changed_files_boost(self, mock_embed):
        rows = [
            _make_db_row(id=1, path="src/a.md", similarity=0.7),
            _make_db_row(id=2, path="src/b.md", similarity=0.75),
        ]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig(path_boost_weight=0.1))

        results = await engine.search(pool, "test-repo", "test query",
                                       changed_files=["src/a.md"])

        # a.md boosted to 0.8, b.md stays 0.75
        assert results[0].id == 1
        assert results[0].score.path_boost == 0.1

    @pytest.mark.asyncio
    async def test_top_k_truncation(self, mock_embed):
        rows = [_make_db_row(id=i, similarity=0.9 - i * 0.01) for i in range(10)]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query", k=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_embed):
        pool = _mock_pool([])
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_snippet_truncation(self, mock_embed):
        row = _make_db_row()
        row["chunk_text"] = "x" * 1000
        pool = _mock_pool([row])
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")

        assert len(results[0].snippet) == 500

    @pytest.mark.asyncio
    async def test_to_dict_backward_compat(self, mock_embed):
        rows = [_make_db_row(similarity=0.85)]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig())

        results = await engine.search(pool, "test-repo", "test query")
        d = results[0].to_dict()

        assert "similarity" in d
        assert "score_components" in d
        assert "provenance" in d
        assert d["similarity"] == pytest.approx(0.85)


class TestRankingReproducibility:
    @pytest.mark.asyncio
    async def test_deterministic_ordering(self, mock_embed):
        """Two consecutive calls with identical data produce identical ordering."""
        rows = [
            _make_db_row(id=1, similarity=0.9),
            _make_db_row(id=2, similarity=0.85),
            _make_db_row(id=3, similarity=0.85),  # tie with id=2
            _make_db_row(id=4, similarity=0.7),
        ]
        pool = _mock_pool(rows)
        engine = RetrievalEngine(RankingConfig())

        results1 = await engine.search(pool, "test-repo", "query")
        results2 = await engine.search(pool, "test-repo", "query")

        ids1 = [r.id for r in results1]
        ids2 = [r.id for r in results2]
        assert ids1 == ids2
        # Verify tie-breaking: id=2 before id=3
        assert ids1 == [1, 2, 3, 4]
