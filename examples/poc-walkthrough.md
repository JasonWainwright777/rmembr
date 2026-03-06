# rmembr POC Walkthrough

Live examples captured from the running local stack. All requests use the CLI (`scripts/mcp-cli.py`), which calls the Gateway HTTP API under the hood.

---

## 1. Health Check

Verify all services are running and can reach their dependencies.

### CLI

```bash
python scripts/mcp-cli.py health
```

### HTTP Equivalent

```
GET http://localhost:8080/health
```

### Response

```json
{
  "status": "healthy",
  "service": "gateway",
  "index": true,
  "standards": true,
  "postgres": true
}
```

If any dependency is down, its field returns `false` and `status` becomes `"degraded"`.

---

## 2. Index a Single Repo

Chunk, embed, and upsert a repo's `.ai/memory/` pack. The indexer compares content hashes to skip unchanged chunks, re-embeds modified chunks, and deletes stale ones.

### CLI

```bash
python scripts/mcp-cli.py index-repo sample-repo-a
```

### HTTP Equivalent

```
POST http://localhost:8080/proxy/index/index_repo
Content-Type: application/json

{
  "repo": "sample-repo-a",
  "ref": "local"
}
```

### Response

```json
{
  "repo": "sample-repo-a",
  "ref": "local",
  "indexed_files": 2,
  "chunks_new": 0,
  "chunks_updated": 0,
  "skipped_unchanged": 6,
  "chunks_deleted": 0,
  "total_chunks": 6
}
```

**Reading the response:**

| Field | Meaning |
|-------|---------|
| `indexed_files` | Number of `.md`/`.yaml` files found under `.ai/memory/` |
| `chunks_new` | Chunks that didn't exist before — embedded and inserted |
| `chunks_updated` | Chunks where content hash changed — re-embedded and upserted |
| `skipped_unchanged` | Chunks with matching content hash — no work done |
| `chunks_deleted` | Chunks in the DB that no longer exist in source — removed |
| `total_chunks` | Total chunks produced by the current chunking run |

---

## 3. Index All Repos

Index every repo found under `REPOS_ROOT` in a single call. Each repo is processed independently.

### CLI

```bash
python scripts/mcp-cli.py index-all
```

### HTTP Equivalent

```
POST http://localhost:8080/proxy/index/index_all
Content-Type: application/json

{
  "ref": "local"
}
```

### Response

```json
{
  "repos_indexed": 4,
  "results": [
    {
      "repo": "enterprise-standards",
      "ref": "local",
      "indexed_files": 9,
      "chunks_new": 31,
      "chunks_updated": 0,
      "skipped_unchanged": 26,
      "chunks_deleted": 0,
      "total_chunks": 57
    },
    {
      "repo": "rmembr",
      "ref": "local",
      "indexed_files": 10,
      "chunks_new": 0,
      "chunks_updated": 0,
      "skipped_unchanged": 78,
      "chunks_deleted": 0,
      "total_chunks": 78
    },
    {
      "repo": "sample-repo-a",
      "ref": "local",
      "indexed_files": 2,
      "chunks_new": 0,
      "chunks_updated": 0,
      "skipped_unchanged": 6,
      "chunks_deleted": 0,
      "total_chunks": 6
    },
    {
      "repo": "sample-repo-b",
      "ref": "local",
      "indexed_files": 2,
      "chunks_new": 0,
      "chunks_updated": 0,
      "skipped_unchanged": 6,
      "chunks_deleted": 0,
      "total_chunks": 6
    }
  ]
}
```

