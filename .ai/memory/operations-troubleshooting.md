---
title: Operations and Troubleshooting
---

# Operations and Troubleshooting

## Running Locally

```powershell
cd mcp-memory-local
docker compose up -d
docker compose exec ollama ollama pull nomic-embed-text
```

Use the CLI:

```powershell
python -m pip install httpx
python scripts/mcp-cli.py health
```

## Auto-Reindex Watcher

The watcher monitors `mcp-memory-local/repos/**/.ai/memory/**` and reindexes on changes.

```powershell
python -m pip install watchdog httpx
python scripts/watch-reindex.py
```

## Common Failures

## `embedding_service_unavailable` (Index)

Cause: Index cannot reach Ollama at `OLLAMA_URL`.

Checks:

- `docker compose ps` shows `ollama` healthy
- the model is pulled: `docker compose exec ollama ollama pull nomic-embed-text`

## `401 missing X-Internal-Token` / `invalid X-Internal-Token`

Cause: Gateway and internal services do not agree on `INTERNAL_SERVICE_TOKEN`.

Checks:

- `mcp-memory-local/.env` has a non-empty `INTERNAL_SERVICE_TOKEN`
- containers were restarted after changing `.env`: `docker compose up -d --force-recreate`

## `No .ai/memory directory found in repo '<repo>'`

Cause: the repo under `mcp-memory-local/repos/<repo>/` does not have `/.ai/memory/`.

Fix:

- create `mcp-memory-local/repos/<repo>/.ai/memory/manifest.yaml` and `instructions.md`

## “Why didn’t my front matter affect behavior?”

At the moment, front matter is parsed in the chunker but not persisted into `metadata_json` during ingestion. Do not expect `priority:` or other front matter fields to drive bundle assembly unless you verify/extend the implementation.

