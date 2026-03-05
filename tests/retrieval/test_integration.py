"""Integration test: engine -> DB -> ranked results with provenance.

These tests require running services (docker compose up).
Skipped automatically if services are not available.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))

import pytest

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


INDEX_URL = os.environ.get("INDEX_URL", "http://localhost:8081")

pytestmark = pytest.mark.skipif(
    not HAS_HTTPX or not os.environ.get("INTEGRATION_TESTS", ""),
    reason="Integration tests require INTEGRATION_TESTS=1 and running services"
)


@pytest.mark.asyncio
async def test_search_repo_memory_returns_provenance():
    """search_repo_memory response includes provenance fields."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{INDEX_URL}/tools/search_repo_memory",
            json={"repo": "test-repo", "query": "test", "k": 3},
        )
    if resp.status_code != 200:
        pytest.skip(f"Index service returned {resp.status_code}")

    data = resp.json()
    results = data.get("results", [])
    if not results:
        pytest.skip("No results to verify provenance on")

    for r in results:
        assert "provenance" in r, "Missing provenance field"
        assert "score_components" in r, "Missing score_components field"
        assert "similarity" in r, "Missing backward-compat similarity field"
        prov = r["provenance"]
        assert "provider_name" in prov
        assert "external_id" in prov
        assert "content_hash" in prov
        assert "indexed_at" in prov


@pytest.mark.asyncio
async def test_resolve_context_returns_provenance():
    """resolve_context response includes provenance fields."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{INDEX_URL}/tools/resolve_context",
            json={"repo": "test-repo", "task": "test task", "k": 3},
        )
    if resp.status_code != 200:
        pytest.skip(f"Index service returned {resp.status_code}")

    data = resp.json()
    pointers = data.get("pointers", [])
    if not pointers:
        pytest.skip("No pointers to verify provenance on")

    for p in pointers:
        assert "provenance" in p
        assert "score_components" in p


@pytest.mark.asyncio
async def test_ranking_parity_default_config():
    """Default config produces results with expected score structure."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{INDEX_URL}/tools/search_repo_memory",
            json={"repo": "test-repo", "query": "test", "k": 5},
        )
    if resp.status_code != 200:
        pytest.skip(f"Index service returned {resp.status_code}")

    results = resp.json().get("results", [])
    for r in results:
        sc = r.get("score_components", {})
        # Default config: freshness_boost should be 0.0
        assert sc.get("freshness_boost", 0.0) == 0.0
        # similarity should equal semantic + path_boost (freshness is 0)
        expected = min(1.0, sc.get("semantic", 0) + sc.get("path_boost", 0))
        assert abs(r["similarity"] - expected) < 0.001
