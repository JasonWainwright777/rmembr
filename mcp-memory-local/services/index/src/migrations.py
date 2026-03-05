"""Postgres schema migrations for the Index service (§4.1)."""

import logging

logger = logging.getLogger("index")

MIGRATIONS = [
    # Migration 1: Core tables and indexes
    """
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS memory_packs (
        id              BIGSERIAL PRIMARY KEY,
        namespace       TEXT NOT NULL DEFAULT 'default',
        repo            TEXT NOT NULL,
        pack_version    INT NOT NULL DEFAULT 1,
        owners          JSONB NOT NULL DEFAULT '[]',
        classification  TEXT NOT NULL DEFAULT 'internal',
        embedding_model TEXT NOT NULL DEFAULT 'nomic-embed-text',
        last_indexed_ref TEXT NOT NULL DEFAULT 'local',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (namespace, repo)
    );

    CREATE TABLE IF NOT EXISTS memory_chunks (
        id                  BIGSERIAL PRIMARY KEY,
        namespace           TEXT NOT NULL DEFAULT 'default',
        source_kind         TEXT NOT NULL DEFAULT 'repo_memory',
        repo                TEXT NOT NULL,
        ref_type            TEXT NOT NULL DEFAULT 'branch',
        ref                 TEXT NOT NULL DEFAULT 'local',
        path                TEXT NOT NULL,
        anchor              TEXT NOT NULL,
        heading             TEXT NOT NULL DEFAULT '',
        chunk_text          TEXT NOT NULL,
        metadata_json       JSONB NOT NULL DEFAULT '{}',
        content_hash        TEXT NOT NULL,
        embedding_model     TEXT NOT NULL DEFAULT 'nomic-embed-text',
        embedding_version   TEXT NOT NULL DEFAULT 'locked',
        embedding           vector(768),
        classification      TEXT NOT NULL DEFAULT 'internal',
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS bundle_cache (
        id          BIGSERIAL PRIMARY KEY,
        cache_key   TEXT NOT NULL,
        bundle_json JSONB NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at  TIMESTAMPTZ NOT NULL
    );

    -- HNSW index for vector similarity search
    CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
        ON memory_chunks USING hnsw (embedding vector_cosine_ops);

    -- B-tree index for filtered queries
    CREATE INDEX IF NOT EXISTS idx_chunks_namespace_repo_ref
        ON memory_chunks (namespace, repo, ref);

    -- B-tree index on bundle_cache.cache_key (non-partial; expiry checked at query time)
    CREATE INDEX IF NOT EXISTS idx_bundle_cache_key
        ON bundle_cache (cache_key);

    -- Unique constraint for upsert logic
    CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_repo_path_anchor_ref
        ON memory_chunks (repo, path, anchor, ref);
    """,
    # Migration 2: Provider-agnostic location index columns (Phase 2)
    """
    ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS provider_name VARCHAR;
    ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS external_id VARCHAR;

    CREATE INDEX IF NOT EXISTS idx_chunks_provider_external
        ON memory_chunks (provider_name, external_id);
    """,
]


async def run_migrations(pool) -> None:
    """Run all pending migrations."""
    async with pool.acquire() as conn:
        for i, migration in enumerate(MIGRATIONS):
            logger.info(f"Running migration {i + 1}/{len(MIGRATIONS)}")
            await conn.execute(migration)
    logger.info("All migrations complete")
