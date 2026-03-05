# Usage Guide

## Quick Start

```bash
# 1. Start all services
docker compose up -d

# 2. Pull the embedding model
docker compose exec ollama ollama pull nomic-embed-text

# 3. Place a memory pack in repos/<your-repo>/.ai/memory/
#    (see Memory Pack Authoring below)

# 4. Index the repo
python scripts/mcp-cli.py index-repo my-repo

# 5. Search for relevant context
python scripts/mcp-cli.py search my-repo "how do we handle auth?"

# 6. Get a full context bundle for a task
python scripts/mcp-cli.py get-bundle my-repo "implement OAuth login"
```

## CLI Command Reference

All commands use `python scripts/mcp-cli.py <command>`. The CLI connects to the gateway at `GATEWAY_URL` (default `http://localhost:8080`).

### health

Check that all services are running.

```bash
python scripts/mcp-cli.py health
```

### index-repo

Index a single repository's memory pack.

```bash
python scripts/mcp-cli.py index-repo <repo> [--ref local]
```

- `repo` — directory name under `repos/`
- `--ref` — version ref (default: `local`)

Returns counts of new, updated, unchanged, and deleted chunks.

### index-all

Index every repository found under `REPOS_ROOT`.

```bash
python scripts/mcp-cli.py index-all [--ref local]
```

### search

Semantic search across a repo's indexed memory chunks.

```bash
python scripts/mcp-cli.py search <repo> "<query>" [--k 8] [--ref local] [--namespace default]
```

- `repo` — repository to search
- `query` — natural language query (max 2,000 chars)
- `--k` — number of results to return (1-100, default 8)

Each result includes path, heading, snippet, classification, and similarity score.

### get-bundle

Assemble a full context bundle combining repo memory and enterprise standards.

```bash
python scripts/mcp-cli.py get-bundle <repo> "<task>" \
  [--persona human] \
  [--k 12] \
  [--ref local] \
  [--namespace default] \
  [--standards-version local] \
  [--changed-files "src/auth.py,src/login.py"] \
  [--format json]
```

- `--persona` — `human`, `agent`, or `external` (controls classification access)
- `--changed-files` — comma-separated list; chunks matching these paths get a 0.1 similarity boost
- `--format` — `json` (default) or `markdown`

### explain-bundle

Retrieve and explain a previously generated bundle.

```bash
python scripts/mcp-cli.py explain-bundle <bundle_id>
```

The `bundle_id` is returned in the `get-bundle` response. Bundle records are cached for 24 hours.

### list-standards

List available enterprise standards.

```bash
python scripts/mcp-cli.py list-standards [--version local] [--domain enterprise/terraform]
```

- `--domain` — optional prefix filter on standard IDs

### get-standard

Fetch a single enterprise standard by ID.

```bash
python scripts/mcp-cli.py get-standard <standard_id> [--version local] [--format json]
```

Standard IDs use slash-separated paths like `enterprise/ado/pipelines/job-templates-v3`.

### validate-pack

Validate a repo's memory pack by running a test indexing and search cycle.

```bash
python scripts/mcp-cli.py validate-pack <repo> [--ref local]
```

## Memory Pack Authoring

A memory pack lives at `repos/<repo-name>/.ai/memory/` and contains markdown files plus a `manifest.yaml`.

### Directory Layout

```
repos/
  my-repo/
    .ai/
      memory/
        manifest.yaml        # Required: pack metadata
        instructions.md      # General instructions and context
        architecture.md      # Architecture decisions
        patterns.md          # Code patterns and conventions
        onboarding.md        # Team onboarding notes
        ...                  # Any .md files you want indexed
```

All `.md` files in `.ai/memory/` are chunked and indexed. The `manifest.yaml` itself is excluded from chunking.

### manifest.yaml Schema

```yaml
pack_version: 1                    # Schema version (currently 1)

scope:
  repo: my-repo                    # Must match the directory name
  namespace: default               # Logical grouping (default: "default")

owners:                            # Teams responsible for this pack
  - platform-architecture
  - backend-team

required_files:                    # Files that must exist
  - instructions.md

classification: internal           # "public", "internal", or other custom values

embedding:
  model: nomic-embed-text          # Must match EMBED_MODEL
  dims: 768                        # Must match EMBED_DIMS
  version: locked                  # Embedding version tag

references:
  standards:                       # Enterprise standards this repo follows
    - enterprise/ado/pipelines/job-templates-v3
    - enterprise/terraform/module-versioning

override_policy:
  allow_repo_overrides: false      # Reserved for future use
```

### Markdown Authoring Tips

