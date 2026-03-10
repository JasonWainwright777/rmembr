# Setting Up rMEMbr on a New Repository

rMEMbr is an MCP server. You do not need to clone the rMEMbr repo or run any scripts from it. Your repo only needs a `.ai/memory/` pack and an MCP client config pointing to the running gateway.

## Prerequisites

- The rMEMbr local stack is running and healthy (gateway reachable on `localhost:8080`)
- Your repo is hosted on GitHub (for the GitHub provider) or accessible locally

## Step 1: Create the Memory Pack

In the root of your repository, create the `.ai/memory/` directory:

```
your-repo/
└── .ai/
    └── memory/
        ├── manifest.yaml        # required — pack metadata
        ├── instructions.md      # required — what this repo is and how to use it
        ├── README.md            # recommended — index of memory files
        └── <topic>.md           # additional memory files by topic
```

### manifest.yaml (Required)

```yaml
pack_version: 1
scope:
  repo: your-repo-name          # must match the GitHub repo name
  namespace: default
owners:
  - your-team-name
required_files:
  - instructions.md
classification: internal        # internal | public | confidential
embedding:
  model: nomic-embed-text
  dims: 768
  version: locked
references:
  standards:                     # optional — enterprise standards to include in bundles
    - enterprise/docker/container-standards
    - enterprise/dotnet/application-standards
override_policy:
  allow_repo_overrides: false
```

### instructions.md (Required)

```markdown
---
title: Your Repo Instructions
priority: must-follow
---

# Your Repo Name

## What This Repo Is
Brief description of the project.

## Source of Truth
- Application code: `src/`
- Configuration: `appsettings.json`, `.env`
- Infrastructure: `infra/`

## How to Run Locally
Steps to build, run, and test the project.
```

### Additional Topic Files (Recommended)

Create separate `.md` files for each major topic:

- `architecture.md` — components, data flows, service boundaries
- `configuration.md` — environment variables, config files, feature flags
- `api.md` — endpoints, contracts, authentication
- `security.md` — auth patterns, secrets, access control
- `operations.md` — deployment, monitoring, troubleshooting
- `data-model.md` — database schemas, key entities, constraints
- `testing.md` — test structure, how to run, coverage expectations
- `patterns.md` — conventions, coding standards, common patterns

## Step 2: Authoring Rules for Memory Files

rMEMbr chunks your markdown at `##` and `###` headings. Follow these rules for optimal retrieval:

- **Keep chunks focused** — one concept per heading section
- **Chunks > 2,000 chars** get split on blank lines (avoid this when possible)
- **Chunks < 100 chars** without a heading are dropped
- **Use YAML front matter** — `title` and optionally `priority: must-follow`
- **Include concrete values** — file paths, env var names, endpoints, versions
- **Lead with facts, not narrative** — AI retrieval works best with direct, scannable content
- **Avoid large code blocks** — keep examples short and representative
- **Reference file paths** — use `path/to/file.py` so the AI can navigate to source

## Step 3: Connect Your Repo to rMEMbr

rMEMbr discovers repos via its **provider framework**. Use the method that fits your setup.

### MCP Registration (Recommended)

If rMEMbr is already running and your repo is on GitHub, register it directly through your AI assistant:

> *"Register my repo in rMEMbr: `owner/my-repo`"*

This calls the `register_repo` MCP tool, which validates the repo has `.ai/memory/manifest.yaml` and adds it to the index. No env var changes or restarts needed.

You can also verify what's registered:

> *"List all repos in rMEMbr"*

### GitHub Provider (Environment Config)

For bootstrapping or permanent repos, configure these env vars in the rMEMbr stack's `.env`:

```env
ACTIVE_PROVIDERS=github
GITHUB_TOKEN=ghp_your_pat_here
GITHUB_REPOS=owner/your-repo          # comma-separated for multiple repos
```

The GitHub provider reads `.ai/memory/` directly from your repo via the GitHub API. No symlinks, no copying, no volume mounts. It uses a two-layer cache (tree ETag + blob SHA) so steady-state indexing costs 0-2 API calls.

> **Note:** Env-var repos and MCP-registered repos are merged automatically. Repos in both sources are deduplicated.

#### Enterprise Standards Repo

The standards service also reads from GitHub. To configure which repo serves enterprise standards:

```env
GITHUB_STANDARDS_REPO=owner/enterprise-standards
```

This must be a repo with standards files under `.ai/memory/enterprise/**/*.md`, each with YAML front matter (`title`, `domain`, `standard_id`). The standards service fetches and caches these via the GitHub API — no local files needed.

Restart the stack after changing env vars:

```bash
docker compose up -d
```

### Filesystem Provider (Alternative)

If your repo is not on GitHub, you can mount it into `mcp-memory-local/repos/`:

