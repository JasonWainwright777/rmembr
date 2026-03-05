---
title: Memory Pack Authoring Notes
---

# Memory Pack Authoring Notes

This repo’s system expects curated repo context under `/.ai/memory/**` inside each repo being indexed.

## Minimum Pack Layout

```
.ai/memory/
  manifest.yaml
  instructions.md
  *.md
```

## Chunking Rules (Current Implementation)

Implemented in `mcp-memory-local/services/shared/src/chunking/chunker.py`.

- YAML front matter (single `--- ... ---` block at file start) is parsed and removed from the chunk text
- Chunk boundaries start at each `##` / `###` heading
- Long sections are split on blank lines to keep chunks under ~2000 chars
- Very short content (<100 chars) without a heading is dropped
- Anchors are generated as `<slug>-c<index>` (e.g. `terraform-module-versioning-c3`)

## What Gets Indexed

The Index service currently ingests:

- `*.md` under `.ai/memory/**`
- `*.yaml` under `.ai/memory/**`

It explicitly excludes `manifest.yaml` from chunking.

## Writing For Retrieval

- Prefer concrete headings (`## Authentication`, `## Deploy Pipeline`, `## Local Dev`) over long prose
- Keep each section self-contained; assume it may be retrieved alone
- Put “must follow” constraints in a short, explicit section near the top

