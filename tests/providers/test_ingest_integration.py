"""Integration test: provider -> ingest pipeline -> DB.

This test validates end-to-end flow using MockProvider without requiring
running services (mocks the DB pool and embeddings).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))

from src.providers.types import RepoDescriptor, DocumentDescriptor, DocumentContent
from src.providers.registry import ProviderRegistry
from src.providers.filesystem import FilesystemProvider
from src.ingest import index_repo, index_all, set_registry
from tests.providers.conftest import MockProvider, SAMPLE_MARKDOWN


class _FakeAsyncCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        pass


def _make_mock_pool():
    """Create a mock asyncpg pool that tracks executed SQL."""
    executed = []
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=lambda *args: executed.append(("execute", args)))
    conn.fetch = AsyncMock(return_value=[])  # No existing chunks

    pool = MagicMock()
    pool.acquire.return_value = _FakeAsyncCtx(conn)

    return pool, conn, executed


def _make_mock_embeddings(dim=768):
    """Return a mock embed_texts that returns zero vectors."""
    async def mock_embed(texts):
        return [[0.0] * dim for _ in texts]
    return mock_embed


@pytest.fixture
def mock_registry(mock_provider):
    reg = ProviderRegistry()
    reg.register(mock_provider)
    set_registry(reg)
    return reg


@pytest.mark.asyncio
async def test_index_repo_with_mock_provider(mock_provider, mock_repo_descriptor, mock_registry):
    pool, conn, executed = _make_mock_pool()

    with patch("src.ingest.embed_texts", side_effect=_make_mock_embeddings()):
        result = await index_repo(pool, mock_repo_descriptor, ref="local")

    assert result["repo"] == "mock-repo"
    assert result["total_chunks"] > 0
    assert result["chunks_new"] > 0

    # Verify provider_name and external_id were passed in SQL
    insert_calls = [args for op, args in executed if op == "execute" and "INSERT INTO memory_chunks" in args[0]]
    assert len(insert_calls) > 0
    for call_args in insert_calls:
        # provider_name is $14, external_id is $15
        assert call_args[14] == "mock"  # provider_name
        assert call_args[15] == "mock://mock-repo"  # external_id


@pytest.mark.asyncio
async def test_index_repo_with_filesystem_provider(temp_repo):
    provider = FilesystemProvider(repos_root=str(temp_repo))
    reg = ProviderRegistry()
    reg.register(provider)
    set_registry(reg)

    pool, conn, executed = _make_mock_pool()

    # Get repo descriptor
    repos = []
    async for r in provider.enumerate_repos():
        repos.append(r)
    assert len(repos) == 1

    with patch("src.ingest.embed_texts", side_effect=_make_mock_embeddings()):
        result = await index_repo(pool, repos[0], ref="local")

    assert result["repo"] == "test-repo"
    assert result["total_chunks"] > 0
    assert result["chunks_new"] > 0

    # Verify provider_name is 'filesystem'
    insert_calls = [args for op, args in executed if op == "execute" and "INSERT INTO memory_chunks" in args[0]]
    for call_args in insert_calls:
        assert call_args[14] == "filesystem"


@pytest.mark.asyncio
async def test_index_all_with_mock_provider(mock_provider, mock_registry, monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDERS", "mock")
    pool, conn, executed = _make_mock_pool()

    with patch("src.ingest.embed_texts", side_effect=_make_mock_embeddings()):
        result = await index_all(pool, mock_registry, ref="local")

    assert result["repos_indexed"] == 1
    assert result["results"][0]["repo"] == "mock-repo"


@pytest.mark.asyncio
async def test_index_repo_skips_unchanged_chunks(mock_provider, mock_repo_descriptor, mock_registry):
    """If content_hash matches, chunks are skipped."""
    pool, conn, executed = _make_mock_pool()

    # First pass: index everything
    with patch("src.ingest.embed_texts", side_effect=_make_mock_embeddings()):
        result1 = await index_repo(pool, mock_repo_descriptor, ref="local")

    # Second pass: simulate existing chunks with matching hashes
    from chunking import chunk_markdown
    chunks = chunk_markdown(".ai/memory/test-doc.md", SAMPLE_MARKDOWN)
    existing_rows = [
        {"id": i + 1, "path": c.path, "anchor": c.anchor, "content_hash": c.content_hash}
        for i, c in enumerate(chunks)
    ]
    conn.fetch = AsyncMock(return_value=existing_rows)

    with patch("src.ingest.embed_texts", side_effect=_make_mock_embeddings()):
        result2 = await index_repo(pool, mock_repo_descriptor, ref="local")

    assert result2["skipped_unchanged"] == result1["total_chunks"]
    assert result2["chunks_new"] == 0
    assert result2["chunks_updated"] == 0
