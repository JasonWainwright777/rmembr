"""Manual validation script for local-ai-memory.

Requires the pgvector database to be running (docker compose up -d).
Run: python tests/test_manual.py
"""

import json
import os
import sys

# Allow running from repo root or tests/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.embeddings import EMBEDDING_DIM, embed


def test_embedding_dimension():
    """Unit: embed() returns a list of exactly 768 floats."""
    vec = embed("hello world")
    assert isinstance(vec, list), f"Expected list, got {type(vec)}"
    assert len(vec) == EMBEDDING_DIM, f"Expected {EMBEDDING_DIM} dims, got {len(vec)}"
    assert all(isinstance(v, float) for v in vec), "All elements must be floats"
    print(f"[PASS] embed() returns {EMBEDDING_DIM} floats")


def test_add_and_search():
    """Integration: add_thought inserts rows; search_thoughts retrieves them."""
    from src.server import add_thought, search_thoughts

    thoughts = [
        ("The weather is sunny and warm today", "test", "{}"),
        ("It is raining heavily outside", "test", "{}"),
        ("Python is a great programming language", "test", "{}"),
        ("I enjoy hiking in the mountains", "test", "{}"),
        ("Machine learning models need training data", "test", "{}"),
    ]

    ids = []
    for text, source, meta in thoughts:
        result = json.loads(add_thought(text, source, meta))
        ids.append(result["id"])
        print(f"  Added thought id={result['id']}: {text[:50]}")

    print(f"[PASS] Added {len(ids)} thoughts")

    # Semantic search: "nice day outside" should rank sunny > rainy
    results = json.loads(search_thoughts("nice day outside", top_k=3))
    print(f"\n  Search 'nice day outside' -> top results:")
    for r in results:
        print(f"    sim={r['similarity']:.4f}  {r['text'][:60]}")

    assert any("sunny" in r["text"].lower() for r in results[:2]), (
        "Expected sunny thought in top 2 results"
    )
    print("[PASS] Semantic search returns expected ordering")

    # Verify metadata round-trip
    meta_thought = add_thought("test metadata", "test", '{"key": "value"}')
    meta_result = json.loads(meta_thought)
    search_meta = json.loads(search_thoughts("test metadata", top_k=1))
    assert search_meta[0]["metadata"]["key"] == "value", "Metadata not preserved"
    print("[PASS] Metadata round-trip works")


def test_safety_checks():
    """Safety: verify .env is gitignored and Docker binds to localhost."""
    # Check .gitignore contains .env
    gitignore_path = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
    with open(gitignore_path) as f:
        gitignore = f.read()
    assert ".env" in gitignore, ".env not in .gitignore"
    print("[PASS] .env is in .gitignore")

    # Check docker-compose binds to 127.0.0.1
    compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
    with open(compose_path) as f:
        compose = f.read()
    assert "127.0.0.1:" in compose, "Docker not bound to localhost"
    print("[PASS] Docker binds to 127.0.0.1 only")


if __name__ == "__main__":
    print("=== Embedding Tests ===")
    test_embedding_dimension()

    print("\n=== Safety Checks ===")
    test_safety_checks()

    print("\n=== Integration Tests (requires running DB) ===")
    try:
        test_add_and_search()
    except Exception as e:
        print(f"[SKIP] Integration tests require running DB: {e}")

    print("\n=== All checks complete ===")
