# Generate `.ai/memory` Pack for a Repository

You are analyzing a code repository to produce a **memory pack** — a set of curated markdown files that will be chunked, embedded into a vector database, and retrieved by LLMs at inference time to answer questions about this repository.

## Your Goal

Create the directory `.ai/memory/` at the repository root containing:

1. `manifest.yaml` — pack metadata
2. `instructions.md` — the "start here" file: what this repo is, how to run it, source of truth pointers
3. Additional topic files as needed (e.g., `architecture.md`, `data-model.md`, `api.md`, `configuration.md`, `security.md`, `testing.md`, `operations.md`)

These files are the **only** thing an LLM will know about this repo beyond the user's immediate question. Write them to be maximally useful for an AI that needs to understand, modify, debug, or extend this codebase.

---

## How the Content Will Be Used

The indexing pipeline works as follows:

1. Every `.md` file under `.ai/memory/` is read (except `manifest.yaml`)
2. YAML front matter (`--- ... ---`) is parsed and stripped from chunk text
3. Content is split into chunks at every `##` and `###` heading boundary
4. Sections longer than ~2,000 characters are further split on blank lines
5. Sections shorter than 100 characters without a heading are dropped
6. Each chunk's heading is prepended to its text before embedding
7. Chunks are embedded with a sentence-level model and stored in pgvector
8. At query time, chunks are retrieved by cosine similarity to a natural-language task description

**This means each `##` section may be retrieved independently, without the rest of the file.** Write accordingly.

---

## Step 1 — Explore the Repository

Before writing anything, thoroughly explore the codebase. Look at:

- **Project root**: `README.md`, `package.json` / `pyproject.toml` / `*.csproj` / `go.mod` / `Cargo.toml` / `Makefile` / `docker-compose.yml` / etc.
- **Source code structure**: main entry points, module/package layout, key abstractions
- **Configuration**: environment variables, config files, feature flags
- **Data layer**: database schemas/migrations, ORMs, data models
- **API surface**: routes, controllers, RPC definitions, GraphQL schemas, CLI commands
- **Infrastructure**: Dockerfiles, CI/CD pipelines, IaC (Terraform, Pulumi, CloudFormation)
- **Tests**: test structure, fixtures, how to run them
- **Documentation**: existing docs, ADRs, runbooks, changelogs
- **Security**: auth mechanisms, secrets management, input validation, access control
- **Dependencies**: key libraries and frameworks, version constraints

Do not guess. Read the actual files. If something is ambiguous, note the ambiguity rather than inventing an answer.

---

## Step 2 — Create `manifest.yaml`

```yaml
pack_version: 1

scope:
  repo: <REPO_DIRECTORY_NAME>    # must match the directory name exactly
  namespace: default

owners:
  - <team-or-maintainer-name>    # who maintains this pack

required_files:
  - instructions.md

classification: internal         # "public", "internal", or a custom value

embedding:
  model: nomic-embed-text
  dims: 768
  version: locked

references:
  standards: []                  # list any enterprise standard IDs this repo follows

override_policy:
  allow_repo_overrides: false
```

---

## Step 3 — Create `instructions.md`

This is the highest-priority file. It must answer:

1. **What is this repo?** — One-paragraph summary: purpose, primary users, key technology choices.
2. **Where to look first (source of truth)** — Pointers to the canonical locations for behavior, config, API contracts, and docs. State explicitly: "if code and docs disagree, treat the code as truth."
3. **How to run it locally** — Exact commands. Include prerequisites (runtime versions, env setup, database seeds, etc.).
4. **Things an AI must know** — Gotchas, non-obvious conventions, known gaps between intent and implementation. Be honest about what is incomplete or misleading.

Use a `priority: must-follow` front matter tag:

```markdown
---
title: <Repo Name> Instructions
priority: must-follow
---
```

---

## Step 4 — Create Topic Files

Create **one file per major topic**. Only create files where the repo has meaningful content for that topic. Do not create empty or trivial files — chunks under 100 characters with no heading are dropped by the indexer.

### Recommended topics (use the ones that apply):

| File | Covers |
|------|--------|
| `architecture.md` | Component diagram, service boundaries, key abstractions, request/data flows |
| `data-model.md` | Database tables, schemas, migrations, key constraints, relationships |
| `api.md` | Endpoints/routes, request/response shapes, auth requirements, versioning |
| `configuration.md` | Environment variables (with defaults), config files, feature flags |
| `security.md` | Auth mechanisms, authorization model, input validation, secrets handling |
| `testing.md` | How to run tests, test structure, fixture conventions, coverage expectations |
| `operations.md` | How to deploy, monitor, troubleshoot; runbook-style content |
| `patterns.md` | Code conventions, naming rules, error handling patterns, logging standards |
| `dependencies.md` | Key libraries/frameworks, version constraints, upgrade notes |

You may combine small topics into fewer files or split large topics further — optimize for chunks that are self-contained and retrievable.

---

## Writing Rules (Critical for Retrieval Quality)

