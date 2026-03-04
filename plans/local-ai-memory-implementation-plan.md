# Local “AI Memory Layer” (Vector + MCP) — Implementation Plan

**Goal:** Build a *local-first* “memory layer” that any AI client can use for persistent recall (semantic search + optional metadata), mirroring the SaaS-style concept but runnable on a single dev machine for fast experimentation.

This plan is optimized for a **local test** that proves:
1) **Write memory** (capture)
2) **Retrieve memory** (semantic search)
3) **Expose tools to an AI client** via **MCP**

---

## 1) Success criteria

### Must-have (MVP)
- Add a “thought” (free text) into storage
- Generate an embedding for the thought (local or remote)
- Query by meaning (semantic search) and get top-N results
- Tools are callable from an MCP-capable client (e.g., Claude Desktop)

### Nice-to-have (V1)
- Metadata extraction (tags, source, project, timestamps)
- Simple filters (by tag/source/project)
- “Upsert” behavior (avoid duplicates)
- Basic observability (logs + simple health check)

---

## 2) Architecture (local)

### Minimal local architecture
- **Postgres + pgvector** (vector storage + similarity search)
- **Embedding generator** (choose one)
  - Local: **Ollama embedding model** (e.g., `nomic-embed-text`)
  - Local: **Sentence-Transformers** (e.g., `all-MiniLM-L6-v2`, 384 dims)
  - Remote (optional): OpenRouter/OpenAI embeddings
- **Local MCP Server** (Node or Python) exposing:
  - `add_thought(text, metadata?)`
  - `search_thoughts(query, top_k?, filters?)`

**Why this design:** pgvector is simple, cheap, and “close enough” to the Supabase + pgvector approach for local testing. pgvector supports running via Docker images and enabling the `vector` extension in Postgres.  
See: pgvector install + Docker options: https://github.com/pgvector/pgvector  
Example Docker run: https://www.yugabyte.com/blog/postgresql-pgvector-getting-started/  
Supabase local alternative: https://supabase.com/docs/guides/local-development

---

## 3) Technology choices

### 3.1 Vector database: Postgres + pgvector (recommended)
- Pros: simple, local, familiar SQL, easy backup, good enough for MVP
- Cons: less “managed” UX than Supabase; you maintain the container

### 3.2 Embeddings: pick one path

#### Path A — Local embeddings with Ollama (fast to test)
- Use Ollama’s embedding-only model `nomic-embed-text` for local embedding generation.
- Model info + usage: https://ollama.com/library/nomic-embed-text

#### Path B — Local embeddings with Sentence-Transformers (portable)
- Use `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional embeddings)
- Model card: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2  
- SBERT docs: https://sbert.net/

#### Path C — Remote embeddings (only if you want “SaaS-like” behavior)
- Use OpenAI/OpenRouter embeddings for parity with hosted stacks.
- Keep as a later toggle so local testing isn’t blocked on keys/billing.

> **Important:** Your pgvector column dimension must match your embedding model output.  
> Example: `all-MiniLM-L6-v2` → **384 dims**.

### 3.3 MCP client integration
- Claude Desktop supports connecting to local MCP servers and uses a config file location on Windows/macOS.
- MCP docs: build server + connect local servers:
  - https://modelcontextprotocol.io/docs/develop/build-server
  - https://modelcontextprotocol.io/docs/develop/connect-local-servers  
  (Windows config path is documented there.)

Claude Desktop extension guidance (optional): https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop

---

## 4) Implementation phases

### Phase 0 — Pre-flight
**Deliverables**
- Repo folder initialized (e.g., `local-ai-memory/`)
- Docker installed and working
- Node or Python runtime installed

**Checklist**
- [ ] Docker Desktop running
- [ ] `docker version` works
- [ ] Decide MCP server language (Node or Python)
- [ ] Decide embedding path (A, B, or C)

---

### Phase 1 — Stand up Postgres + pgvector (local)

#### 1. Run Postgres with pgvector
**Option 1 (quickest):** run the official `pgvector/pgvector` container image.

PowerShell example:
```powershell
docker pull pgvector/pgvector:pg16

docker run --name pgvector-local `
  -p 5432:5432 `
  -e POSTGRES_PASSWORD=localdevpassword `
  -d pgvector/pgvector:pg16
```

(Reference for the container pattern: https://www.yugabyte.com/blog/postgresql-pgvector-getting-started/)

#### 2. Initialize DB schema
Connect:
```powershell
docker exec -it pgvector-local psql -U postgres
```

Schema (example using 384 dims; adjust if you change models):
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS thoughts (
  id           bigserial PRIMARY KEY,
  created_at   timestamptz NOT NULL DEFAULT now(),
  source       text,
  text         text NOT NULL,
  metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding    vector(384) NOT NULL
);

-- Helpful index for cosine distance queries (adjust ops based on your chosen metric)
-- pgvector supports different index types; start without indexes for MVP, add later when you have enough data.
```

**Deliverables**
- [ ] Container running
- [ ] `vector` extension enabled
- [ ] `thoughts` table created

---

### Phase 2 — Embedding generator

Pick one.

#### Path A: Ollama embedding service (local)
1) Install Ollama and run it
2) Pull the embedding model:
```powershell
ollama pull nomic-embed-text
```

3) Confirm it works (example requests are shown on the model page):  
https://ollama.com/library/nomic-embed-text

**Deliverables**
- [ ] You can call Ollama embeddings locally and get a numeric vector

#### Path B: Sentence-Transformers (local Python)
1) Create venv and install:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install sentence-transformers psycopg[binary]
```

2) Verify embedding dimension is 384 for `all-MiniLM-L6-v2`:
- Model card notes 384-d vectors:
  https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

