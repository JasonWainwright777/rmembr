# RMEMBR_v3 — Execution Plan: Local AI Memory Layer (Vector + MCP)

governance_constitution_version: AI Company Constitution v0.4
governance_providers_version: 1.3

**Cycle:** RMEMBR_v3
**Mode:** FULL
**Source proposal:** governance/proposals/RMEMBR-proposal.md
**Prior version:** governance/plans/RMEMBR/RMEMBR_v2.md
**Audit of prior version:** governance/plans/RMEMBR/audits/AUDIT_RMEMBR_v2.md
**Date prepared:** 2026-03-03
**Prepared by:** Builder

---

## Audit Resolution Map

| # | Required Change (from AUDIT_RMEMBR_v2) | How Addressed | Location in v2 |
|---|---|---|---|
| 1 | `governance/NOW.md` CURRENT FOCUS is internally inconsistent (`Phase: RMEMBR_v2` but `Active cycle: RMEMBR_v0`); cycle designation must unambiguously match. | Updated `governance/NOW.md` to change `Active cycle: RMEMBR_v0` to `Active cycle: RMEMBR`. The `Active cycle` field now names the cycle without a version suffix, while the `Phase` field tracks the current plan iteration. This eliminates the inconsistency. | NOW.md CURRENT FOCUS section (line 86) |

---

## Background

The Founder wants a local-first "memory layer" that any MCP-capable AI client
can use for persistent recall via semantic search. The system stores free-text
"thoughts" with embeddings in Postgres (pgvector), and exposes `add_thought` /
`search_thoughts` tools via a local MCP server. This is a greenfield component
in a new directory (`local-ai-memory/`), separate from the governance framework.

---

## Governance Checks

| Check | Answer | Rationale |
|---|---|---|
| 1. Blast Radius | Yes | New Docker service, DB credentials, MCP integration with Claude Desktop |
| 2. Reversibility | Yes | Standalone new component; remove by stopping containers + deleting directory |
| 3. Surface Area | Yes | New DB schema creation |

**Mode: FULL** (checks 1 and 3 are Yes)

---

## Plan (ordered steps)

### Phase 1 — Project scaffold

1. Create `local-ai-memory/` directory at repo root.
2. Initialize with `pyproject.toml` (Python MCP server approach).
3. Add `.env.example` with placeholder DB credentials.
4. Add `.gitignore` entry for `.env` and any venv directories.
5. Create `docker-compose.yml` for pgvector (Postgres 16 + pgvector extension).

### Phase 2 — Database setup

6. Create `local-ai-memory/sql/init.sql` with:
   - `CREATE EXTENSION IF NOT EXISTS vector;`
   - `thoughts` table (id, created_at, source, text, metadata jsonb, embedding vector(384)).
7. Wire `init.sql` into docker-compose as an init script mount.

### Phase 3 — Embedding module

8. Create `local-ai-memory/src/embeddings.py`:
   - Default: Sentence-Transformers `all-MiniLM-L6-v2` (384 dims, local, no API key).
   - Interface: `embed(text: str) -> list[float]`.
   - Model loaded once at import time.

### Phase 4 — MCP server

9. Create `local-ai-memory/src/server.py`:
   - MCP server using the `mcp` Python SDK.
   - Tool: `add_thought(text, source?, metadata?)` — embeds text, inserts into Postgres.
   - Tool: `search_thoughts(query, top_k=5)` — embeds query, cosine similarity search.
10. DB connection via `psycopg` using env vars from `.env`.

### Phase 5 — Integration config

11. Add `local-ai-memory/claude_desktop_config.example.json` showing how to
    register the MCP server in Claude Desktop config.
12. Add `local-ai-memory/README.md` with setup and usage instructions.

### Phase 6 — Validation

13. Manual test script (`local-ai-memory/tests/test_manual.py`):
    - Add 3-5 thoughts.
    - Search by synonym/paraphrase.
    - Verify result ordering and metadata.
14. Safety checks:
    - DB credentials only in `.env` (gitignored).
    - Docker services bound to localhost only.
    - MCP server does not expose filesystem access.

---

## Assumptions

1. Python 3.10+ is available on the dev machine.
2. Docker Desktop is installed and running.
3. Sentence-Transformers is the embedding path (Path B from proposal). No API keys needed.
4. The MCP Python SDK (`mcp`) is available via pip.
5. This is a standalone project directory — no changes to existing CodeFactory code.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Embedding dimension mismatch (model vs DB column) | Medium | Hardcode 384 in both schema and embedding module; validated in test. |
| DB credentials leak via git | High | `.env` in `.gitignore`; only `.env.example` committed. |
| Docker port exposure beyond localhost | Medium | `docker-compose.yml` binds to `127.0.0.1:5432` explicitly. |
| MCP SDK breaking changes | Low | Pin SDK version in `pyproject.toml`. |
| Sentence-Transformers download size (~90MB model) | Low | One-time download; documented in README. |
| Accidental exposure of MCP server to network | Medium | Server binds to localhost; documented in config example. |

---

## Test approach

1. **Unit**: `embed()` returns a list of exactly 384 floats.
2. **Integration**: `add_thought` inserts a row; `search_thoughts` returns it.
3. **Semantic**: Add "The weather is sunny" and "It is raining"; search "nice day outside" returns the sunny thought first.
4. **Safety**: Verify `.env` is gitignored; verify Docker binds to 127.0.0.1 only.

---

## Rollback plan

1. Stop and remove Docker containers: `docker compose down -v`.
2. Delete `local-ai-memory/` directory.
3. Remove MCP server entry from Claude Desktop config (if added).
4. No existing CodeFactory code is modified by this cycle.

---

## Files to create

| # | File | Purpose |
|---|---|---|
| 1 | `local-ai-memory/pyproject.toml` | Project config and dependencies |
| 2 | `local-ai-memory/.env.example` | Credential template |
| 3 | `local-ai-memory/.gitignore` | Exclude .env, venv, __pycache__ |
| 4 | `local-ai-memory/docker-compose.yml` | pgvector Postgres service |
| 5 | `local-ai-memory/sql/init.sql` | DB schema |
| 6 | `local-ai-memory/src/__init__.py` | Package init |
| 7 | `local-ai-memory/src/embeddings.py` | Embedding generation |
| 8 | `local-ai-memory/src/server.py` | MCP server with tools |
| 9 | `local-ai-memory/tests/test_manual.py` | Manual validation script |
| 10 | `local-ai-memory/claude_desktop_config.example.json` | Client config example |
| 11 | `local-ai-memory/README.md` | Setup and usage docs |

---

## Planned outputs

A verification report (closure artifact) will be produced at implementation time containing test results confirming all validation steps pass. The artifact's filename and location will be determined when the implementation phase begins. No governance path is pre-declared for this future file.

---

READY FOR AUDITOR REVIEW
