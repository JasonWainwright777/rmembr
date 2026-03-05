"""Unit tests for ProviderRegistry."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp-memory-local" / "services" / "index"))

from src.providers.registry import ProviderRegistry


class FakeProvider:
    def __init__(self, provider_name: str):
        self._name = provider_name

    @property
    def name(self) -> str:
        return self._name


@pytest.fixture
def registry():
    reg = ProviderRegistry()
    reg.register(FakeProvider("filesystem"))
    reg.register(FakeProvider("ado"))
    return reg


def test_register_and_get(registry):
    provider = registry.get("filesystem")
    assert provider.name == "filesystem"


def test_get_unknown_raises(registry):
    with pytest.raises(ValueError, match="Unknown provider"):
        registry.get("github")


def test_active_providers_default(registry, monkeypatch):
    monkeypatch.delenv("ACTIVE_PROVIDERS", raising=False)
    active = registry.active_providers()
    assert len(active) == 1
    assert active[0].name == "filesystem"


def test_active_providers_single(registry, monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDERS", "ado")
    active = registry.active_providers()
    assert len(active) == 1
    assert active[0].name == "ado"


def test_active_providers_multiple(registry, monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDERS", "filesystem,ado")
    active = registry.active_providers()
    assert len(active) == 2
    names = [p.name for p in active]
    assert names == ["filesystem", "ado"]


def test_active_providers_unknown_skipped(registry, monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDERS", "filesystem,github")
    active = registry.active_providers()
    assert len(active) == 1
    assert active[0].name == "filesystem"


def test_active_providers_empty_string(registry, monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDERS", "")
    active = registry.active_providers()
    assert len(active) == 0


def test_active_providers_whitespace_handling(registry, monkeypatch):
    monkeypatch.setenv("ACTIVE_PROVIDERS", " filesystem , ado ")
    active = registry.active_providers()
    assert len(active) == 2
