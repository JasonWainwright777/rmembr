# Local AI Memory

A local-first AI memory layer that stores free-text "thoughts" with vector
embeddings in Postgres (pgvector) and exposes them via MCP tools for semantic
search.

## Prerequisites

- Python 3.10+
- Docker Desktop (running)

## Setup

1. **Start the database:**

   ```bash
   cp .env.example .env   # edit credentials if desired
   docker compose up -d
   ```

2. **Install dependencies:**

   ```bash
   pip install -e .
   ```

   Requires [Ollama](https://ollama.com/download) running with the embedding model pulled:

   ```bash
   ollama pull nomic-embed-text
   ```

3. **Configure Claude Desktop:**

   Copy the contents of `claude_desktop_config.example.json` into your Claude
   Desktop MCP config (usually `~/.claude/claude_desktop_config.json`). Update
   the `cwd` path to point to this directory.

## MCP Tools

| Tool | Description |
|------|-------------|
| `add_thought(text, source?, metadata?)` | Store a thought with its embedding |
| `search_thoughts(query, top_k=5)` | Semantic similarity search over stored thoughts |

## Running manually

```bash
python -m src.server
```

The server communicates over stdio (MCP transport).

## Testing

```bash
# Requires the database to be running
python tests/test_manual.py
```

## Teardown

```bash
docker compose down -v   # removes containers and data volume
```
