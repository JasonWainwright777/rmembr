"""Unit tests for FilesystemProvider against fixture repos."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))

from src.providers.filesystem import FilesystemProvider
from src.providers.types import RepoDescriptor, DocumentDescriptor, DocumentContent
from tests.providers.conftest import SAMPLE_MANIFEST, SAMPLE_MARKDOWN


async def _collect(ait):
    result = []
    async for item in ait:
        result.append(item)
    return result


@pytest.fixture
def provider(temp_repo):
    return FilesystemProvider(repos_root=str(temp_repo))


@pytest.mark.asyncio
async def test_name_is_filesystem(provider):
    assert provider.name == "filesystem"


@pytest.mark.asyncio
async def test_enumerate_repos_finds_repo(provider):
    repos = await _collect(provider.enumerate_repos())
    assert len(repos) == 1
    repo = repos[0]
    assert repo.repo == "test-repo"
    assert repo.namespace == "default"
    assert repo.provider_name == "filesystem"
    assert repo.metadata["classification"] == "internal"
    assert repo.metadata["embedding_model"] == "nomic-embed-text"


@pytest.mark.asyncio
async def test_enumerate_repos_skips_non_memory_dirs(tmp_path):
    """Dirs without .ai/memory are skipped."""
    (tmp_path / "no-memory-repo").mkdir()
    provider = FilesystemProvider(repos_root=str(tmp_path))
    repos = await _collect(provider.enumerate_repos())
    assert len(repos) == 0


@pytest.mark.asyncio
async def test_enumerate_repos_nonexistent_root():
    provider = FilesystemProvider(repos_root="/nonexistent/path")
    repos = await _collect(provider.enumerate_repos())
    assert len(repos) == 0


@pytest.mark.asyncio
async def test_enumerate_documents_finds_markdown(provider):
    repos = await _collect(provider.enumerate_repos())
    docs = await _collect(provider.enumerate_documents(repos[0]))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.path.endswith("test-doc.md")
    assert doc.repo == repos[0]


@pytest.mark.asyncio
async def test_enumerate_documents_excludes_manifest(provider):
    repos = await _collect(provider.enumerate_repos())
    docs = await _collect(provider.enumerate_documents(repos[0]))
    paths = [d.path for d in docs]
    assert not any("manifest.yaml" in p for p in paths)


@pytest.mark.asyncio
async def test_enumerate_documents_includes_yaml(temp_repo):
    """Non-manifest YAML files are included."""
    repo_dir = temp_repo / "test-repo" / ".ai" / "memory"
    (repo_dir / "extra.yaml").write_text("key: value\nmore_content: " + "x" * 200, encoding="utf-8")
    provider = FilesystemProvider(repos_root=str(temp_repo))
    repos = await _collect(provider.enumerate_repos())
    docs = await _collect(provider.enumerate_documents(repos[0]))
    paths = [d.path for d in docs]
    assert any("extra.yaml" in p for p in paths)


@pytest.mark.asyncio
async def test_fetch_content_returns_text(provider):
    repos = await _collect(provider.enumerate_repos())
    docs = await _collect(provider.enumerate_documents(repos[0]))
    content = await provider.fetch_content(docs[0])
    assert isinstance(content, DocumentContent)
    assert "Overview" in content.text
    assert len(content.content_hash) == 64


@pytest.mark.asyncio
async def test_fetch_content_hash_is_sha256(provider):
    import hashlib
    repos = await _collect(provider.enumerate_repos())
    docs = await _collect(provider.enumerate_documents(repos[0]))
    content = await provider.fetch_content(docs[0])
    expected = hashlib.sha256(content.text.encode("utf-8")).hexdigest()
    assert content.content_hash == expected


@pytest.mark.asyncio
async def test_multiple_repos(tmp_path):
    """Multiple repos with memory dirs are all enumerated."""
    for name in ["repo-a", "repo-b"]:
        memory_dir = tmp_path / name / ".ai" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "manifest.yaml").write_text(SAMPLE_MANIFEST, encoding="utf-8")
        (memory_dir / "doc.md").write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    provider = FilesystemProvider(repos_root=str(tmp_path))
    repos = await _collect(provider.enumerate_repos())
    assert len(repos) == 2
    assert {r.repo for r in repos} == {"repo-a", "repo-b"}
