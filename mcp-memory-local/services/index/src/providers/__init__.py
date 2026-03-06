"""Provider package -- pluggable content source abstraction."""

from .base import LocationProvider
from .registry import ProviderRegistry
from .types import RepoDescriptor, DocumentDescriptor, DocumentContent
from .github import GitHubProvider

__all__ = [
    "LocationProvider",
    "ProviderRegistry",
    "RepoDescriptor",
    "DocumentDescriptor",
    "DocumentContent",
    "GitHubProvider",
]
