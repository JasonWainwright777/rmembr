"""Markdown chunking implementation (§8).

Rules:
1. Parse YAML front matter (single front matter per file)
2. Split on headings (##, ###)
3. Split long sections into paragraphs
4. Enforce chunk size budgets
"""

import hashlib
import re
from dataclasses import dataclass, field

import yaml


@dataclass
class Chunk:
    """A single chunk of markdown content."""

    path: str
    heading: str
    anchor: str
    chunk_text: str
    content_hash: str
    metadata: dict = field(default_factory=dict)
    chunk_index: int = 0


# Max characters per chunk (roughly ~500 tokens)
MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 100


def _slugify(text: str) -> str:
    """Convert heading text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _compute_hash(text: str) -> str:
    """SHA-256 content hash for upsert logic (§4.3)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_front_matter(content: str) -> tuple[dict, str]:
    """Extract YAML front matter from markdown content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return metadata, body
            except yaml.YAMLError:
                pass
    return {}, content


def _split_on_headings(content: str) -> list[tuple[str, str]]:
    """Split content on ## and ### headings. Returns (heading, body) pairs."""
    sections: list[tuple[str, str]] = []
    # Match ## or ### headings
    pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

    matches = list(pattern.finditer(content))
    if not matches:
        return [("", content.strip())]

    # Content before first heading
    preamble = content[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        sections.append((heading, body))

    return sections


def _split_long_section(heading: str, body: str) -> list[tuple[str, str]]:
    """Split a long section into paragraph-sized chunks."""
    if len(body) <= MAX_CHUNK_CHARS:
        return [(heading, body)]

    paragraphs = re.split(r"\n\n+", body)
    chunks: list[tuple[str, str]] = []
    current = ""

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > MAX_CHUNK_CHARS:
            chunks.append((heading, current.strip()))
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append((heading, current.strip()))

    return chunks


def chunk_markdown(path: str, content: str) -> list[Chunk]:
    """Chunk a markdown file into embedding-ready pieces.

    Returns a list of Chunk objects with stable anchors and content hashes.
    """
    metadata, body = _extract_front_matter(content)
    sections = _split_on_headings(body)

    chunks: list[Chunk] = []
    chunk_index = 0

    for heading, section_body in sections:
        sub_sections = _split_long_section(heading, section_body)
        for sub_heading, sub_body in sub_sections:
            if len(sub_body.strip()) < MIN_CHUNK_CHARS and not sub_heading:
                continue

            slug = _slugify(sub_heading) if sub_heading else "preamble"
            anchor = f"{slug}-c{chunk_index}"

            # Embed text includes heading for context
            embed_text = f"## {sub_heading}\n\n{sub_body}" if sub_heading else sub_body

            chunks.append(
                Chunk(
                    path=path,
                    heading=sub_heading or "(preamble)",
                    anchor=anchor,
                    chunk_text=embed_text,
                    content_hash=_compute_hash(embed_text),
                    metadata=metadata,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

    return chunks
