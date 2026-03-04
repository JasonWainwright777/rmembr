"""MCP server exposing add_thought and search_thoughts tools."""

import json
import os

import psycopg
from mcp.server.fastmcp import FastMCP

from .embeddings import embed

mcp = FastMCP("local-ai-memory")


def _get_conn_str() -> str:
    user = os.environ.get("POSTGRES_USER", "memory")
    password = os.environ.get("POSTGRES_PASSWORD", "changeme")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "ai_memory")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@mcp.tool()
def add_thought(text: str, source: str = "", metadata: str = "{}") -> str:
    """Store a thought with its embedding for later semantic search.

    Args:
        text: The thought text to store.
        source: Optional source identifier (e.g. "conversation", "note").
        metadata: Optional JSON string of additional metadata.
    """
    vector = embed(text)
    meta = json.loads(metadata) if metadata else {}

    with psycopg.connect(_get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO thoughts (text, source, metadata, embedding) "
                "VALUES (%s, %s, %s, %s::vector) RETURNING id, created_at",
                (text, source, json.dumps(meta), str(vector)),
            )
            row = cur.fetchone()
        conn.commit()

    return json.dumps({"id": row[0], "created_at": row[1].isoformat()})


@mcp.tool()
def search_thoughts(query: str, top_k: int = 5) -> str:
    """Search stored thoughts by semantic similarity.

    Args:
        query: The search query text.
        top_k: Number of results to return (default 5).
    """
    vector = embed(query)

    with psycopg.connect(_get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, text, source, metadata, created_at, "
                "1 - (embedding <=> %s::vector) AS similarity "
                "FROM thoughts "
                "ORDER BY embedding <=> %s::vector "
                "LIMIT %s",
                (str(vector), str(vector), top_k),
            )
            rows = cur.fetchall()

    results = [
        {
            "id": r[0],
            "text": r[1],
            "source": r[2],
            "metadata": r[3],
            "created_at": r[4].isoformat(),
            "similarity": round(float(r[5]), 4),
        }
        for r in rows
    ]
    return json.dumps(results, indent=2)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