- Use `##` and `###` headings to create logical chunk boundaries
- Each heading starts a new chunk (up to 2,000 characters)
- Chunks under 100 characters without a heading are dropped
- Long sections are split on paragraph boundaries (`\n\n`)
- YAML front matter (between `---` delimiters) is extracted as metadata
- Headings are prepended to chunk text for embedding context

## Standards Versioning

Standards are stored under `repos/<STANDARDS_REPO>/` (default: `enterprise-standards`).

### Directory Convention

```
repos/enterprise-standards/
  local/                     # Local development standards
    enterprise/
      terraform/
        module-versioning.md
  v3/                        # Version 3 standards
    enterprise/
      ado/
        pipelines/
          job-templates-v3.md
  v4/                        # Version 4 standards
    ...
```

- `local` — mutable, for development
- `v3`, `v4` — immutable version snapshots
- Use `--standards-version` or `DEFAULT_STANDARDS_VERSION` to select

Standard IDs are the slash-separated path relative to the version directory: `enterprise/terraform/module-versioning`.

## Persona and Classification

Three personas control what chunks are visible in bundles:

| Persona | Sees Classifications | Use Case |
|---------|---------------------|----------|
| `human` | `public`, `internal` | Developer working in the codebase |
| `agent` | `public`, `internal` | AI coding assistant with repo access |
| `external` | `public` only | External collaborator or public API consumer |

Set the classification in `manifest.yaml` per memory pack. Use `--persona` on `get-bundle` to filter.

## Bundle Workflow

The typical workflow for retrieving context:

```
1. index-repo    Index the memory pack (creates embeddings)
        |
2. search        Find relevant chunks by semantic similarity
        |
3. get-bundle    Assemble a full context bundle:
        |          - Retrieve top-k chunks from index
        |          - Fetch referenced enterprise standards
        |          - Apply persona/classification filtering
        |          - Sort by priority class
        |          - Fit within character budget
        |          - Cache the result
        |
4. explain-bundle  Retrieve and break down a cached bundle
```

### Priority Classes

Chunks in a bundle are sorted by priority:

1. `enterprise_must_follow` — mandatory enterprise standards (highest)
2. `repo_must_follow` — repo-specific requirements
3. `task_specific` — contextually relevant chunks (lowest)

Higher priority chunks are included first when applying the character budget.

## File Watcher for Auto-Reindex

The file watcher monitors `.ai/memory/` directories for changes and triggers reindexing automatically.

```bash
pip install watchdog httpx
python scripts/watch-reindex.py
```

- Watches `REPOS_ROOT` recursively for file changes
- Only reacts to changes under `.ai/memory/` paths
- Debounces events for 3 seconds before triggering reindex
- Calls `index-repo` via the gateway API

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_URL` | `http://localhost:8080` | Gateway endpoint |
| `REPOS_ROOT` | `../repos` (relative to script) | Root directory to watch |

## MCP Client Integration

rmembr exposes all 9 tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) over SSE transport. Any MCP-compatible client can discover and invoke tools directly.

**Setup guides:**

- **VS Code 1.102+:** [docs/integration/vscode-mcp.md](integration/vscode-mcp.md) -- primary supported client
- **Claude Code:** [docs/integration/claude-code-mcp.md](integration/claude-code-mcp.md) -- secondary supported client

**Quick start:** Set `MCP_ENABLED=true` in your `.env`, restart the gateway, and add the appropriate config file for your client. See the integration guides for full details.

**UAT checklist:** [docs/integration/uat-checklist.md](integration/uat-checklist.md) -- manual validation steps for verifying MCP client interoperability.

## Example Workflows

### Human Developer

A developer working on a Terraform module wants to know the team conventions:

```bash
# Index the repo if not done yet
python scripts/mcp-cli.py index-repo infra-modules

# Search for Terraform conventions
python scripts/mcp-cli.py search infra-modules "terraform module versioning rules"

# Get a full bundle for a specific task
python scripts/mcp-cli.py get-bundle infra-modules \
  "add a new terraform module for S3 bucket provisioning" \
  --persona human \
  --standards-version v3 \
  --format markdown
```

### AI Agent with Changed Files

An AI coding assistant receives a PR with changes and needs relevant context:

```bash
# Get context with changed file boosting
python scripts/mcp-cli.py get-bundle my-service \
  "review PR for auth refactor" \
  --persona agent \
  --changed-files "src/auth/handler.py,src/auth/middleware.py" \
  --k 20 \
  --format json
```

Chunks whose `path` matches one of the changed files receive a 0.1 similarity boost, surfacing directly relevant memory higher in the results.
