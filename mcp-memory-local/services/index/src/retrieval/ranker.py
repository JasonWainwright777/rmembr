"""Ranking pipeline: semantic score, path boost, freshness boost, configurable stage weights."""

from datetime import datetime, timezone, timedelta

from .types import RankingConfig, RetrievalResult, ScoreComponents


class Ranker:
    """Configurable ranking pipeline with discrete stages."""

    def __init__(self, config: RankingConfig):
        self.config = config

    def rank(
        self,
        results: list[RetrievalResult],
        changed_files: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Apply ranking stages and return sorted results."""
        ranked = []
        for r in results:
            path_boost = self._path_boost(r, changed_files)
            freshness_boost = self._freshness_boost(r)
            score = ScoreComponents(
                semantic=r.score.semantic,
                path_boost=path_boost,
                freshness_boost=freshness_boost,
            )
            ranked.append(RetrievalResult(
                id=r.id, path=r.path, anchor=r.anchor, heading=r.heading,
                snippet=r.snippet, source_kind=r.source_kind,
                classification=r.classification, score=score,
                provenance=r.provenance,
            ))
        # Sort by final score descending, then by id ascending for tie-breaking
        ranked.sort(key=lambda r: (-r.score.final, r.id))
        return ranked

    def _path_boost(self, result: RetrievalResult, changed_files: list[str] | None) -> float:
        if not changed_files:
            return 0.0
        for cf in changed_files:
            if cf in result.path:
                return self.config.path_boost_weight
        return 0.0

    def _freshness_boost(self, result: RetrievalResult) -> float:
        if self.config.freshness_boost_weight == 0.0:
            return 0.0
        indexed_at = result.provenance.indexed_at
        if not indexed_at:
            return 0.0
        try:
            ts = datetime.fromisoformat(indexed_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.freshness_window_hours)
            if ts >= cutoff:
                return self.config.freshness_boost_weight
        except (ValueError, TypeError):
            pass
        return 0.0