The local stack ships with 4 repos: `enterprise-standards` (57 chunks across versioned standards), `rmembr` (78 chunks — the system's own memory pack), and two sample repos (6 chunks each).

---

## 4. Semantic Search

Search a repo's indexed chunks by natural language query. Returns the top-k results ranked by cosine similarity.

### CLI

```bash
python scripts/mcp-cli.py search rmembr "how does the chunking pipeline work" --k 5
```

### HTTP Equivalent

```
POST http://localhost:8080/proxy/index/search_repo_memory
Content-Type: application/json

{
  "repo": "rmembr",
  "query": "how does the chunking pipeline work",
  "k": 5,
  "ref": "local",
  "namespace": "default"
}
```

### Response

```json
{
  "results": [
    {
      "id": 75,
      "path": ".ai/memory/memory-pack-authoring.md",
      "anchor": "chunking-rules-current-implementation-c2",
      "heading": "Chunking Rules (Current Implementation)",
      "snippet": "## Chunking Rules (Current Implementation)\n\nImplemented in `mcp-memory-local/services/shared/src/chunking/chunker.py`.\n\n- YAML front matter (single `--- ... ---` block at file start) is parsed and removed from the chunk text\n- Chunk boundaries start at each `##` / `###` heading\n- Long sections are split on blank lines to keep chunks under ~2000 chars\n- Very short content (<100 chars) without a heading is dropped\n- Anchors are generated as `<slug>-c<index>` (e.g. `terraform-module-versioning-c3`)",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.6543
    },
    {
      "id": 64,
      "path": ".ai/memory/data-model.md",
      "anchor": "memorychunks-c2",
      "heading": "`memory_chunks`",
      "snippet": "## `memory_chunks`\n\nStores chunk content and embeddings.\n\nNotable columns:\n\n- identifiers: `repo`, `ref`, `path`, `anchor` (unique with `(repo, path, anchor, ref)`)\n- content: `heading`, `chunk_text`, `content_hash`\n- retrieval: `embedding vector(768)` with HNSW index (cosine ops)\n- access: `classification`\n- provenance (migration 2): `provider_name`, `external_id`\n\nThe Index service returns `similarity = 1 - (embedding <=> query_embedding)`.",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.6121
    },
    {
      "id": 71,
      "path": ".ai/memory/instructions.md",
      "anchor": "metadata-is-parsed-but-not-fully-used-c5",
      "heading": "Metadata Is Parsed But Not Fully Used",
      "snippet": "## Metadata Is Parsed But Not Fully Used\n\nMarkdown YAML front matter is parsed in the chunker, but the current Index ingest path does not persist front matter into `memory_chunks.metadata_json` (it inserts `{}` today). That means fields like `priority: must-follow` are not currently enforced by the running system; treat them as documentation intent.",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.6082
    },
    {
      "id": 126,
      "path": ".ai/memory/system-architecture.md",
      "anchor": "indexing-c11",
      "heading": "Indexing",
      "snippet": "## Indexing\n\n1. User (via CLI) calls Gateway `/proxy/index/index_repo`\n2. Gateway forwards to Index `/tools/index_repo` (with `X-Internal-Token`)\n3. Index reads `repos/<repo>/.ai/memory/**` and chunks content (shared chunker)\n4. Index calls Ollama to embed changed chunks\n5. Index upserts rows to Postgres",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.6064
    },
    {
      "id": 127,
      "path": ".ai/memory/system-architecture.md",
      "anchor": "bundle-assembly-c12",
      "heading": "Bundle Assembly",
      "snippet": "## Bundle Assembly\n\n1. User calls Gateway `/tools/get_context_bundle` with `{repo, task, persona, ...}`\n2. Gateway calls Index `/tools/resolve_context` to get top-k chunk pointers\n3. Gateway calls Standards `/tools/list_standards` + `/tools/get_standard` to fetch up to 5 standards\n4. Gateway filters chunks by persona classification and applies size budget\n5. Gateway returns JSON bundle and a markdown rendering",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.5926
    }
  ],
  "count": 5
}
```

**What to notice:**

- The top result (0.65 similarity) is the exact section describing chunking rules — the query "how does the chunking pipeline work" matched the heading "Chunking Rules (Current Implementation)" directly.
- Lower-ranked results are still relevant: the data model for chunks, metadata parsing notes, and the indexing flow.
- Each result includes `path`, `anchor`, and `heading` — enough for an LLM to cite its source or navigate to the file.

---

## 5. Context Bundle Assembly

The core feature. Assembles a complete context package for a task by combining:
1. **Semantic search results** from the repo's indexed memory
2. **Enterprise standards** referenced by the repo's manifest
3. **Persona-based classification filtering**
4. **Character budget enforcement**

### CLI

```bash
python scripts/mcp-cli.py get-bundle sample-repo-a \
  "add OAuth2 login to the API layer" \
  --persona agent \
  --k 6 \
  --changed-files "src/Api/AuthController.cs,src/Api/Startup.cs" \
  --format json
```

### HTTP Equivalent

```
POST http://localhost:8080/tools/get_context_bundle
Content-Type: application/json

