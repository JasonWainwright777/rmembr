"""Normalized retrieval types: RetrievalResult, ScoreComponents, ProvenanceInfo, RankingConfig."""

import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class ScoreComponents:
    """Breakdown of how the final score was computed."""
    semantic: float           # Raw cosine similarity (0.0-1.0)
    path_boost: float = 0.0   # Boost from changed_files match
    freshness_boost: float = 0.0  # Boost from recency of update

    @property
    def final(self) -> float:
        return min(1.0, self.semantic + self.path_boost + self.freshness_boost)


@dataclass(frozen=True)
class ProvenanceInfo:
    """Origin tracking for a retrieved chunk."""
    provider_name: Optional[str] = None   # e.g., 'filesystem', 'ado'
    external_id: Optional[str] = None     # Provider-stable ID
    content_hash: str = ""                # SHA-256 of chunk content
    indexed_at: Optional[str] = None      # ISO timestamp of last index


@dataclass(frozen=True)
class RetrievalResult:
    """Normalized chunk returned by the retrieval engine."""
    id: int
    path: str
    anchor: str
    heading: str
    snippet: str                          # chunk_text[:500]
    source_kind: str                      # 'repo_memory' or 'enterprise_standard'
    classification: str                   # 'public', 'internal'
    score: ScoreComponents
    provenance: ProvenanceInfo

    def to_dict(self) -> dict:
        """Serialize to dict for JSON response."""
        d = {
            "id": self.id,
            "path": self.path,
            "anchor": self.anchor,
            "heading": self.heading,
            "snippet": self.snippet,
            "source_kind": self.source_kind,
            "classification": self.classification,
            "similarity": self.score.final,  # Backward compat
            "score_components": asdict(self.score),
            "provenance": asdict(self.provenance),
        }
        return d


@dataclass(frozen=True)
class RankingConfig:
    """Configurable weights for ranking pipeline stages."""
    path_boost_weight: float = 0.1        # Boost for changed_files match
    freshness_boost_weight: float = 0.0   # Boost for recently updated chunks (0 = disabled)
    freshness_window_hours: int = 168     # 7 days -- chunks updated within window get boost

    @classmethod
    def from_env(cls) -> "RankingConfig":
        """Load config from environment variables."""
        return cls(
            path_boost_weight=float(os.environ.get("RANKING_PATH_BOOST", "0.1")),
            freshness_boost_weight=float(os.environ.get("RANKING_FRESHNESS_BOOST", "0.0")),
            freshness_window_hours=int(os.environ.get("RANKING_FRESHNESS_WINDOW_HOURS", "168")),
        )
