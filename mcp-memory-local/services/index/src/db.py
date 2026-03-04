"""Database connection pool management."""

import os

import asyncpg


async def create_pool() -> asyncpg.Pool:
    """Create a connection pool to Postgres."""
    return await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "memory"),
        user=os.environ.get("POSTGRES_USER", "memory"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        min_size=2,
        max_size=10,
    )