{
  "repo": "sample-repo-a",
  "task": "add OAuth2 login to the API layer",
  "persona": "agent",
  "k": 6,
  "ref": "local",
  "namespace": "default",
  "standards_version": "local",
  "changed_files": ["src/Api/AuthController.cs", "src/Api/Startup.cs"]
}
```

### Response

```json
{
  "bundle_id": "817de76e-19fe-4da0-866c-6cead34d99e4",
  "bundle": {
    "bundle_id": "817de76e-19fe-4da0-866c-6cead34d99e4",
    "repo": "sample-repo-a",
    "task": "add OAuth2 login to the API layer",
    "persona": "agent",
    "ref": "local",
    "namespace": "default",
    "standards_version": "local",
    "standards_content": [
      {
        "id": "enterprise/ado/pipelines/job-templates-v3",
        "version": "local",
        "content": "---\ntitle: ADO Pipeline Job Templates v3\n...\n\n## Approved Templates\n\n### Build Templates\n- `build/dotnet-build.yml` — .NET application builds\n..."
      },
      {
        "id": "enterprise/security/secrets-management",
        "version": "local",
        "content": "---\ntitle: Secrets Management Standard\n...\n\n## Requirements\n\n### Storage\n- Use Azure Key Vault for all secrets\n- Use managed identities for authentication\n..."
      },
      {
        "id": "enterprise/terraform/module-versioning",
        "version": "local",
        "content": "---\ntitle: Terraform Module Versioning Standard\n...\n\n### Pinning Rules\n- Always pin to exact versions in production configurations\n..."
      }
    ],
    "chunks": [
      {
        "id": 29,
        "path": ".ai/memory/instructions.md",
        "anchor": "terraform-modules-c2",
        "heading": "Terraform Modules",
        "snippet": "## Terraform Modules\n\nAll infrastructure is in `infra/`. Modules are pinned to exact versions per enterprise standard. See `enterprise/terraform/module-versioning` for version pinning rules.",
        "source_kind": "repo_memory",
        "classification": "internal",
        "similarity": 0.5463,
        "_priority_class": "task_specific"
      },
      {
        "id": 31,
        "path": ".ai/memory/instructions.md",
        "anchor": "local-development-c4",
        "heading": "Local Development",
        "snippet": "## Local Development\n\n1. Install .NET 8 SDK\n2. Run `dotnet restore`\n3. Set connection string in user secrets\n4. Run `dotnet run --project src/Api`",
        "source_kind": "repo_memory",
        "classification": "internal",
        "similarity": 0.5286,
        "_priority_class": "task_specific"
      },
      {
        "id": 28,
        "path": ".ai/memory/instructions.md",
        "anchor": "branching-strategy-c1",
        "heading": "Branching Strategy",
        "snippet": "## Branching Strategy\n\n- `main` — production-ready code\n- `develop` — integration branch\n- Feature branches: `feature/<ticket-id>-<description>`",
        "source_kind": "repo_memory",
        "classification": "internal",
        "similarity": 0.5054,
        "_priority_class": "task_specific"
      },
      {
        "id": 27,
        "path": ".ai/memory/instructions.md",
        "anchor": "architecture-c0",
        "heading": "Architecture",
        "snippet": "## Architecture\n\nThis repo follows a clean architecture pattern:\n- `src/Api/` — HTTP API layer (controllers, middleware)\n- `src/Domain/` — Business logic and domain entities\n- `src/Infrastructure/` — Data access, external services",
        "source_kind": "repo_memory",
        "classification": "internal",
        "similarity": 0.4901,
        "_priority_class": "task_specific"
      },
      {
        "id": 30,
        "path": ".ai/memory/instructions.md",
        "anchor": "pipeline-configuration-c3",
        "heading": "Pipeline Configuration",
        "snippet": "## Pipeline Configuration\n\nCI/CD uses the enterprise job templates v3. See `enterprise/ado/pipelines/job-templates-v3` for approved templates.",
        "source_kind": "repo_memory",
        "classification": "internal",
        "similarity": 0.4672,
        "_priority_class": "task_specific"
      },
      {
        "id": 32,
        "path": ".ai/memory/README.md",
        "anchor": "tech-stack-c0",
        "heading": "Tech Stack",
        "snippet": "## Tech Stack\n\n- .NET 8 Web API\n- Azure SQL Database\n- Terraform for infrastructure\n- Azure DevOps CI/CD pipelines",
        "source_kind": "repo_memory",
        "classification": "internal",
        "similarity": 0.4557,
        "_priority_class": "task_specific"
      }
    ],
    "total_candidates": 6,
    "filtered_count": 6,
    "returned_count": 6,
    "created_at": "2026-03-06T16:18:54.859868+00:00"
  },
  "cached": false
}
```

**What to notice:**

- **`standards_content`** — The gateway automatically fetched all 3 enterprise standards referenced by sample-repo-a's manifest. These are included as full markdown so the LLM sees the complete standard.
- **`chunks`** — 6 repo-specific chunks sorted by similarity. The "Architecture" chunk (0.49) tells the LLM where `src/Api/` is, which is directly relevant to the OAuth2 task.
- **`changed_files`** — We passed `src/Api/AuthController.cs` and `src/Api/Startup.cs`. Chunks whose `path` matches get a +0.1 similarity boost. In this sample repo none of the memory pack paths match those source files, so the boost didn't change ranking — but for repos with path-specific memory (e.g., a chunk about `src/Api/`), it would surface those chunks higher.
- **`cached: false`** — This was a fresh computation. Subsequent identical requests within the TTL (default 5 min) return `cached: true`.
- **`_priority_class`** — All chunks are `task_specific`. Enterprise standards would appear as `enterprise_must_follow` and are always included first in the character budget.

---

## 6. Explain Bundle

Retrieve the breakdown of a previously assembled bundle. Shows how many candidates were found, what was filtered, and per-chunk details.

### CLI

```bash
python scripts/mcp-cli.py explain-bundle 817de76e-19fe-4da0-866c-6cead34d99e4
```

### HTTP Equivalent

```
POST http://localhost:8080/tools/explain_context_bundle
Content-Type: application/json

