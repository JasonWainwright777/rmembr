"""Parse and validate manifest.yaml files (§2)."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ManifestData:
    """Parsed manifest.yaml data."""

    pack_version: int = 1
    scope_repo: str = ""
    scope_namespace: str = "default"
    owners: list[str] = field(default_factory=list)
    required_files: list[str] = field(default_factory=list)
    classification: str = "internal"
    embedding_model: str = "nomic-embed-text"
    embedding_dims: int = 768
    embedding_version: str = "locked"
    references_standards: list[str] = field(default_factory=list)
    allow_repo_overrides: bool = False


def parse_manifest(manifest_path: Path) -> ManifestData:
    """Parse a manifest.yaml file into ManifestData."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    scope = raw.get("scope", {})
    embedding = raw.get("embedding", {})
    references = raw.get("references", {})
    override_policy = raw.get("override_policy", {})

    return ManifestData(
        pack_version=raw.get("pack_version", 1),
        scope_repo=scope.get("repo", ""),
        scope_namespace=scope.get("namespace", "default"),
        owners=raw.get("owners", []),
        required_files=raw.get("required_files", []),
        classification=raw.get("classification", "internal"),
        embedding_model=embedding.get("model", "nomic-embed-text"),
        embedding_dims=embedding.get("dims", 768),
        embedding_version=embedding.get("version", "locked"),
        references_standards=references.get("standards", []),
        allow_repo_overrides=override_policy.get("allow_repo_overrides", False),
    )
