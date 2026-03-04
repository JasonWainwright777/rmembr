# File-Based Semantic Memory System (Local-First) — Implementation Plan

**Goal:** Prove the "AI memory layer" concept locally using **plain Markdown files** as the source of truth, plus a **lightweight vector index** for semantic search—*before* committing to Postgres/Supabase.

This plan uses:
- **Python** with `typer` CLI framework
- **Markdown files** for durable memory (Git-friendly)
- **SQLite + sqlite-vec** for local vector search (768-dim vectors; pre‑v1)
- **Ollama + nomic-embed-text** for local embeddings (768 dimensions)
- Optional: **MCP server** so an AI client (Claude Desktop, etc.) can call `add_memory` / `search_memory`

---

## Locked-in decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | **Python** | Best ecosystem for embeddings, vector search, SQLite; canonical Postgres migration path |
| CLI framework | **typer** | Minimal boilerplate, type hints as CLI args |
| Embedding model | **nomic-embed-text** (768-dim) | Local-only via Ollama, good quality for size |
| Vector dimensions | **768** | Determined by nomic-embed-text |
| Chunk size target | **200–500 tokens** | Balance between context and precision |
| Front-matter parser | **python-frontmatter** | Dead simple YAML front-matter extraction |
| Env management | **uv** | Fast, handles venvs cleanly on Windows |
| sqlite-vec install | **pip: sqlite-vec** | Pure pip, no native build step |

---

## 1) Success criteria

### MVP (must-have)
- Add a memory entry (text + optional tags)
- Store it as a file (Markdown) in a predictable folder structure
- Index it (chunk + embed + store vectors in SQLite)
- Search by meaning (semantic query) and return top matches with file paths + snippets

### V1 (nice-to-have)
- Metadata filters (tags, source, project)
- Incremental indexing (only re-index changed files)
- "Promote" capture notes into curated notes without breaking links
- Hybrid search (ripgrep pre-filter + embedding re-rank)
- Near-duplicate detection on insert (similarity > 0.95 across top-5 → warn)
- Optional MCP tool layer for AI client integration

---

## 2) Architecture

### Source of truth: files
- `memory/` folder contains Markdown content only
- Git can version the folder if you want (exclude `.index/`)

### Index: SQLite + sqlite-vec
- `.index/memory.sqlite` stores:
  - chunk embeddings (768-dim float vectors via `vec0` virtual table)
  - chunk text
  - file path + offsets/anchors
  - file hash (sha256) for change detection — no separate manifest file
  - metadata (json)

**sqlite-vec** provides a `vec0` virtual table for storing/querying vectors. It's pre‑v1 (expect breaking changes).

### Embeddings: Ollama + nomic-embed-text
- `nomic-embed-text` produces **768-dimensional** float vectors
- Ollama serves embeddings via its `/api/embed` HTTP endpoint
- All embedding calls go through a wrapper that checks Ollama health first

### Optional AI integration: MCP
- Expose `add_memory` and `search_memory` as MCP tools
- Claude Desktop can connect to local MCP servers

---

## 3) Folder layout

```
rmembr/
  memory/
    capture/              # quick dumps / inbox (one file per entry)
      2026-03-04/
        161200-abc123.md
        164455-def456.md
    notes/                # cleaned-up notes
    projects/             # project-specific context
    people/               # people + preferences
    logs/                 # dated logs (optional)
    _templates/           # note templates (optional)
  .index/                 # local-only index (gitignored)
    memory.sqlite
  src/
    rmembr/
      __init__.py
      cli.py              # typer app entry point
      chunker.py          # markdown → chunks
      embedder.py         # ollama wrapper
      indexer.py           # file → chunks → embeddings → sqlite
      search.py           # semantic query
      db.py               # sqlite + sqlite-vec schema/operations
      models.py           # dataclasses for Chunk, Memory, SearchResult
  pyproject.toml
```

### File naming conventions
- Capture: `capture/YYYY-MM-DD/HHMMSS-<id>.md` (one entry per file)
  - Example: `memory/capture/2026-03-04/161200-abc123.md`
  - Why: `python-frontmatter` expects one YAML front matter per file; daily append breaks that
- Notes: `notes/<topic>.md`
- Projects: `projects/<project>/<topic>.md`
- People: `people/<name>.md`

---

## 4) Data model

### 4.1 Memory entry format (Markdown)
YAML front matter (parsed with `python-frontmatter`) + body text.

```md
---
id: 2026-03-04T16:12:00-0600-abc123
tags: [terraform, ado, pipelines]
source: manual
project: terraform-pipeline-utilities
---

Need to standardize unified version tagging across Tier 1 modules...
```

### 4.2 SQLite schema

