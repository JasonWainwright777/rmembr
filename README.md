# rmembr

Local-first reference implementation of a **targeted AI memory** system:

- Source of truth: curated repo docs under `/.ai/memory/**` (Markdown)
- Index: Postgres + `pgvector` (HNSW) storing chunk embeddings
- Embeddings: Ollama (default model: `nomic-embed-text`, 768 dims)
- API surface: FastAPI services exposing MCP-style “tools”
- UX: a small Python CLI that talks to the Gateway

Most runnable code lives under `mcp-memory-local/`.

## Repo Layout

- `docs/`: user-facing guides (usage/config/tuning)
- `mcp-memory-local/`: the runnable local Docker stack (gateway/index/standards/postgres/ollama)
- `plans/`, `later/`, `reviews/`, `archive/`: design notes, historical plans, and reviews
- `.ai/memory/`: AI-indexed context for this repo (generated in this change)

## Quick Start (Local Stack)

Prereqs: Docker Desktop, Python 3.11+.

```powershell
cd mcp-memory-local

# optional: create local env file
Copy-Item .env.example .env

docker compose up -d
docker compose exec ollama ollama pull nomic-embed-text

# CLI deps (CLI is intentionally lightweight and not packaged)
python -m pip install httpx

python scripts/mcp-cli.py health
python scripts/mcp-cli.py index-repo sample-repo-a
python scripts/mcp-cli.py search sample-repo-a "terraform module versioning"
python scripts/mcp-cli.py get-bundle sample-repo-a "add an auth feature" --format markdown
```

## Core Docs

- `docs/USAGE.md`
- `docs/CONFIGURATION.md`
- `docs/TUNING.md`

## Memory Pack Convention

A “memory pack” for a repo lives at:

```
<repo>/.ai/memory/
  manifest.yaml
  instructions.md
  *.md
```

The Index service chunks and embeds the markdown, then stores it in Postgres. See `docs/USAGE.md` for the authoring rules and `docs/CONFIGURATION.md` for environment variables.
