"""Unit tests for GitHubProvider (mocked HTTP, no real API calls)."""

import base64
import hashlib
import json
import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

# Ensure shared lib path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "index", "src"))

from providers.types import RepoDescriptor, DocumentDescriptor, DocumentContent
from providers.github import GitHubProvider


MANIFEST_YAML = """\
pack_version: 1
scope:
  repo: test-repo
  namespace: default
owners: [team-a]
classification: internal
embedding:
  model: nomic-embed-text
  version: locked
"""


def _env(**overrides):
    """Build env dict with defaults for GitHubProvider."""
    env = {
        "GITHUB_TOKEN": "ghp_test_token_123",
        "GITHUB_REPOS": "octocat/test-repo",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_DEFAULT_BRANCH": "main",
    }
    env.update(overrides)
    return env


def _make_response(status_code, json_data=None, headers=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


@pytest.fixture
def provider():
    """Create a GitHubProvider with mocked env and no pool."""
    with patch.dict(os.environ, _env(), clear=False):
        p = GitHubProvider(pool=None)
    return p


# --- Test 1: __init__ raises ValueError on empty GITHUB_TOKEN ---
def test_init_raises_on_empty_token():
    with patch.dict(os.environ, _env(GITHUB_TOKEN=""), clear=False):
        with pytest.raises(ValueError, match="GITHUB_TOKEN is set but empty"):
            GitHubProvider()


# --- Test 2: name property returns "github" ---
def test_name_property(provider):
    assert provider.name == "github"


# --- Test 3: enumerate_repos yields nothing when GITHUB_REPOS empty ---
@pytest.mark.asyncio
async def test_enumerate_repos_empty_repos():
    with patch.dict(os.environ, _env(GITHUB_REPOS=""), clear=False):
        p = GitHubProvider(pool=None)
    repos = [r async for r in p.enumerate_repos()]
    assert repos == []


# --- Test 4: enumerate_repos yields RepoDescriptor on 200 ---
@pytest.mark.asyncio
async def test_enumerate_repos_success(provider):
    manifest_b64 = base64.b64encode(MANIFEST_YAML.encode()).decode()
    resp = _make_response(200, {"content": manifest_b64})

    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    repos = [r async for r in provider.enumerate_repos()]
    assert len(repos) == 1
    assert repos[0].repo == "test-repo"
    assert repos[0].provider_name == "github"
    assert repos[0].external_id == "octocat/test-repo"
    assert repos[0].namespace == "default"


# --- Test 5: enumerate_repos skips 404 with warning ---
@pytest.mark.asyncio
async def test_enumerate_repos_404_skips(provider):
    resp = _make_response(404)
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    repos = [r async for r in provider.enumerate_repos()]
    assert repos == []


# --- Test 6: enumerate_repos raises on 401 ---
@pytest.mark.asyncio
async def test_enumerate_repos_401_raises(provider):
    resp = _make_response(401)
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    with pytest.raises(RuntimeError, match="authentication failed"):
        async for _ in provider.enumerate_repos():
            pass


# --- Test 7: enumerate_repos raises on 500 ---
@pytest.mark.asyncio
async def test_enumerate_repos_500_raises(provider):
    resp = _make_response(500)
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    with pytest.raises(RuntimeError, match="API error 500"):
        async for _ in provider.enumerate_repos():
            pass


# --- Test 8: enumerate_documents yields DocumentDescriptors ---
@pytest.mark.asyncio
async def test_enumerate_documents_success(provider):
    tree_resp = _make_response(200, {
        "sha": "abc123",
        "tree": [
            {"path": "memory/README.md", "type": "blob", "sha": "sha_readme"},
            {"path": "memory/instructions.md", "type": "blob", "sha": "sha_instr"},
            {"path": "memory/manifest.yaml", "type": "blob", "sha": "sha_manifest"},
            {"path": "memory/sub/deep.yaml", "type": "blob", "sha": "sha_deep"},
            {"path": "other/file.md", "type": "blob", "sha": "sha_other"},
            {"path": "memory/subdir", "type": "tree", "sha": "sha_dir"},
        ],
    }, headers={"ETag": '"etag123"'})

    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=tree_resp)

    repo_desc = RepoDescriptor(
        namespace="default", repo="test-repo",
        provider_name="github", external_id="octocat/test-repo",
    )
    docs = [d async for d in provider.enumerate_documents(repo_desc)]
    assert len(docs) == 3
    paths = {d.path for d in docs}
    assert ".ai/memory/README.md" in paths
    assert ".ai/memory/instructions.md" in paths
    assert ".ai/memory/sub/deep.yaml" in paths
    # manifest.yaml excluded
    assert ".ai/memory/manifest.yaml" not in paths