{
  "bundle_id": "817de76e-19fe-4da0-866c-6cead34d99e4"
}
```

### Response

```json
{
  "bundle_id": "817de76e-19fe-4da0-866c-6cead34d99e4",
  "repo": "sample-repo-a",
  "task": "add OAuth2 login to the API layer",
  "persona": "agent",
  "total_candidates": 6,
  "after_classification_filter": 6,
  "after_budget_trim": 6,
  "standards_included": [
    "enterprise/ado/pipelines/job-templates-v3",
    "enterprise/security/secrets-management",
    "enterprise/terraform/module-versioning"
  ],
  "priority_breakdown": {
    "task_specific": 6
  },
  "chunks_summary": [
    {
      "path": ".ai/memory/instructions.md",
      "heading": "Terraform Modules",
      "priority": "task_specific",
      "similarity": 0.5463,
      "classification": "internal"
    },
    {
      "path": ".ai/memory/instructions.md",
      "heading": "Local Development",
      "priority": "task_specific",
      "similarity": 0.5286,
      "classification": "internal"
    },
    {
      "path": ".ai/memory/instructions.md",
      "heading": "Branching Strategy",
      "priority": "task_specific",
      "similarity": 0.5054,
      "classification": "internal"
    },
    {
      "path": ".ai/memory/instructions.md",
      "heading": "Architecture",
      "priority": "task_specific",
      "similarity": 0.4901,
      "classification": "internal"
    },
    {
      "path": ".ai/memory/instructions.md",
      "heading": "Pipeline Configuration",
      "priority": "task_specific",
      "similarity": 0.4672,
      "classification": "internal"
    },
    {
      "path": ".ai/memory/README.md",
      "heading": "Tech Stack",
      "priority": "task_specific",
      "similarity": 0.4557,
      "classification": "internal"
    }
  ]
}
```

**What to notice:**

- **`total_candidates: 6`** → **`after_classification_filter: 6`** → **`after_budget_trim: 6`** — No chunks were dropped. The `agent` persona can see `internal` content, and all 6 chunks fit within the 40,000-character budget.
- **`priority_breakdown`** — All 6 chunks are `task_specific`. If enterprise standards were embedded as chunks (rather than fetched separately), they'd appear as `enterprise_must_follow`.
- **`standards_included`** — Lists the 3 standards that were fetched and included in the bundle.

---

## 7. List Enterprise Standards

List all available enterprise standards, optionally filtered by domain prefix.

### CLI

```bash
python scripts/mcp-cli.py list-standards
```

### HTTP Equivalent

```
POST http://localhost:8080/proxy/standards/list_standards
Content-Type: application/json

{
  "version": "local"
}
```

### Response

```json
{
  "standards": [
    {
      "id": "enterprise/ado/pipelines/job-templates-v3",
      "version": "local"
    },
    {
      "id": "enterprise/security/secrets-management",
      "version": "local"
    },
    {
      "id": "enterprise/terraform/module-versioning",
      "version": "local"
    }
  ],
  "count": 3
}
```

### With Domain Filter

```bash
python scripts/mcp-cli.py list-standards --domain enterprise/terraform
```

Returns only standards whose ID starts with `enterprise/terraform`.

---

## 8. Get a Single Standard

Fetch the full content of one enterprise standard by its slash-separated ID.

### CLI

```bash
python scripts/mcp-cli.py get-standard enterprise/terraform/module-versioning
```

### HTTP Equivalent

```
POST http://localhost:8080/proxy/standards/get_standard
Content-Type: application/json

