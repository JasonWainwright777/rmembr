---
title: Providers
---

# Providers (Filesystem + GitHub)

Primary references:

- `mcp-memory-local/services/index/src/providers/registry.py`
- `mcp-memory-local/services/index/src/providers/filesystem.py`
- `mcp-memory-local/services/index/src/providers/github.py`
- `mcp-memory-local/services/index/src/migrations.py`

## Provider Framework

Index provider selection is controlled by `ACTIVE_PROVIDERS` (comma-separated).

Default active provider is `filesystem`.

GitHub provider is only usable when `GITHUB_TOKEN` is set.

## Filesystem Provider

- discovers repos from local `REPOS_ROOT`
- expects `/.ai/memory/manifest.yaml`
- indexes markdown and yaml files under `.ai/memory/`
- excludes `manifest.yaml` from chunking

## GitHub Provider

- discovers repos from configured `owner/repo` list
- reads `.ai/memory/manifest.yaml` and content via GitHub API
- supports enterprise API base URL override
- indexes `.md` and `.yaml` under `.ai/memory/`, excluding manifest

## GitHub Caching Semantics

Migration 3 introduces `github_cache` table.

Two cache layers:

- tree-level cache using ETag/SHA metadata
- blob-level cache by blob SHA content

Goal is minimizing steady-state API calls during repeat indexing.

## Provenance in Retrieval

Chunks include `provider_name` and `external_id` to preserve source provenance across providers.
