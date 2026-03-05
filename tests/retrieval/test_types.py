"""Unit tests for retrieval DTOs and serialization."""

import os
import sys
from pathlib import Path

# Add index service to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))

from src.retrieval.types import ScoreComponents, ProvenanceInfo, RetrievalResult, RankingConfig


class TestScoreComponents:
    def test_final_score_semantic_only(self):
        s = ScoreComponents(semantic=0.85)
        assert s.final == 0.85

    def test_final_score_with_boosts(self):
        s = ScoreComponents(semantic=0.8, path_boost=0.1, freshness_boost=0.05)
        assert abs(s.final - 0.95) < 1e-9

    def test_final_score_capped_at_1(self):
        s = ScoreComponents(semantic=0.9, path_boost=0.1, freshness_boost=0.1)
        assert s.final == 1.0

    def test_defaults(self):
        s = ScoreComponents(semantic=0.5)
        assert s.path_boost == 0.0
        assert s.freshness_boost == 0.0

    def test_frozen(self):
        s = ScoreComponents(semantic=0.5)
        try:
            s.semantic = 0.9  # type: ignore
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestProvenanceInfo:
    def test_defaults(self):
        p = ProvenanceInfo()
        assert p.provider_name is None
        assert p.external_id is None
        assert p.content_hash == ""
        assert p.indexed_at is None

    def test_with_values(self):
        p = ProvenanceInfo(
            provider_name="filesystem",
            external_id="fs://repo/doc.md",
            content_hash="abc123",
            indexed_at="2025-01-01T00:00:00+00:00",
        )
        assert p.provider_name == "filesystem"
        assert p.external_id == "fs://repo/doc.md"


class TestRetrievalResult:
    def _make_result(self, **kwargs):
        defaults = {
            "id": 1,
            "path": ".ai/memory/doc.md",
            "anchor": "overview",
            "heading": "Overview",
            "snippet": "Test content",
            "source_kind": "repo_memory",
            "classification": "internal",
            "score": ScoreComponents(semantic=0.85),
            "provenance": ProvenanceInfo(provider_name="filesystem", content_hash="abc"),
        }
        defaults.update(kwargs)
        return RetrievalResult(**defaults)

    def test_to_dict_has_similarity(self):
        r = self._make_result()
        d = r.to_dict()
        assert "similarity" in d
        assert d["similarity"] == 0.85

    def test_to_dict_has_score_components(self):
        r = self._make_result(score=ScoreComponents(semantic=0.8, path_boost=0.1))
        d = r.to_dict()
        assert d["score_components"]["semantic"] == 0.8
        assert d["score_components"]["path_boost"] == 0.1
        assert d["similarity"] == 0.9

    def test_to_dict_has_provenance(self):
        r = self._make_result()
        d = r.to_dict()
        assert d["provenance"]["provider_name"] == "filesystem"
        assert d["provenance"]["content_hash"] == "abc"

    def test_to_dict_backward_compat_fields(self):
        """Ensure all original search.py dict fields are present."""
        r = self._make_result()
        d = r.to_dict()
        for key in ["id", "path", "anchor", "heading", "snippet", "source_kind", "classification", "similarity"]:
            assert key in d, f"Missing backward-compat key: {key}"

    def test_frozen(self):
        r = self._make_result()
        try:
            r.id = 99  # type: ignore
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestRankingConfig:
    def test_defaults(self):
        c = RankingConfig()
        assert c.path_boost_weight == 0.1
        assert c.freshness_boost_weight == 0.0
        assert c.freshness_window_hours == 168

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("RANKING_PATH_BOOST", "0.2")
        monkeypatch.setenv("RANKING_FRESHNESS_BOOST", "0.05")
        monkeypatch.setenv("RANKING_FRESHNESS_WINDOW_HOURS", "72")
        c = RankingConfig.from_env()
        assert c.path_boost_weight == 0.2
        assert c.freshness_boost_weight == 0.05
        assert c.freshness_window_hours == 72

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("RANKING_PATH_BOOST", raising=False)
        monkeypatch.delenv("RANKING_FRESHNESS_BOOST", raising=False)
        monkeypatch.delenv("RANKING_FRESHNESS_WINDOW_HOURS", raising=False)
        c = RankingConfig.from_env()
        assert c.path_boost_weight == 0.1
        assert c.freshness_boost_weight == 0.0
        assert c.freshness_window_hours == 168