{
  "id": "enterprise/terraform/module-versioning",
  "version": "local"
}
```

### Response

```json
{
  "id": "enterprise/terraform/module-versioning",
  "version": "local",
  "path": "/repos/enterprise-standards/.ai/memory/enterprise/terraform/module-versioning.md",
  "content": "---\ntitle: Terraform Module Versioning Standard\ndomain: terraform\nstandard_id: enterprise/terraform/module-versioning\nversion: v3\nclassification: internal\n---\n\n# Terraform Module Versioning\n\n## Overview\n\nAll Terraform modules must follow semantic versioning (SemVer) and be pinned to specific versions in consuming configurations.\n\n## Requirements\n\n### Version Format\n- Use SemVer: `MAJOR.MINOR.PATCH`\n- Tag releases in the module repository\n- Document breaking changes in CHANGELOG.md\n\n### Pinning Rules\n- Always pin to exact versions in production configurations\n- Use version constraints (`~>`) only in development environments\n- Never use `ref = \"main\"` in module sources\n\n### Module Registry\n- All shared modules must be published to the internal Terraform module registry\n- Module names must follow the pattern: `terraform-<PROVIDER>-<NAME>`\n- Each module must include a `versions.tf` file declaring required provider versions\n\n## Examples\n\n### Correct Usage\n```hcl\nmodule \"network\" {\n  source  = \"app.terraform.io/myorg/network/azurerm\"\n  version = \"3.2.1\"\n}\n```\n\n### Incorrect Usage\n```hcl\nmodule \"network\" {\n  source = \"git::https://dev.azure.com/myorg/modules/network?ref=main\"\n}\n```\n"
}
```

---

## 9. Validate Pack

Runs a test cycle against a repo's indexed memory: verifies that the index has chunks and that search returns results.

### CLI

```bash
python scripts/mcp-cli.py validate-pack rmembr
```

### HTTP Equivalent

```
POST http://localhost:8080/tools/validate_pack
Content-Type: application/json

{
  "repo": "rmembr",
  "ref": "local"
}
```

### Response (Healthy)

```json
{
  "repo": "rmembr",
  "ref": "local",
  "valid": true,
  "issues": []
}
```

### Response (Problem)

```json
{
  "repo": "nonexistent-repo",
  "ref": "local",
  "valid": false,
  "issues": [
    "No .ai/memory directory found in repo 'nonexistent-repo'"
  ]
}
```

---

## 10. Semantic Search Across Repos

The same search tool works across any indexed repo. Here's a search against `sample-repo-a` with a task-oriented query.

### CLI

```bash
python scripts/mcp-cli.py search sample-repo-a "how do we deploy to production" --k 3
```

### HTTP Equivalent

```
POST http://localhost:8080/proxy/index/search_repo_memory
Content-Type: application/json

{
  "repo": "sample-repo-a",
  "query": "how do we deploy to production",
  "k": 3,
  "ref": "local",
  "namespace": "default"
}
```

### Response

```json
{
  "results": [
    {
      "id": 28,
      "path": ".ai/memory/instructions.md",
      "anchor": "branching-strategy-c1",
      "heading": "Branching Strategy",
      "snippet": "## Branching Strategy\n\n- `main` — production-ready code\n- `develop` — integration branch\n- Feature branches: `feature/<ticket-id>-<description>`",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.5462
    },
    {
      "id": 29,
      "path": ".ai/memory/instructions.md",
      "anchor": "terraform-modules-c2",
      "heading": "Terraform Modules",
      "snippet": "## Terraform Modules\n\nAll infrastructure is in `infra/`. Modules are pinned to exact versions per enterprise standard. See `enterprise/terraform/module-versioning` for version pinning rules.",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.5321
    },
    {
      "id": 30,
      "path": ".ai/memory/instructions.md",
      "anchor": "pipeline-configuration-c3",
      "heading": "Pipeline Configuration",
      "snippet": "## Pipeline Configuration\n\nCI/CD uses the enterprise job templates v3. See `enterprise/ado/pipelines/job-templates-v3` for approved templates.",
      "source_kind": "repo_memory",
      "classification": "internal",
      "similarity": 0.4803
    }
  ],
  "count": 3
}
```

**What to notice:**

- The query "how do we deploy to production" surfaced branching strategy (mentions `main` = production-ready), terraform modules (infrastructure), and pipeline configuration (CI/CD) — all deployment-adjacent topics.
- Similarity scores are lower (0.48–0.55) because sample-repo-a's memory pack is small and doesn't have a dedicated deployment section. This is expected — better memory packs produce better retrieval.
