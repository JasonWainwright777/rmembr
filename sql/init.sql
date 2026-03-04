CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS thoughts (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    source        TEXT,
    text          TEXT NOT NULL,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(768) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_thoughts_embedding
    ON thoughts USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
