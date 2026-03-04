# Architecture Brief

## Enterprise Targeted AI Memory Strategy

**Generated:** 2026-03-04T17:14:39.215518 UTC\
**Author Role Context:** Enterprise Architecture

------------------------------------------------------------------------

# 1. Executive Summary

The enterprise requires a mechanism for delivering **targeted, governed,
and high-precision contextual knowledge** to AI systems without
requiring full knowledge base ingestion.

Two primary usage scenarios drive this requirement:

1.  **Human-in-the-loop development** -- Developers and architects using
    LLM tooling inside corporate repositories.
2.  **Ephemeral autonomous agents** -- Pipeline-driven AI systems (e.g.,
    Azure DevOps runners) executing tasks with no retained memory
    between runs.

This document proposes a **Repo-Scoped Targeted Memory Architecture**
that keeps memory version-controlled, governed, and quickly retrievable,
while preserving a clean path toward centralized enterprise-scale
indexing.

------------------------------------------------------------------------

# 2. Problem Statement

Current LLM workflows suffer from:

-   Overloading context windows with irrelevant information
-   Lack of deterministic instruction retrieval
-   Inconsistent rule/schema application
-   Ephemeral agents rebuilding knowledge from scratch each run

The enterprise needs:

-   Structured, discoverable AI instructions
-   Repo-scoped rules and schemas
-   Fast retrieval without global ingestion
-   Governance and ownership
-   CI/CD compatibility
-   Clear future path to centralized indexing

------------------------------------------------------------------------

# 3. Architectural Principles

1.  **Files are the Source of Truth**
    -   Memory lives in repositories.
    -   Content is versioned, reviewed, and branchable.
2.  **Separation of Concerns**
    -   Memory Store (Markdown files)
    -   Memory Index (search backend)
3.  **Targeted Retrieval over Bulk Loading**
    -   Retrieve only relevant instructions/rules/schemas.
4.  **Backend Agnostic Indexing**
    -   Retrieval backend must be swappable (lexical → SQLite →
        pgvector).
5.  **Governed Memory Packs**
    -   Each repository defines its AI-facing knowledge explicitly.

------------------------------------------------------------------------

# 4. Proposed Solution: Repo-Scoped Memory Packs

Each repository contains a structured memory directory:

    /.ai/
      memory/
        README.md
        manifest.yaml
        instructions.md
        schemas/
        runbooks/
        adr/
        repo-skills/

## 4.1 manifest.yaml Responsibilities

The manifest defines:

-   Scope (repo/team/domain)
-   Owners and approvers
-   Required memory files
-   Embedding model + version (if vectors are used)
-   Tool compatibility version
-   Classification level (optional)

This ensures deterministic discovery of relevant enterprise knowledge.

------------------------------------------------------------------------

# 5. Retrieval Architecture Options

## Option A -- Files + Lexical/Hybrid Search (Low Friction)

Mechanism: - Ripgrep/BM25 lexical search - Optional embedding rerank

Advantages: - No local DB required - Enterprise-friendly - Works in dev
machines and runners

Tradeoff: - Slightly weaker semantic recall

Best suited for: - Instruction-heavy, schema-driven content

------------------------------------------------------------------------

## Option B -- Portable Vector Index Artifact (Recommended Transitional Model)

Mechanism: - CI builds vector index from memory files - Index artifact
versioned per commit - Devs optionally download - ADO runners
automatically download at job start

Advantages: - Fast semantic retrieval - No persistent local DB
requirement - Ideal for ephemeral environments

Tradeoff: - Requires embedding model/version governance

Recommended near-term architecture.

------------------------------------------------------------------------

## Option C -- Centralized Memory Index Service (Future State)

Mechanism: - Central service indexes approved branches - Retrieval via
authenticated API - Cross-repo semantic queries

Advantages: - Enterprise-grade auditability - Access control -
Multi-repo federation

Tradeoff: - Platform ownership and operational cost

------------------------------------------------------------------------

# 6. Retrieval Strategy Recommendation

Adopt **Hybrid Retrieval as Default**:

1.  Lexical pre-filter (deterministic and fast)
2.  Semantic rerank (precision boost)

This balances correctness, speed, and governance.

------------------------------------------------------------------------

# 7. CI/CD Integration Model

For Option B:

1.  Pipeline step builds index from `/ai/memory`
2.  Embedding model + version recorded in manifest
3.  Index stored as artifact keyed to commit SHA
4.  Agents download artifact at runtime
5.  Retrieval occurs locally within job execution

This eliminates the need to rebuild embeddings during each ephemeral
run.

------------------------------------------------------------------------

# 8. Evolution Path

### Phase 1

-   Memory Packs
-   Lexical search
-   Optional semantic rerank

### Phase 2

-   CI-built vector artifact
-   Standardized embedding contract

### Phase 3

-   Centralized pgvector-backed service
-   Enterprise-wide AI knowledge federation

------------------------------------------------------------------------

# 9. Risk Considerations

  Risk                                  Mitigation
  ------------------------------------- ----------------------------------------
  Embedding model drift                 Lock model + version in manifest
  Governance gaps                       Require code review for memory changes
  Sensitive data leakage                Classification field in manifest
  Over-reliance on semantic retrieval   Hybrid default strategy

------------------------------------------------------------------------

# 10. Decision Recommendation

Adopt **Portable Index Artifact + Hybrid Retrieval** as the strategic
direction.

This:

-   Preserves repository governance
-   Supports ephemeral ADO runners
-   Avoids mandatory SQLite deployment
-   Enables future migration to centralized pgvector infrastructure

------------------------------------------------------------------------

# Appendix A -- Conceptual Diagram (Textual)

    [Repo Memory Files]
            ↓
    [CI Pipeline Index Build]
            ↓
    [Index Artifact]
            ↓
    [Dev Machines]    [ADO Runner Agents]
            ↓                 ↓
       Hybrid Retrieval   Hybrid Retrieval

------------------------------------------------------------------------

# Closing Statement

This architecture enables precise, governed, and performant AI memory
retrieval aligned with enterprise architecture standards while
maintaining long-term flexibility and scalability.
