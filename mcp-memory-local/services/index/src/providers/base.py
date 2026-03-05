"""LocationProvider protocol defining the provider contract."""

from typing import Protocol, AsyncIterator

from .types import RepoDescriptor, DocumentDescriptor, DocumentContent


class LocationProvider(Protocol):
    """Contract for pluggable content sources."""

    @property
    def name(self) -> str:
        """Provider identifier (e.g., 'filesystem', 'ado', 'github')."""
        ...

    async def enumerate_repos(self) -> AsyncIterator[RepoDescriptor]:
        """Yield all repos available from this provider."""
        ...

    async def enumerate_documents(
        self, repo: RepoDescriptor
    ) -> AsyncIterator[DocumentDescriptor]:
        """Yield all indexable documents in a repo."""
        ...

    async def fetch_content(
        self, doc: DocumentDescriptor
    ) -> DocumentContent:
        """Fetch full content of a document for chunking."""
        ...
