"""Unit tests for ranking pipeline stages and configurability."""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))

import pytest

from src.retrieval.types import ScoreComponents, ProvenanceInfo, RetrievalResult, RankingConfig
from src.retrieval.ranker import Ranker


def _make_result(id=1, path=".ai/memory/doc.md", semantic=0.8, provider_name=None, indexed_at=None):
    return RetrievalResult(
        id=id,
        path=path,
        anchor="overview",
        heading="Overview",
        snippet="content",
        source_kind="repo_memory",
        classification="internal",
        score=ScoreComponents(semantic=semantic),
        provenance=ProvenanceInfo(
            provider_name=provider_name,
            content_hash="abc",
            indexed_at=indexed_at,
        ),
    )


class TestPathBoost:
    def test_no_changed_files(self):
        config = RankingConfig(path_boost_weight=0.1)
        ranker = Ranker(config)
        result = _make_result(path="src/foo.md")
        ranked = ranker.rank([result], changed_files=None)
        assert ranked[0].score.path_boost == 0.0

    def test_matching_changed_file(self):
        config = RankingConfig(path_boost_weight=0.1)
        ranker = Ranker(config)
        result = _make_result(path="src/foo.md")
        ranked = ranker.rank([result], changed_files=["src/foo.md"])
        assert ranked[0].score.path_boost == 0.1

    def test_non_matching_changed_file(self):
        config = RankingConfig(path_boost_weight=0.1)
        ranker = Ranker(config)
        result = _make_result(path="src/foo.md")
        ranked = ranker.rank([result], changed_files=["src/bar.md"])
        assert ranked[0].score.path_boost == 0.0

    def test_substring_match(self):
        config = RankingConfig(path_boost_weight=0.15)
        ranker = Ranker(config)
        result = _make_result(path="src/components/foo.md")
        ranked = ranker.rank([result], changed_files=["foo.md"])
        assert ranked[0].score.path_boost == 0.15

    def test_path_boost_affects_ordering(self):
        config = RankingConfig(path_boost_weight=0.1)
        ranker = Ranker(config)
        r1 = _make_result(id=1, path="src/a.md", semantic=0.7)
        r2 = _make_result(id=2, path="src/b.md", semantic=0.75)
        ranked = ranker.rank([r1, r2], changed_files=["src/a.md"])
        # r1 gets 0.7 + 0.1 = 0.8, r2 stays 0.75
        assert ranked[0].id == 1
        assert ranked[1].id == 2


class TestFreshnessBoost:
    def test_disabled_by_default(self):
        config = RankingConfig()  # freshness_boost_weight=0.0
        ranker = Ranker(config)
        now = datetime.now(timezone.utc).isoformat()
        result = _make_result(indexed_at=now)
        ranked = ranker.rank([result])
        assert ranked[0].score.freshness_boost == 0.0

    def test_recent_chunk_gets_boost(self):
        config = RankingConfig(freshness_boost_weight=0.05, freshness_window_hours=168)
        ranker = Ranker(config)
        now = datetime.now(timezone.utc).isoformat()
        result = _make_result(indexed_at=now)
        ranked = ranker.rank([result])
        assert ranked[0].score.freshness_boost == 0.05

    def test_old_chunk_no_boost(self):
        config = RankingConfig(freshness_boost_weight=0.05, freshness_window_hours=168)
        ranker = Ranker(config)
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = _make_result(indexed_at=old)
        ranked = ranker.rank([result])
        assert ranked[0].score.freshness_boost == 0.0

    def test_no_indexed_at_no_boost(self):
        config = RankingConfig(freshness_boost_weight=0.05)
        ranker = Ranker(config)
        result = _make_result(indexed_at=None)
        ranked = ranker.rank([result])
        assert ranked[0].score.freshness_boost == 0.0


class TestRankerOrdering:
    def test_sorts_by_final_score_descending(self):
        config = RankingConfig()
        ranker = Ranker(config)
        r1 = _make_result(id=1, semantic=0.7)
        r2 = _make_result(id=2, semantic=0.9)
        r3 = _make_result(id=3, semantic=0.8)
        ranked = ranker.rank([r1, r2, r3])
        assert [r.id for r in ranked] == [2, 3, 1]

    def test_tie_breaking_by_id(self):
        config = RankingConfig()
        ranker = Ranker(config)
        r1 = _make_result(id=5, semantic=0.8)
        r2 = _make_result(id=2, semantic=0.8)
        r3 = _make_result(id=9, semantic=0.8)
        ranked = ranker.rank([r1, r2, r3])
        assert [r.id for r in ranked] == [2, 5, 9]

    def test_empty_input(self):
        config = RankingConfig()
        ranker = Ranker(config)
        ranked = ranker.rank([])
        assert ranked == []

    def test_default_config_matches_current_behavior(self):
        """Default config with path_boost=0.1 should replicate current resolve_context behavior."""
        config = RankingConfig()  # path_boost_weight=0.1, freshness=0.0
        ranker = Ranker(config)
        r1 = _make_result(id=1, path="src/changed.md", semantic=0.7)
        r2 = _make_result(id=2, path="src/other.md", semantic=0.75)
        ranked = ranker.rank([r1, r2], changed_files=["src/changed.md"])
        # r1: 0.7 + 0.1 = 0.8, r2: 0.75
        assert ranked[0].id == 1
        assert ranked[0].score.final == pytest.approx(0.8)
        assert ranked[1].id == 2
        assert ranked[1].score.final == pytest.approx(0.75)
