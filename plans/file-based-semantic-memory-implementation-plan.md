# File-Based Semantic Memory System (Local-First) — Implementation Plan

**Goal:** Prove the “AI memory layer” concept locally using **plain Markdown files** as the source of truth, plus a **lightweight vector index** for semantic search—*before* committing to Postgres/Supabase.

This plan uses:
- **Markdown files** for durable memory (Git-friendly)
- **SQLite + sqlite-vec** for local vector search (tiny, runs anywhere; pre‑v1) citeturn0search0
- **Ollama + nomic-embed-text** for local embeddings citeturn0search1turn0search5
- Optional: **MCP server** so an AI client (Claude Desktop, etc.) can call `add_memory` / `search_memory` citeturn0search2turn0search16

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
- “Promote” capture notes into curated notes without breaking links
- Optional MCP tool layer for AI client integration

---

## 2) Architecture

### Source of truth: files
- `memory/` folder contains Markdown content only
- Git can version the folder if you want (exclude `.index/`)

### Index: SQLite + sqlite-vec
- `.index/memory.sqlite` stores:
  - chunk embeddings
  - chunk text
  - file path + offsets/anchors
  - metadata (json)

**sqlite-vec** provides a `vec0` virtual table for storing/querying vectors, and is designed to be small and portable. It’s marked pre‑v1 (expect breaking changes). citeturn0search0

### Embeddings: Ollama + nomic-embed-text
- `nomic-embed-text` is an embeddings-only model and requires a minimum Ollama version noted on the model page. citeturn0search1
- Ollama provides an embeddings capability and API endpoint. citeturn0search5

### Optional AI integration: MCP
- Expose `add_memory` and `search_memory` as MCP tools.
- Claude Desktop can connect to local MCP servers using the official “connect local servers” docs. citeturn0search2turn0search16

---

## 3) Folder layout (recommended)

```
memory/
  capture/          # quick dumps / inbox
  notes/            # cleaned-up notes
  projects/         # project-specific context
  people/           # people + preferences
  logs/             # dated logs (optional)
  _templates/       # note templates (optional)
  .index/           # local-only index (gitignored)
    memory.sqlite
    manifest.json
```

### File naming conventions
- Capture: `capture/YYYY-MM-DD.md` (append entries)
- Notes: `notes/<topic>.md`
- Projects: `projects/<project>/<topic>.md`
- People: `people/<name>.md`

---

## 4) Data model

### 4.1 Memory entry format (Markdown)
Use a lightweight YAML front matter (optional) + body text.

Example:
```md
---
id: 2026-03-04T16:12:00-0600-abc123
tags: [terraform, ado, pipelines]
source: manual
project: terraform-pipeline-utilities
---

Need to standardize unified version tagging across Tier 1 modules...
```

### 4.2 Chunking strategy (MVP)
Start simple:
- Split on blank lines into paragraphs
- Optionally split long paragraphs (>800–1200 chars)
- Store:
  - `chunk_text`
  - `file_path`
  - `chunk_index`
  - `heading_anchor` (optional)
  - `metadata_json`

**Tip:** keep chunks ~200–800 tokens worth of text. Don’t overthink it for MVP.

---

## 5) Implementation phases

## Phase 0 — Pre-flight (30–60 min)
**Deliverables**
- [ ] Choose language for the tooling: **Python** (recommended) or Node
- [ ] Install dependencies:
  - [ ] Ollama installed (local)
  - [ ] SQLite available (usually built-in)
  - [ ] A place for a small CLI tool (`tools/memory/`)

Links:
- Ollama download and model page for `nomic-embed-text` citeturn0search1

---

## Phase 1 — Local embeddings (Ollama) (15–30 min)

1) Pull the embedding model:
```bash
ollama pull nomic-embed-text
```

2) Verify embeddings work:
- Ollama embeddings capability docs describe generating embeddings and note that vector length depends on the model. citeturn0search5

**Deliverables**
- [ ] You can generate an embedding for a test string (vector of floats)

---