```sql
-- Chunks table (source of truth for indexed content)
CREATE TABLE chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path     TEXT NOT NULL,
    file_hash     TEXT NOT NULL,        -- sha256 of file at index time
    chunk_index   INTEGER NOT NULL,
    chunk_text    TEXT NOT NULL,
    heading       TEXT,                 -- nearest parent heading (context)
    anchor        TEXT,                 -- stable ref: "{heading_slug}-c{chunk_index}"
    project       TEXT,                 -- denormalized from front-matter
    source        TEXT,                 -- denormalized from front-matter
    metadata_json TEXT,                 -- full front-matter as JSON (superset)
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(file_path, chunk_index)
);

CREATE INDEX idx_chunks_project ON chunks(project);
CREATE INDEX idx_chunks_source ON chunks(source);

-- Vector table (sqlite-vec)
CREATE VIRTUAL TABLE chunk_embeddings USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);
```

File change detection uses `file_hash` in the chunks table directly — no separate manifest file. On re-index: compare current file hash to stored hash; if different, delete old chunks for that file and re-chunk/re-embed.

File **deletion** handling: if a file in the index no longer exists on disk, delete its chunks and embeddings.

File **rename** handling: treated as delete + add (new path, new chunks). No attempt to track renames.

### 4.3 Chunking strategy

1. Parse front-matter with `python-frontmatter` (extracted as metadata, not chunked)
2. Split body on `## ` headings as primary boundaries
3. Within each section, split on blank lines into paragraphs
4. If any chunk exceeds ~500 tokens (~2000 chars), split at sentence boundaries
5. Prepend the nearest heading as context prefix to each chunk (e.g., `"## Terraform\n\n<chunk text>"`)
6. Generate a stable anchor per chunk: `"{heading_slug}-c{chunk_index}"` (e.g., `terraform-c0`)
7. Discard chunks that are empty or whitespace-only

Target: **200–500 tokens** per chunk.

> **Note:** Anchors are stable only until the file is re-chunked. Edits that shift chunk boundaries will change anchors. This is acceptable for MVP — content-based stable anchors are V1 territory.

---

## 5) Implementation phases

## Phase 0 — Pre-flight

**Deliverables**
- [ ] Project scaffolded with `uv init` + `pyproject.toml`
- [ ] Dependencies installed:
  - [ ] `typer` (CLI)
  - [ ] `python-frontmatter` (YAML parsing)
  - [ ] `sqlite-vec` (vector search)
  - [ ] `httpx` (Ollama API calls)
- [ ] Ollama installed locally
- [ ] `ollama pull nomic-embed-text` run successfully
- [ ] Folder structure created (`memory/capture/`, `memory/notes/`, etc.)
- [ ] `.gitignore` includes `.index/`

---

## Phase 1 — Ollama embeddings wrapper

1. Implement `embedder.py`:
   - `check_health()` → call `GET http://localhost:11434/api/tags`, raise clear error if Ollama isn't running
   - `embed(text: str) -> list[float]` → call `POST http://localhost:11434/api/embed` with model `nomic-embed-text`, **normalize output vector to unit length** before returning (so dot product ≈ cosine similarity)
   - `embed_batch(texts: list[str]) -> list[list[float]]` → batch variant, also returns unit-normalized vectors
2. Verify: embed a test string, assert vector length == 768, assert `abs(norm(vector) - 1.0) < 1e-6`

**Deliverables**
- [ ] `embedder.py` with health check and embed functions
- [ ] All returned vectors are unit-normalized (dot product ≈ cosine)
- [ ] Clear error message when Ollama is offline: `"Ollama is not running. Start it with: ollama serve"`

---

## Phase 2 — SQLite vector index (sqlite-vec)

### 2.1 Implement `db.py`
- `init_db(path)` → create/open SQLite database, load sqlite-vec extension, create tables if not exist
  - Call `conn.enable_load_extension(True)` before loading sqlite-vec
  - If extension loading fails, raise a clear error: `"Cannot load sqlite-vec extension. Python's bundled sqlite3 may not support extensions. Try: install Python from python.org (not Microsoft Store), or use the 'apsw' package."`
- `upsert_chunks(chunks, embeddings)` → insert chunk rows + vector rows
- `delete_file_chunks(file_path)` → remove chunks + embeddings for a file
- `get_file_hash(file_path)` → return stored hash (or None)
- `search_vectors(query_embedding, k)` → KNN query on vec0 table (dot product on unit-normalized vectors), return chunk IDs + distances
- `get_chunks_by_ids(ids)` → return full chunk data
- **All per-file operations (delete old + insert new) wrapped in a single transaction** to prevent partial index states

### 2.2 Verify
- Insert a fake 768-dim vector, query top-1, confirm it comes back

