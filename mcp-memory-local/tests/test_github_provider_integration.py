"""Integration tests for GitHubProvider (requires real GITHUB_TOKEN).

These tests are skipped (not failed) when GITHUB_TOKEN is not set.
They hit the real GitHub API, so they require a valid PAT with
Contents: Read-only and Metadata: Read-only permissions.

Set GITHUB_REPOS to a repo that has .ai/memory/manifest.yaml for full coverage.
Note: 403 without rate limit (PAT permissions issue) is not tested here because
integration tests use a valid token by definition.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "index", "src"))

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOS = os.environ.get("GITHUB_REPOS", "")

skip_no_token = pytest.mark.skipif(
    not GITHUB_TOKEN,
    reason="GITHUB_TOKEN not set -- skipping integration tests"
)
skip_no_repos = pytest.mark.skipif(
    not GITHUB_REPOS,
    reason="GITHUB_REPOS not set -- skipping integration tests"
)


@skip_no_token
@skip_no_repos
@pytest.mark.asyncio
class TestGitHubProviderIntegration:
    """Integration tests against real GitHub API."""

    def _make_provider(self):
        from providers.github import GitHubProvider
        return GitHubProvider(pool=None)

    # Test 1: Provider initializes with real token
    async def test_provider_init(self):
        provider = self._make_provider()
        assert provider.name == "github"

    # Test 2: enumerate_repos returns at least one repo
    async def test_enumerate_repos(self):
        provider = self._make_provider()
        repos = [r async for r in provider.enumerate_repos()]
        assert len(repos) >= 1
        repo = repos[0]
        assert repo.provider_name == "github"
        assert "/" in repo.external_id

    # Test 3: enumerate_documents returns documents
    async def test_enumerate_documents(self):
        provider = self._make_provider()
        repos = [r async for r in provider.enumerate_repos()]
        assert len(repos) >= 1
        docs = [d async for d in provider.enumerate_documents(repos[0])]
        assert len(docs) >= 1
        for doc in docs:
            assert doc.path.startswith(".ai/memory/")
            assert doc.external_id  # has a blob SHA

    # Test 4: fetch_content returns valid content with hash
    async def test_fetch_content(self):
        provider = self._make_provider()
        repos = [r async for r in provider.enumerate_repos()]
        assert len(repos) >= 1
        docs = [d async for d in provider.enumerate_documents(repos[0])]
        assert len(docs) >= 1
        content = await provider.fetch_content(docs[0])
        assert content.text
        assert content.content_hash
        assert len(content.content_hash) == 64  # SHA-256 hex

    # Test 5: full round-trip confirms provider_name
    async def test_provider_name_in_descriptors(self):
        provider = self._make_provider()
        repos = [r async for r in provider.enumerate_repos()]
        assert len(repos) >= 1
        assert repos[0].provider_name == "github"
        docs = [d async for d in provider.enumerate_documents(repos[0])]
        if docs:
            assert docs[0].repo.provider_name == "github"