**Deliverables**
- [ ] You can embed text into a 384-length list/array

---

### Phase 3 — Implement the MCP server (tools)

**Goal:** Provide a stable tool API that AI clients can call:
- `add_thought(text, source?, metadata?)`
- `search_thoughts(query, top_k?, filters?)`

**Implementation notes**
- Use MCP “Build a server” as the baseline structure:
  https://modelcontextprotocol.io/docs/develop/build-server
- Your server will:
  1) accept tool call input
  2) generate embedding for the input text (Phase 2)
  3) insert into Postgres
  4) for search: embed the query and run a similarity query in SQL

**SQL search example (cosine distance):**
```sql
-- given: :query_embedding is vector(384)
SELECT
  id, created_at, source, text, metadata,
  1 - (embedding <=> :query_embedding) AS similarity
FROM thoughts
ORDER BY embedding <=> :query_embedding
LIMIT :top_k;
```

**Deliverables**
- [ ] MCP server can start locally
- [ ] `add_thought` writes to DB
- [ ] `search_thoughts` returns expected hits

---

### Phase 4 — Connect to Claude Desktop (local MCP)

Use the MCP “connect local servers” guide:
https://modelcontextprotocol.io/docs/develop/connect-local-servers

**Windows config location is documented there** (Claude Desktop config file path and JSON format).

**Deliverables**
- [ ] Claude Desktop shows the server connected
- [ ] Tools appear and can be called from chat

---

### Phase 5 — Test plan

#### Functional tests
- [ ] Add 3–5 distinct thoughts
- [ ] Search using synonyms/paraphrases (semantic, not keyword)
- [ ] Verify results order is reasonable
- [ ] Verify metadata is stored and returned

#### Reliability tests
- [ ] Restart DB container; data persists via Docker volume (optional, but recommended)
- [ ] Restart MCP server; reconnect from client
- [ ] Handle empty queries and long text inputs gracefully

#### Safety tests
- [ ] Ensure DB credentials are not logged
- [ ] Ensure MCP tools do not expose arbitrary filesystem by default
- [ ] Verify network binding is local-only unless explicitly exposed

---

## 5) Security & operations (local)

### Secrets management
- Store DB password and any API keys in a local `.env` (gitignored)
- Prefer environment variables over hardcoding

### Data ownership
- Everything is local (Postgres volume)
- Export/backup via `pg_dump` if needed

---

## 6) Milestones (recommended order)

1) **M1: Vector DB online** (pgvector container + schema)
2) **M2: Embeddings online** (Ollama *or* Sentence-Transformers)
3) **M3: MCP tools working** (add/search)
4) **M4: Client integration** (Claude Desktop can call tools)
5) **M5: V1 enhancements** (metadata, filters, indexing)

---

## 7) V1 enhancements (after MVP)

### Add indexing for speed
Once you have enough rows, add an index type supported by pgvector. Start by reviewing pgvector indexing docs:  
https://github.com/pgvector/pgvector

### Add a “capture” UI
- CLI command `memory add "..." --tags ...`
- Optional Slack capture later (requires public URL via tunnel)

### Optional: local Supabase stack
If you want closer parity with the SaaS concept:
- Supabase Local Dev: https://supabase.com/docs/guides/local-development
- Supabase pgvector: https://supabase.com/docs/guides/database/extensions/pgvector

---

## 8) Risks & mitigations

- **Embedding dimension mismatch** → lock the embedding model early; set `vector(N)` accordingly.
- **Client integration complexity** → validate MCP server with a minimal tool first, then add DB + embeddings.
- **Performance tuning too early** → do MVP without indexes; add indexing once you have enough rows.
- **Accidental exposure** → bind services to localhost; don’t open ports unless needed.

---

## 9) What to build next (if MVP feels good)

- Multi-source capture (clipboard, browser highlights, Slack, email)
- “Context packs” (projects) + policy filters
- A small “memory governance” screen (review/edit/delete)
- Multi-model compatibility testing (Claude, ChatGPT, IDE agents)

---

## Appendix A — Quick reference links

- MCP: Build a server: https://modelcontextprotocol.io/docs/develop/build-server  
- MCP: Connect local servers (Claude Desktop config paths): https://modelcontextprotocol.io/docs/develop/connect-local-servers  
- Claude Desktop MCP help: https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop  
- pgvector: https://github.com/pgvector/pgvector  
- pgvector Docker run example: https://www.yugabyte.com/blog/postgresql-pgvector-getting-started/  
- Supabase local dev: https://supabase.com/docs/guides/local-development  
- Ollama embeddings model: https://ollama.com/library/nomic-embed-text  
- all-MiniLM-L6-v2 model card: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2  
- Sentence-Transformers docs: https://sbert.net/
