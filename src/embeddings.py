"""Embedding generation using Sentence-Transformers (all-MiniLM-L6-v2, 384 dims)."""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model = SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    """Return a 384-dimensional embedding for the given text."""
    vector = _model.encode(text, normalize_embeddings=True)
    return vector.tolist()
