---
title: Repo Layout
---

# Repo Layout (rmembr)

## Top-Level Folders

## `mcp-memory-local/`

Runnable local stack with Docker Compose and 3 FastAPI services:

- `docker-compose.yml`: Postgres + Ollama + gateway/index/standards
- `services/gateway/src/server.py`: bundle assembly + proxy endpoints
- `services/index/src/server.py`: indexing + search endpoints
- `services/standards/src/server.py`: standards endpoints
- `services/shared/src/`: chunking, manifest parsing, validation, auth, structured logging
- `scripts/mcp-cli.py`: small CLI to call the gateway
- `scripts/watch-reindex.py`: file watcher that reindexes on `/.ai/memory/**` changes under `repos/`
- `repos/`: example repos, including `enterprise-standards/` and sample repos

## `docs/`

Living documentation for using/tuning/configuring the local stack:

- `USAGE.md`: quick start + CLI usage + memory pack authoring
- `CONFIGURATION.md`: environment variables, docker-compose layout, DB schema overview
- `TUNING.md`: embedding/chunk/budget/cache and performance tuning knobs

## `plans/`, `later/`, `reviews/`, `archive/`

Design and planning material. Expect some of it to reflect earlier iterations.