## Phase 2 — SQLite vector index (sqlite-vec) (1–2 hours)

### 2.1 Add sqlite-vec
- Use `sqlite-vec` as the vector extension. citeturn0search0
- Keep it in `.index/` or as a vendor dependency (platform-specific build artifacts may apply).

> Note: sqlite-vec is pre‑v1; expect breaking changes. citeturn0search0

### 2.2 Create the index schema
SQLite holds:
- A table for chunks + metadata
- A vec0 virtual table for embeddings
- A manifest that tracks file hashes for incremental indexing

**Deliverables**
- [ ] `.index/memory.sqlite` exists
- [ ] You can insert a fake vector row and query top-N

---

## Phase 3 — Build the indexer (files → chunks → embeddings → SQLite) (2–4 hours)

### 3.1 Index command
Implement:
- `memory index`
  - Walks `memory/`
  - Detects changed files (manifest.json stores sha256 or mtime+size)
  - Chunks changed files
  - Embeds each chunk with Ollama
  - Upserts chunks in SQLite

### 3.2 Add command
Implement:
- `memory add "text..." --tags x,y --project ... --source manual`
  - Appends to `memory/capture/YYYY-MM-DD.md`
  - Calls `memory index` for just that file

**Deliverables**
- [ ] Add creates/updates a capture file
- [ ] Index adds chunks to SQLite with embeddings

---

## Phase 4 — Search (semantic recall) (1–2 hours)

Implement:
- `memory search "query..." --k 8`
  - Embeds the query
  - Runs vector search in sqlite-vec
  - Returns:
    - similarity score
    - file path
    - snippet preview (first ~200 chars)
    - optional surrounding context

### Optional: “hybrid” search (fast + good)
For large repos, you can pre-filter using `ripgrep` and then re-rank with embeddings. Many workflows combine ripgrep with fuzzy selection tools like fzf. citeturn0search3turn0search7turn0search11

**Deliverables**
- [ ] Searches return relevant matches even with paraphrasing
- [ ] Outputs are stable and readable

---

## Phase 5 — Optional MCP integration (2–4 hours)

Only do this once CLI add/search feel good.

### 5.1 MCP server tools
Expose:
- `add_memory(text, tags?, project?, source?)`
- `search_memory(query, k?, filters?)`

### 5.2 Claude Desktop connection
Follow “Connect to local MCP servers” docs. citeturn0search2  
Background on MCP as a standard: citeturn0search16

**Deliverables**
- [ ] Claude Desktop sees tools and can call them
- [ ] Results include file paths/snippets

---

## 6) Testing checklist

### Functional
- [ ] Add 10–20 memories across a few topics
- [ ] Search using synonyms (semantic)
- [ ] Verify returned paths/snippets are correct

### Incremental indexing
- [ ] Edit one file: only that file reindexes
- [ ] Delete one file: chunks removed from index

### Robustness
- [ ] Handle empty query gracefully
- [ ] Handle very long entries (chunking)
- [ ] Index survives restart (SQLite persisted)

---

## 7) Operational guidance

### Git strategy (recommended)
- Commit `memory/**` (optional, if you want versioned memories)
- Add `.index/` to `.gitignore` (local index)

### Privacy
- No SaaS required for embeddings or storage if you stay local with Ollama.
- Keep MCP server bound locally unless you explicitly expose it.

---

## 8) Upgrade path to Postgres/pgvector later
Once you like the workflow:
- Replace SQLite index with Postgres + pgvector
- Keep the same file layout and CLI commands
- Only swap the “index backend” module

This keeps your MVP investment reusable.

---

## Appendix A — Reference links
- sqlite-vec (vector search extension; successor to sqlite-vss; pre‑v1) citeturn0search0
- nomic-embed-text (Ollama embedding model) citeturn0search1
- Ollama embeddings capability docs citeturn0search5
- MCP connect local servers docs citeturn0search2
- MCP announcement/overview (standard concept) citeturn0search16
- ripgrep + fzf workflow articles (optional hybrid search ideas) citeturn0search3turn0search7turn0search11
