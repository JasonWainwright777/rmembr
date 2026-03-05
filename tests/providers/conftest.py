"""Shared fixtures for provider tests."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

import pytest

# Add shared src to path for manifest/chunking imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "shared" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))

from src.providers.types import RepoDescriptor, DocumentDescriptor, DocumentContent


SAMPLE_MANIFEST = """\
pack_version: 1
scope:
  repo: test-repo
  namespace: default
owners:
  - team-alpha
classification: internal
embedding:
  model: nomic-embed-text
  dims: 768
  version: locked
"""

SAMPLE_MARKDOWN = """\
---
title: Test Document
---

## Overview

This is a test document with enough content to pass the minimum chunk size threshold.
It contains information about testing the provider abstraction layer.

## Details

The details section provides additional content for chunking purposes.
Multiple paragraphs ensure that the chunker has material to work with.
"""


class MockProvider:
    """A mock LocationProvider for contract testing."""

    def __init__(self, repos: Optional[list[RepoDescriptor]] = None, docs: Optional[dict] = None):
        self._repos = repos or []
        self._docs = docs or {}  # repo.repo -> list[DocumentDescriptor]
        self._contents = {}  # doc.external_id -> DocumentContent

    @property
    def name(self) -> str:
        return "mock"

    def add_content(self, doc: DocumentDescriptor, text: str) -> None:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self._contents[doc.external_id] = DocumentContent(
            doc=doc, text=text, content_hash=content_hash
        )

    async def enumerate_repos(self) -> AsyncIterator[RepoDescriptor]:
        for repo in self._repos:
            yield repo

    async def enumerate_documents(
        self, repo: RepoDescriptor
    ) -> AsyncIterator[DocumentDescriptor]:
        for doc in self._docs.get(repo.repo, []):
            yield doc

    async def fetch_content(
        self, doc: DocumentDescriptor
    ) -> DocumentContent:
        if doc.external_id not in self._contents:
            raise FileNotFoundError(f"No content for {doc.external_id}")
        return self._contents[doc.external_id]


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repo with .ai/memory structure."""
    repo_dir = tmp_path / "test-repo"
    memory_dir = repo_dir / ".ai" / "memory"
    memory_dir.mkdir(parents=True)

    manifest_path = memory_dir / "manifest.yaml"
    manifest_path.write_text(SAMPLE_MANIFEST, encoding="utf-8")

    doc_path = memory_dir / "test-doc.md"
    doc_path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    return tmp_path


@pytest.fixture
def mock_repo_descriptor():
    return RepoDescriptor(
        namespace="default",
        repo="mock-repo",
        provider_name="mock",
        external_id="mock://mock-repo",
        metadata={"pack_version": 1, "owners": ["team-alpha"], "classification": "internal",
                  "embedding_model": "nomic-embed-text", "embedding_version": "locked"},
    )


@pytest.fixture
def mock_doc_descriptor(mock_repo_descriptor):
    return DocumentDescriptor(
        repo=mock_repo_descriptor,
        path=".ai/memory/test-doc.md",
        anchor=None,
        external_id="mock://mock-repo/test-doc.md",
    )


@pytest.fixture
def mock_provider(mock_repo_descriptor, mock_doc_descriptor):
    provider = MockProvider(
        repos=[mock_repo_descriptor],
        docs={"mock-repo": [mock_doc_descriptor]},
    )
    provider.add_content(mock_doc_descriptor, SAMPLE_MARKDOWN)
    return provider