# --- Test 9: enumerate_documents returns empty on 404 ---
@pytest.mark.asyncio
async def test_enumerate_documents_404(provider):
    resp = _make_response(404)
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    repo_desc = RepoDescriptor(
        namespace="default", repo="test-repo",
        provider_name="github", external_id="octocat/test-repo",
    )
    docs = [d async for d in provider.enumerate_documents(repo_desc)]
    assert docs == []


# --- Test 10: fetch_content decodes blob and computes hash ---
@pytest.mark.asyncio
async def test_fetch_content_success(provider):
    text = "# Hello World\nSome content here."
    content_b64 = base64.b64encode(text.encode()).decode()
    resp = _make_response(200, {"content": content_b64})

    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    repo_desc = RepoDescriptor(
        namespace="default", repo="test-repo",
        provider_name="github", external_id="octocat/test-repo",
    )
    doc_desc = DocumentDescriptor(
        repo=repo_desc, path=".ai/memory/README.md",
        anchor=None, external_id="sha_readme",
    )
    result = await provider.fetch_content(doc_desc)
    assert result.text == text
    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert result.content_hash == expected_hash
    assert result.doc is doc_desc


# --- Test 11: fetch_content raises on non-200 ---
@pytest.mark.asyncio
async def test_fetch_content_error(provider):
    resp = _make_response(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"})
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    repo_desc = RepoDescriptor(
        namespace="default", repo="test-repo",
        provider_name="github", external_id="octocat/test-repo",
    )
    doc_desc = DocumentDescriptor(
        repo=repo_desc, path=".ai/memory/README.md",
        anchor=None, external_id="sha_readme",
    )
    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        await provider.fetch_content(doc_desc)


# --- Test 12: 403 without rate limit raises permissions error ---
@pytest.mark.asyncio
async def test_403_without_rate_limit(provider):
    resp = _make_response(403, headers={})
    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    repo_desc = RepoDescriptor(
        namespace="default", repo="test-repo",
        provider_name="github", external_id="octocat/test-repo",
    )
    doc_desc = DocumentDescriptor(
        repo=repo_desc, path=".ai/memory/README.md",
        anchor=None, external_id="sha_readme",
    )
    with pytest.raises(RuntimeError, match="access denied"):
        await provider.fetch_content(doc_desc)


# --- Test 13: rate limit warning logged when remaining < 100 ---
@pytest.mark.asyncio
async def test_rate_limit_warning_logged(provider, caplog):
    import logging
    manifest_b64 = base64.b64encode(MANIFEST_YAML.encode()).decode()
    resp = _make_response(200, {"content": manifest_b64}, headers={
        "X-RateLimit-Remaining": "50",
        "X-RateLimit-Limit": "5000",
        "X-RateLimit-Reset": "1700000000",
    })

    provider._client = AsyncMock()
    provider._client.get = AsyncMock(return_value=resp)

    with caplog.at_level(logging.WARNING, logger="index"):
        repos = [r async for r in provider.enumerate_repos()]

    assert any("rate limit low" in record.message.lower() for record in caplog.records)


# --- Test 14: cache operations are no-op when pool is None ---
@pytest.mark.asyncio
async def test_cache_noop_without_pool(provider):
    assert provider._pool is None
    result = await provider._get_cached_tree("owner/repo", "main")
    assert result is None
    result = await provider._get_cached_blob("sha123")
    assert result is None
    # These should not raise
    await provider._set_cached_tree("owner/repo", "main", "etag", "sha", {})
    await provider._set_cached_blob("sha123", "text")