**Deliverables**
- [ ] `.index/memory.sqlite` created with correct schema
- [ ] Round-trip insert + query works
- [ ] Clear error message if sqlite-vec extension fails to load

---

## Phase 3 — Indexer + Add command

### 3.1 Implement `chunker.py`
- `parse_file(path) -> (metadata, chunks)` using `python-frontmatter` + the chunking strategy from §4.3

### 3.2 Implement `indexer.py`
- `index_all(memory_dir, db)`:
  - Walk `memory/` for `*.md` files
  - For each file: compute sha256, compare to stored hash
  - If changed: delete old chunks, re-chunk, embed, upsert
  - If file deleted from disk: delete orphaned chunks
- `index_file(path, db)`: single-file variant for use after `add`

### 3.3 Implement CLI commands in `cli.py`
- `rmembr index` → run full incremental index
- `rmembr add "text..." --tags x,y --project ... --source manual`
  - Writes a **new file** in `memory/capture/YYYY-MM-DD/HHMMSS-<id>.md` (one entry per file)
  - Generates front-matter with id, tags, source, project
  - Runs `index_file` for that new file
  - If no text argument provided, **reads from stdin** (supports piping)

**Deliverables**
- [ ] `rmembr add` creates a new capture file per entry with proper front-matter
- [ ] `rmembr add` reads from stdin when no text arg: `echo "note" | rmembr add --tags x`
- [ ] `rmembr index` processes all changed files, skips unchanged ones
- [ ] Deleted files have their chunks cleaned up

---

## Phase 4 — Search (semantic recall)

### 4.1 Implement `search.py`
- `search(query, db, embedder, k=8) -> list[SearchResult]`
  - Embed query (unit-normalized)
  - KNN search via sqlite-vec (dot product ≈ cosine on normalized vectors)
  - Return: similarity score, file path, anchor (`file_path#anchor`), heading, snippet (first ~200 chars), metadata

### 4.2 Implement CLI command
- `rmembr search "query..." --k 8`
  - Formatted output: score | file | heading | snippet

### 4.3 Near-duplicate detection (add-time)
- On `rmembr add`, embed the new text and check top-5 similarity (unit-normalized dot product ≈ cosine)
- If any of the top-5 results exceed 0.95 similarity, warn: `"Similar memory already exists in <file>#<anchor>. Add anyway? [y/N]"`

**Deliverables**
- [ ] Searches return relevant matches even with paraphrased queries
- [ ] Duplicate detection warns on near-identical adds
- [ ] Output is clean and readable

---

## Phase 5 — Optional MCP integration

Only do this once CLI add/search feel good.

### 5.1 MCP server tools
Expose:
- `add_memory(text, tags?, project?, source?)`
- `search_memory(query, k?, filters?)`

### 5.2 Claude Desktop connection
- Use the Anthropic MCP Python SDK
- Configure in Claude Desktop's MCP settings

**Deliverables**
- [ ] Claude Desktop sees tools and can call them
- [ ] Results include file paths/snippets

---

## 6) Testing checklist

### Functional
- [ ] Add 10–20 memories across a few topics
- [ ] Search using synonyms (semantic)
- [ ] Verify returned paths/snippets are correct
- [ ] Duplicate detection triggers on near-identical content

### Incremental indexing
- [ ] Edit one file: only that file reindexes
- [ ] Delete one file: chunks removed from index
- [ ] Rename a file: old chunks removed, new chunks added

### Robustness
- [ ] Handle empty query gracefully
- [ ] Handle very long entries (chunking splits correctly)
- [ ] Index survives restart (SQLite persisted)
- [ ] Graceful error when Ollama is not running
- [ ] Graceful error when embedding model not pulled

---

## 7) Operational guidance

### Git strategy (recommended)
- Commit `memory/**` (optional, if you want versioned memories)
- Add `.index/` to `.gitignore` (local index, always rebuildable)

### Privacy
- No SaaS required for embeddings or storage — fully local with Ollama
- Keep MCP server bound to localhost unless you explicitly expose it

---

## 8) Upgrade path to Postgres/pgvector later

Once you like the workflow:
- Replace SQLite index with Postgres + pgvector (`psycopg2` + `pgvector` Python package)
- Keep the same file layout and CLI commands
- Only swap the `db.py` backend module

This keeps your MVP investment reusable.

---

## Appendix A — Python dependencies

```toml
[project]
name = "rmembr"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9",
    "python-frontmatter>=1.0",
    "sqlite-vec>=0.1",
    "httpx>=0.27",
]
```

## Appendix B — Reference links
- sqlite-vec (vector search extension; successor to sqlite-vss; pre‑v1)
- nomic-embed-text (Ollama embedding model, 768-dim)
- Ollama embeddings API (`/api/embed` endpoint)
- MCP Python SDK
- MCP connect local servers docs