### Structure

- **Every section must start with a `##` or `###` heading.** This is where chunk boundaries are created. A file with no `##` headings produces a single large chunk or gets dropped.
- **Use concrete, specific headings.** `## Authentication Middleware` retrieves better than `## Overview`. The heading is prepended to the chunk text before embedding — it is the primary signal for similarity search.
- **Keep each section self-contained.** Assume the section will be retrieved alone, without surrounding context. Do not use "as described above" or "see below" — either repeat the essential fact or omit the reference.
- **Target 200–1,500 characters per section.** Under 100 chars (without a heading) is dropped. Over 2,000 chars is split on blank lines, which may break logical groupings.

### Content

- **Lead with facts, not narrative.** State what the code does, where it lives, and what the constraints are. Skip preamble and filler.
- **Include file paths.** Every claim about behavior should reference the file where that behavior is implemented (e.g., `Implemented in src/auth/middleware.ts`). This lets the LLM navigate to source.
- **Include concrete values.** Default ports, environment variable names, table names, endpoint paths, version numbers. These are the details an LLM needs to generate correct code.
- **Document the non-obvious.** The LLM can read straightforward code. Focus on things that are hard to infer: implicit conventions, historical decisions, known footguns, undocumented dependencies between components.
- **Be honest about gaps.** If something is partially implemented, deprecated, or works differently than the docs suggest, say so explicitly. A memory pack that lies is worse than no memory pack.

### What NOT to write

- Do not duplicate content that is already in the repo's README if the README is accurate and stable. Summarize and point to it instead.
- Do not write tutorials or onboarding guides — write reference material.
- Do not include large code samples, logs, or data examples. The chunk budget is small.
- Do not write aspirational content about planned features. Document what exists today.
- Do not add comments like `<!-- TODO -->` or `<!-- FIXME -->` — these waste chunk space.

---

## Step 5 — Create a `README.md` (Index File)

Create `.ai/memory/README.md` as a lightweight table of contents:

```markdown
---
title: <Repo Name> Memory Pack
---

# <Repo Name>: AI-Indexed Notes

## Start Here

- [instructions.md](instructions.md): what this repo is, source of truth, how to run it

## Reference

- [architecture.md](architecture.md): components and data flows
- [api.md](api.md): endpoint contracts
- ...
```

This file is also chunked and indexed — keep it short. Its purpose is to help the LLM understand what files exist and where to look.

---

## Step 6 — Keeping the Index Current

Memory packs are reindexed via the gateway API. The indexer uses content-hash comparison — only chunks whose text actually changed are re-embedded, so reindexing is fast even for large packs.

### CI Pipeline Trigger (Recommended)

Add a path-filtered CI step that triggers on changes to `.ai/memory/**`. This ensures the index stays current whenever a memory pack is updated through a PR merge.

**The CI step should:**

1. Detect changes under `.ai/memory/**` (path filter on the trigger)
2. Call the gateway reindex endpoint:
   ```bash
   curl -X POST http://<GATEWAY_URL>/proxy/index/index_repo \
     -H "Content-Type: application/json" \
     -d '{"repo": "<REPO_DIRECTORY_NAME>"}'
   ```
3. Optionally validate the pack after reindex:
   ```bash
   curl -X POST http://<GATEWAY_URL>/tools/validate_pack \
     -H "Content-Type: application/json" \
     -d '{"repo": "<REPO_DIRECTORY_NAME>"}'
   ```

**Example path filters by CI system:**

- **Azure DevOps**: `trigger: paths: include: ['.ai/memory/*']`
- **GitHub Actions**: `on: push: paths: ['.ai/memory/**']`
- **GitLab CI**: `rules: - changes: ['.ai/memory/**/*']`

### What happens during reindex

- New chunks → embedded and inserted
- Changed chunks (different content hash) → re-embedded and updated
- Unchanged chunks → skipped
- Removed sections → deleted from the index
- Cached bundles expire naturally via TTL (default 5 minutes)

If your repo's CI pipeline is already documented in `operations.md` or `instructions.md`, mention the reindex trigger there so future maintainers know the pack is CI-managed.

---

## Quality Checklist

Before finishing, verify:

- [ ] Every `.md` file has YAML front matter with at least a `title` field
- [ ] Every file has `##` headings — no file is a single wall of text
- [ ] No section exceeds ~1,800 characters (leave margin below the 2,000 char split threshold)
- [ ] No section is under 100 characters without a heading
- [ ] File paths referenced in the memory pack actually exist in the repo
- [ ] Environment variable names and default values match the actual code
- [ ] `manifest.yaml` `scope.repo` matches the actual directory name
- [ ] `instructions.md` exists and has `priority: must-follow` front matter
- [ ] No secrets, credentials, or sensitive values are included
- [ ] Content describes what the code does today, not what it should do

---

## Output

Produce the complete set of files. For each file, show the full path (relative to repo root) and full content. Create only files that contain substantive, retrieval-worthy content for this specific repository.
