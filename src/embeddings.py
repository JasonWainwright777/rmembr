"""Embedding generation using nomic-embed-text via Ollama (768 dims)."""

import httpx

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "nomic-embed-text"
EMBEDDING_DIM = 768


def embed(text: str) -> list[float]:
    """Return a 768-dimensional embedding for the given text."""
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": MODEL_NAME, "prompt": text},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]
