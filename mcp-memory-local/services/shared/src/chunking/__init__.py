"""Markdown chunking with heading-based splitting and stable anchors (§8)."""

from .chunker import chunk_markdown, Chunk

__all__ = ["chunk_markdown", "Chunk"]
