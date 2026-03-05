---
title: rmembr Instructions
priority: must-follow
---

# rmembr Instructions (Repository Context)

## What This Repo Is

This repo contains a runnable local implementation of a “targeted AI memory” system. The key idea is that each code repo maintains a curated `/.ai/memory/**` pack (Markdown) that is chunked, embedded, and indexed for semantic retrieval.

## Where To Look First (Source Of Truth)

- Product behavior and contracts: `mcp-memory-local/services/**/src/*.py`
- How to run locally: `mcp-memory-local/docker-compose.yml`, `mcp-memory-local/.env.example`
- User docs: `docs/USAGE.md`, `docs/CONFIGURATION.md`, `docs/TUNING.md`
- Historical design notes: `plans/`, `later/`, `reviews/`, `archive/` (not always current)

If code and docs disagree, treat the code as the source of truth and update the docs.

## The Runnable Stack (Local)

The runnable system is under `mcp-memory-local/` and includes:

- `gateway` (FastAPI): external entry point that assembles context bundles
- `index` (FastAPI): indexing + semantic search, backed by Postgres/pgvector
- `standards` (FastAPI): serves “enterprise standards” content from a standards repo
- `postgres` (pgvector image): stores `memory_chunks`, `memory_packs`, and `bundle_cache`
- `ollama`: embedding model server

## Indexing This Repo With The Local Stack

By default, the Docker stack only mounts `mcp-memory-local/repos/` into the containers (`/repos`). To index *this* repo (`rmembr`) using the local stack, put a copy (or a symlink, if your environment supports it) under:

`mcp-memory-local/repos/rmembr/`

Then run:

- `python mcp-memory-local/scripts/mcp-cli.py index-repo rmembr`

## Important Implementation Notes (AI Should Know)

## Metadata Is Parsed But Not Fully Used

Markdown YAML front matter is parsed in the chunker, but the current Index ingest path does not persist front matter into `memory_chunks.metadata_json` (it inserts `{}` today). That means fields like `priority: must-follow` are not currently enforced by the running system; treat them as documentation intent.

## How “Must Follow” Works Today

The Gateway prioritizes:

1. Enterprise standards (`source_kind == enterprise_standard`) as `enterprise_must_follow`
2. Everything else as `task_specific` (with a small code-path intended for `repo_must_follow`)

In other words: do not assume repo-level “must follow” prioritization is implemented unless you verify it in code.
