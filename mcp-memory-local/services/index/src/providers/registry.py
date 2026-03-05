"""ProviderRegistry -- maps provider names to implementations."""

import logging
import os

from .base import LocationProvider

logger = logging.getLogger("index")


class ProviderRegistry:
    """Maps provider names to implementations. Configured via ACTIVE_PROVIDERS env var."""

    def __init__(self):
        self._providers: dict[str, LocationProvider] = {}

    def register(self, provider: LocationProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> LocationProvider:
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        return self._providers[name]

    def active_providers(self) -> list[LocationProvider]:
        """Return providers activated by ACTIVE_PROVIDERS env var."""
        active_names = os.environ.get("ACTIVE_PROVIDERS", "filesystem").split(",")
        result = []
        for n in active_names:
            n = n.strip()
            if not n:
                continue
            if n in self._providers:
                result.append(self._providers[n])
            else:
                logger.warning(f"Unknown provider in ACTIVE_PROVIDERS: {n}")
        return result
