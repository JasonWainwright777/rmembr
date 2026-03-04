"""Ingestion logic: read repos, chunk, embed, upsert (§4.3, §9)."""

import os
from pathlib import Path

import sys
sys.path.insert(0, "/app/shared/src")
from chunking import chunk_markdown, Chunk
from manifest import parse_manifest
from src.embeddings import embed_texts


async def index_repo(pool, repo: str, ref: str = "local") -> dict:
    """Index a single repo's memory pack.

    Content-hash upsert logic (§4.3):
    1. Compute content_hash (SHA-256 of chunk_text)
    2. Check if chunk with same (repo, path, anchor, ref) exists
    3. If content_hash matches -> skip (no-op)
    4. If content_hash differs -> re-embed and upsert
    5. If chunk no longer in source -> delete stale row
    """
    repos_root = Path(os.environ.get("REPOS_ROOT", "/repos"))
    repo_path = repos_root / repo
    memory_path = repo_path / ".ai" / "memory"

    if not memory_path.exists():
        return {"error": f"No .ai/memory directory found in repo '{repo}'"}

    # Parse manifest
    manifest_path = memory_path / "manifest.yaml"
    manifest = parse_manifest(manifest_path)

    # Upsert memory_packs record
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO memory_packs (namespace, repo, pack_version, owners, classification, embedding_model, last_indexed_ref)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            ON CONFLICT (namespace, repo) DO UPDATE SET
                pack_version = EXCLUDED.pack_version,
                owners = EXCLUDED.owners,
                classification = EXCLUDED.classification,
                embedding_model = EXCLUDED.embedding_model,
                last_indexed_ref = EXCLUDED.last_indexed_ref,
                updated_at = now()
            """,
            manifest.scope_namespace,
            repo,
            manifest.pack_version,
            str(manifest.owners).replace("'", '"'),
            manifest.classification,
            manifest.embedding_model,
            ref,
        )

    # Collect all markdown files
    md_files = list(memory_path.rglob("*.md")) + list(memory_path.rglob("*.yaml"))
    # Exclude manifest.yaml itself from chunking
    md_files = [f for f in md_files if f.name != "manifest.yaml"]

    all_chunks: list[Chunk] = []
    for md_file in md_files:
        relative_path = str(md_file.relative_to(repo_path))
        content = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(relative_path, content)
        all_chunks.extend(chunks)

    # Determine which chunks need embedding
    indexed_files = set()
    new_count = 0
    skipped_unchanged = 0
    updated_count = 0
    deleted_count = 0

    async with pool.acquire() as conn:
        # Get existing chunks for this repo+ref
        existing = await conn.fetch(
            "SELECT id, path, anchor, content_hash FROM memory_chunks WHERE repo = $1 AND ref = $2",
            repo, ref,
        )
        existing_map = {(r["path"], r["anchor"]): (r["id"], r["content_hash"]) for r in existing}

        # Track which (path, anchor) pairs are still present
        current_keys = set()

        # Process chunks in batches
        chunks_to_embed: list[tuple[Chunk, bool]] = []  # (chunk, is_new)

        for chunk in all_chunks:
            key = (chunk.path, chunk.anchor)
            current_keys.add(key)
            indexed_files.add(chunk.path)

            if key in existing_map:
                existing_id, existing_hash = existing_map[key]
                if existing_hash == chunk.content_hash:
                    skipped_unchanged += 1
                    continue
                else:
                    chunks_to_embed.append((chunk, False))
            else:
                chunks_to_embed.append((chunk, True))

        # Embed new/changed chunks
        if chunks_to_embed:
            texts = [c.chunk_text for c, _ in chunks_to_embed]
            embeddings = await embed_texts(texts)

            for (chunk, is_new), embedding in zip(chunks_to_embed, embeddings):
                embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                await conn.execute(
                    """
                    INSERT INTO memory_chunks (
                        namespace, source_kind, repo, ref_type, ref,
                        path, anchor, heading, chunk_text, metadata_json,
                        content_hash, embedding_model, embedding_version,
                        embedding, classification
                    ) VALUES (
                        $1, 'repo_memory', $2, 'branch', $3,
                        $4, $5, $6, $7, $8::jsonb,
                        $9, $10, $11,
                        $12::vector, $13
                    )
                    ON CONFLICT (repo, path, anchor, ref) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        heading = EXCLUDED.heading,
                        metadata_json = EXCLUDED.metadata_json,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        embedding_model = EXCLUDED.embedding_model,
                        embedding_version = EXCLUDED.embedding_version,
                        classification = EXCLUDED.classification,
                        updated_at = now()
                    """,
                    manifest.scope_namespace,
                    repo,
                    ref,
                    chunk.path,
                    chunk.anchor,
                    chunk.heading,
                    chunk.chunk_text,
                    "{}",
                    chunk.content_hash,
                    manifest.embedding_model,
                    manifest.embedding_version,
                    embedding_str,
                    manifest.classification,
                )
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

        # Delete stale chunks (§4.3 step 5)
        stale_keys = set(existing_map.keys()) - current_keys
        for path, anchor in stale_keys:
            stale_id = existing_map[(path, anchor)][0]
            await conn.execute("DELETE FROM memory_chunks WHERE id = $1", stale_id)
            deleted_count += 1

    return {
        "repo": repo,
        "ref": ref,
        "indexed_files": len(indexed_files),
        "chunks_new": new_count,
        "chunks_updated": updated_count,
        "skipped_unchanged": skipped_unchanged,
        "chunks_deleted": deleted_count,
        "total_chunks": len(all_chunks),
    }


async def index_all(pool, ref: str = "local") -> dict:
    """Index all repos found under REPOS_ROOT."""
    repos_root = Path(os.environ.get("REPOS_ROOT", "/repos"))
    results = []
    for repo_dir in sorted(repos_root.iterdir()):
        if repo_dir.is_dir() and (repo_dir / ".ai" / "memory").exists():
            result = await index_repo(pool, repo_dir.name, ref)
            results.append(result)
    return {
        "repos_indexed": len(results),
        "results": results,
    }
