"""Embedding adapter for Ollama (§7)."""

import os

import httpx


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""
    pass


class EmbeddingServiceUnavailable(EmbeddingError):
    """Raised when the embedding service is unreachable (§7.1)."""
    pass


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings via Ollama. Returns list of float vectors.

    Resilience (§7.1):
    - If Ollama is unreachable, raises EmbeddingServiceUnavailable
    - Does not silently return empty results
    """
    ollama_url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            results = []
            # Batch requests to Ollama
            for text in texts:
                resp = await client.post(
                    f"{ollama_url}/api/embed",
                    json={"model": model, "input": text},
                )
                resp.raise_for_status()
                data = resp.json()
                # Ollama returns {"embeddings": [[...]]}
                embeddings = data.get("embeddings", [])
                if embeddings:
                    results.append(embeddings[0])
                else:
                    raise EmbeddingError(f"No embedding returned for text: {text[:50]}...")
            return results
    except httpx.ConnectError as e:
        raise EmbeddingServiceUnavailable(
            f"embedding_service_unavailable: Cannot reach Ollama at {ollama_url}: {e}"
        ) from e
    except httpx.HTTPStatusError as e:
        raise EmbeddingError(f"Ollama returned error: {e.response.status_code}") from e


async def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    results = await embed_texts([query])
    return results[0]
