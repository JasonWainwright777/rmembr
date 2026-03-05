"""Contract tests that any LocationProvider implementation must pass."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))

from src.providers.types import RepoDescriptor, DocumentDescriptor, DocumentContent
from src.providers.filesystem import FilesystemProvider
from tests.providers.conftest import MockProvider, SAMPLE_MANIFEST, SAMPLE_MARKDOWN


async def _collect_async_iter(ait):
    result = []
    async for item in ait:
        result.append(item)
    return result


class ContractSuite:
    """Reusable contract tests for any LocationProvider."""

    @staticmethod
    async def assert_provider_has_name(provider):
        assert isinstance(provider.name, str)
        assert len(provider.name) > 0

    @staticmethod
    async def assert_enumerate_repos_yields_descriptors(provider):
        repos = await _collect_async_iter(provider.enumerate_repos())
        assert isinstance(repos, list)
        for repo in repos:
            assert isinstance(repo, RepoDescriptor)
            assert repo.namespace
            assert repo.repo
            assert repo.provider_name == provider.name
            assert repo.external_id

    @staticmethod
    async def assert_enumerate_documents_yields_descriptors(provider):
        repos = await _collect_async_iter(provider.enumerate_repos())
        assert len(repos) > 0, "Need at least one repo for document enumeration test"
        for repo in repos:
            docs = await _collect_async_iter(provider.enumerate_documents(repo))
            assert isinstance(docs, list)
            for doc in docs:
                assert isinstance(doc, DocumentDescriptor)
                assert doc.repo == repo
                assert doc.path
                assert doc.external_id

    @staticmethod
    async def assert_fetch_content_returns_content(provider):
        repos = await _collect_async_iter(provider.enumerate_repos())
        assert len(repos) > 0
        for repo in repos:
            docs = await _collect_async_iter(provider.enumerate_documents(repo))
            for doc in docs:
                content = await provider.fetch_content(doc)
                assert isinstance(content, DocumentContent)
                assert content.doc == doc
                assert len(content.text) > 0
                assert len(content.content_hash) == 64  # SHA-256 hex


# --- FilesystemProvider contract tests ---

@pytest.fixture
def fs_provider(temp_repo):
    return FilesystemProvider(repos_root=str(temp_repo))


@pytest.mark.asyncio
async def test_filesystem_provider_has_name(fs_provider):
    await ContractSuite.assert_provider_has_name(fs_provider)


@pytest.mark.asyncio
async def test_filesystem_provider_enumerate_repos(fs_provider):
    await ContractSuite.assert_enumerate_repos_yields_descriptors(fs_provider)


@pytest.mark.asyncio
async def test_filesystem_provider_enumerate_documents(fs_provider):
    await ContractSuite.assert_enumerate_documents_yields_descriptors(fs_provider)


@pytest.mark.asyncio
async def test_filesystem_provider_fetch_content(fs_provider):
    await ContractSuite.assert_fetch_content_returns_content(fs_provider)


# --- MockProvider contract tests ---

@pytest.mark.asyncio
async def test_mock_provider_has_name(mock_provider):
    await ContractSuite.assert_provider_has_name(mock_provider)


@pytest.mark.asyncio
async def test_mock_provider_enumerate_repos(mock_provider):
    await ContractSuite.assert_enumerate_repos_yields_descriptors(mock_provider)


@pytest.mark.asyncio
async def test_mock_provider_enumerate_documents(mock_provider):
    await ContractSuite.assert_enumerate_documents_yields_descriptors(mock_provider)


@pytest.mark.asyncio
async def test_mock_provider_fetch_content(mock_provider):
    await ContractSuite.assert_fetch_content_returns_content(mock_provider)