```bash
# Windows (PowerShell as Admin)
New-Item -ItemType Junction -Path "mcp-memory-local/repos/your-repo" -Target "C:/path/to/your-repo"

# Linux/macOS
ln -s /path/to/your-repo mcp-memory-local/repos/your-repo
```

> The directory name under `repos/` must match the `scope.repo` value in `manifest.yaml`.

## Step 4: Configure the MCP Client

rMEMbr is a shared local service — configure it once globally so every repo connects automatically.

### Claude Code (Recommended: Global Config)

Run this once to register rMEMbr globally for all repos:

```bash
claude mcp add --transport http rmembr http://localhost:8080/mcp --scope user
```

This stores the config in `~/.claude.json` so every repo has access to rMEMbr automatically. Restart Claude Code to pick up the change.

> **Alternative:** If you only want rMEMbr in a specific repo, create `.mcp.json` at the project root:
> ```json
> {
>   "mcpServers": {
>     "rmembr": {
>       "type": "http",
>       "url": "http://localhost:8080/mcp"
>     }
>   }
> }
> ```

### VS Code (1.102+)

Add to your user settings (`settings.json`) or create `.vscode/mcp.json` per project:

```json
{
  "servers": {
    "rmembr": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## Step 5: Auto-Load Context (Recommended)

Add a `CLAUDE.md` file to the root of your repository so Claude Code automatically pulls rMEMbr context at the start of every task:

```markdown
# AI Assistant Instructions

Before starting any coding task, call the `get_context_bundle` MCP tool with the repo name and a brief task description to load enterprise standards and repo-specific context.
```

This means developers never have to remember to ask for context — Claude will call `get_context_bundle` on its own and receive only the standards relevant to the current task.

> **VS Code Copilot:** Add equivalent instructions to `.github/copilot-instructions.md` for the same effect in VS Code.

## Step 6: Index and Verify

All interaction happens through MCP tools — no scripts needed from your repo.

1. Ask your AI assistant: *"Index my repo in rMEMbr"*
   - This calls `index_repo` via MCP
2. *"Validate my rMEMbr pack"*
   - Calls `validate_pack` to confirm the pack is indexed and queryable
3. *"Search rMEMbr for how this repo is structured"*
   - Calls `search_repo_memory` to test retrieval
4. *"Get a context bundle for adding a new feature to this repo"*
   - Calls `get_context_bundle` for a full bundle with standards

## Available MCP Tools

These are the tools available to your AI assistant once the MCP client is configured:

| Tool | What It Does |
|------|-------------|
| `register_repo` | Register a GitHub repo for indexing (no restart needed) |
| `unregister_repo` | Remove a dynamically registered repo |
| `list_repos` | List all known repos and their index status |
| `index_repo` | Index (or re-index) your repo's memory pack |
| `index_all` | Index all discovered repos |
| `validate_pack` | Verify a pack is indexed and queryable |
| `search_repo_memory` | Semantic search over indexed memory chunks |
| `get_context_bundle` | Assemble a full context bundle (chunks + standards) |
| `explain_context_bundle` | Explain how a bundle was assembled |
| `list_standards` | List available enterprise standards |
| `get_standard` | Retrieve a specific enterprise standard |
| `get_schema` | Retrieve a JSON/YAML schema for a standard |

## Troubleshooting

### "repo not found" or empty search results
- Confirm the repo has `.ai/memory/manifest.yaml` with the correct `scope.repo`
- For GitHub provider: check `GITHUB_REPOS` includes your `owner/repo` and `GITHUB_TOKEN` is valid
- Re-index via MCP: ask your assistant to *"index my repo in rMEMbr"*

### "embedding_service_unavailable"
- The Ollama service may be down or the model not pulled — this is an rMEMbr stack issue, not your repo

### MCP client can't connect
- Verify the gateway is running: `curl http://localhost:8080/health`
- Check `MCP_ENABLED=true` in the rMEMbr stack
- Confirm your `.mcp.json` or `.vscode/mcp.json` points to `http://localhost:8080/mcp`

### Pack validation fails
- Ensure `instructions.md` exists (it's listed in `required_files`)
- Ensure `manifest.yaml` has all required fields
- Ask your assistant to *"validate my rMEMbr pack"* for specific error details

## Auto-Reindexing (Optional)

Trigger reindexing from CI when `.ai/memory/**` files change:

```yaml
# Azure DevOps example
trigger:
  paths:
    include:
      - '.ai/memory/*'

steps:
  - script: |
      curl -X POST http://$RMEMBR_GATEWAY/proxy/index/index_repo \
        -H "Content-Type: application/json" \
        -d '{"repo": "your-repo"}'
```

Or use the MCP `index_repo` tool from any connected client after editing memory files.
