"""Shared data types for location providers."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RepoDescriptor:
    namespace: str
    repo: str
    provider_name: str
    external_id: str
    version_ref: Optional[str] = None
    metadata: Optional[dict] = None


@dataclass(frozen=True)
class DocumentDescriptor:
    repo: RepoDescriptor
    path: str
    anchor: Optional[str]
    external_id: str
    version_ref: Optional[str] = None
    content_hash: Optional[str] = None


@dataclass(frozen=True)
class DocumentContent:
    doc: DocumentDescriptor
    text: str
    content_hash: str
    metadata: Optional[dict] = None
