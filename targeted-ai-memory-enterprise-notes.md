# Targeted AI Memory in Enterprise Repositories

Generated: 2026-03-04T17:12:53.951973 UTC

------------------------------------------------------------------------

## The Core Problem

You are solving for **targeted, governed context** that is:

-   Discoverable quickly
-   Accurate and scoped
-   Usable by both humans and autonomous AI systems
-   Version-controlled and enterprise-safe

Two key scenarios:

1.  **Human-in-the-loop**: Developer/architect using an LLM inside a
    corporate repo.
2.  **Ephemeral autonomous agent**: Fresh ADO runner each step/run with
    no persisted context.

The goal is to allow both to pull the *right* instructions, schemas,
rules, and "skills" without loading the entire knowledge base.

------------------------------------------------------------------------

## Does the Repo-Based Memory Approach Work?

Yes --- with architectural adjustments.

The key shift: treat memory as a **repo-scoped knowledge interface**,
not just personal notes.

Memory must be: - Versioned - Structured - Governed - Quickly
searchable - Portable across ephemeral environments

------------------------------------------------------------------------

## Three Viable Architectural Patterns

### Pattern 1 --- Files + Lexical/Hybrid Search (No SQLite Required)

How it works: - Memory lives under a known path (e.g., `/.ai/memory/`) -
Retrieval uses ripgrep/BM25-style search - Optional embedding-based
reranking on top candidates

Pros: - No local database required - Minimal friction for enterprise
adoption - Works everywhere (dev machines, runners)

Cons: - Weaker semantic recall without reranking

Best for: - Instruction-heavy, schema-driven, rule-based content

------------------------------------------------------------------------

### Pattern 2 --- Portable Index Artifact (Recommended Transitional Model)

How it works: - Markdown memory files remain source of truth - CI
pipeline builds a vector index (e.g., SQLite) as an artifact - Artifact
is downloaded by: - Developers (optional) - ADO runners (automatically)

Pros: - Fast semantic retrieval - No need for SQLite installed
everywhere - Perfect for ephemeral runners

Cons: - Requires index build step in CI - Embedding model/version must
be locked

This is likely the best current balance between governance and speed.

------------------------------------------------------------------------

### Pattern 3 --- Central Memory Index Service (Future State)

How it works: - Memory remains in repos - Central service indexes
approved branches - Retrieval via API with auth/audit

Pros: - Enterprise-ready (audit, access control) - Cross-repo
knowledge - Scalable

Cons: - Requires platform ownership and operational maturity

Likely long-term direction.

------------------------------------------------------------------------

## Recommended Structure: Memory Packs

Example structure:

    /.ai/
      memory/
        README.md
        manifest.yaml
        instructions.md
        schemas/
        runbooks/
        adr/
        repo-skills/

### manifest.yaml should define:

-   Scope (repo/team/domain)
-   Owners/approvers
-   Required memory files
-   Embedding model + version (if vectors used)
-   Compatibility version for tooling

This formalizes how AI retrieves enterprise knowledge.

------------------------------------------------------------------------

## Retrieval Strategy Recommendation

Default to **Hybrid Retrieval**:

1.  Lexical pre-filter (fast, deterministic)
2.  Semantic rerank (precision)

This balances governance, performance, and correctness.

------------------------------------------------------------------------

## Clear Evolution Path

**Now:** - Memory Packs in repo - Lexical search with optional rerank

**Soon:** - CI-built vector index artifact - ADO runners download index

**Later:** - Central index service (pgvector or similar)

This keeps memory in repos while enabling fast and accurate retrieval
for both humans and autonomous systems.

------------------------------------------------------------------------

## Key Architectural Principle

Separate:

-   Memory Store (files in repo)
-   Memory Index (search backend)

Backends can evolve: - Lexical - Local vector (SQLite) - Artifact
vector - Remote vector (Postgres/pgvector)

Switching backends should not require changing memory content structure.

------------------------------------------------------------------------

## Final Recommendation

Adopt Pattern 2 (Portable Index Artifact) with lexical fallback.

This: - Preserves governance - Supports ephemeral ADO runners - Avoids
forcing SQLite on every desktop - Creates a clean migration path to
centralized vector infrastructure
