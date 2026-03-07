# Configuration Guide

## Environment Variables

Copy `.env.example` to `.env` and adjust values for your environment:

```bash
cp .env.example .env
```

### All Variables

| Variable | Default | Service(s) | Description |
|----------|---------|------------|-------------|
| **Postgres** | | | |
| `POSTGRES_DB` | `memory` | postgres, index, gateway | Database name |
| `POSTGRES_USER` | `memory` | postgres, index, gateway | Database user |
| `POSTGRES_PASSWORD` | `CHANGE_ME` | postgres, index, gateway | Database password |
| `POSTGRES_HOST` | `postgres` | index, gateway | Database hostname (Docker service name) |
| `POSTGRES_PORT` | `5432` | index, gateway | Database port |
| **Embeddings** | | | |
| `OLLAMA_URL` | `http://ollama:11434` | index | Ollama API endpoint |
| `EMBED_MODEL` | `nomic-embed-text` | index | Embedding model name |
| `EMBED_DIMS` | `768` | docker-compose | Embedding vector dimensions (informational) |
| **Repository** | | | |
| `REPOS_ROOT` | `/repos` | index, standards | Mount path for repository files |
| `STANDARDS_REPO` | `enterprise-standards` | standards | Directory name for enterprise standards |
| `DEFAULT_STANDARDS_VERSION` | `local` | standards | Default standards version to serve |
| **Gateway** | | | |
| `GATEWAY_MAX_BUNDLE_CHARS` | `40000` | gateway | Max characters in a context bundle |
| `GATEWAY_DEFAULT_K` | `12` | gateway | Default number of chunks to retrieve |
| `BUNDLE_CACHE_TTL_SECONDS` | `300` | gateway | Cache TTL for search-based bundles (seconds) |
| `GATEWAY_PORT` | `8080` | gateway | Listening port |
| **MCP** | | | |
| `MCP_ENABLED` | `false` | gateway | Enable MCP server. Primary transport is Streamable HTTP at `/mcp`; legacy SSE remains available at `/mcp/sse` and `/mcp/messages/`. Must be `true` for MCP clients (VS Code, Claude Code) to connect. |
| `MCP_STDIO_ENABLED` | `false` | gateway | Enable MCP stdio transport. Used for local pipe-based MCP clients. Not needed for VS Code or Claude Code. |
| **Policy** | | | |
| `POLICY_FILE` | *(empty)* | gateway | Path to policy bundle JSON file. If empty, built-in defaults are used (same behavior as pre-Phase 4). |
| `POLICY_HOT_RELOAD` | `false` | gateway | Enable policy file hot-reload (non-prod only). When `true` and `POLICY_FILE` is set, policy is reloaded on file change without gateway restart. |
| `GATEWAY_MAX_SOURCES` | `50` | gateway | Maximum number of sources (chunks) per request. Clamps the `k` parameter if it exceeds this value. |
| **Auth** | | | |
| `INTERNAL_SERVICE_TOKEN` | `dev-secret-token-change-in-prod` | all services | Shared secret for inter-service auth |
| **Multi-tenancy** | | | |
| `DEFAULT_NAMESPACE` | `default` | index, gateway | Default namespace for operations |
| **Service Ports** | | | |
| `INDEX_PORT` | `8081` | index | Index service listening port |
| `STANDARDS_PORT` | `8082` | standards | Standards service listening port |
| **CLI / Scripts** | | | |
| `GATEWAY_URL` | `http://localhost:8080` | mcp-cli.py, watch-reindex.py | Gateway URL for external clients |

## docker-compose.yml Structure

Five services on a shared bridge network (`internal`):

```
┌─────────────────────────────────────────────────────┐
│                   Docker Network: internal           │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ postgres  │  │  ollama  │  │     gateway      │──┼── :8080 (host)
│  │  :5432    │  │  :11434  │  │      :8080       │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                  │           │      │
│                           ┌──────┘           └────┐ │
│                           ▼                       ▼ │
│                    ┌──────────┐            ┌──────┐ │
│                    │  index   │            │stds  │ │
│                    │  :8081   │            │:8082 │ │
│                    └──────────┘            └──────┘ │
└─────────────────────────────────────────────────────┘
```

- **postgres** — PostgreSQL with pgvector extension. Volume: `pgdata`
- **ollama** — Embedding model server. Volume: `ollama_data`
- **index** — Indexes memory packs, handles search. Volume: `./repos:/repos`
- **standards** — Serves enterprise standards. Volume: `./repos:/repos`
- **gateway** — External entry point, assembles bundles, proxies to internal services

Only the gateway exposes a host port (`8080:8080`). Index and standards are internal-only.

### Volumes

| Volume | Mount | Purpose |
|--------|-------|---------|
| `pgdata` | postgres data directory | Persistent database storage |
| `ollama_data` | ollama models directory | Cached embedding models |
| `./repos` | `/repos` in index & standards | Repository files and standards |

## Inter-Service Authentication

Internal services (index, standards) are protected by a shared secret token.

**Mechanism:**
- The gateway adds `X-Internal-Token` and `X-Request-ID` headers to all proxied requests
- Index and standards services validate the token via `InternalAuthMiddleware`
- `/health` endpoints are exempt from auth
- Missing token returns HTTP 401: `{"error": "missing X-Internal-Token header"}`
- Invalid token returns HTTP 401: `{"error": "invalid X-Internal-Token"}`

**Configuration:**
- Set `INTERNAL_SERVICE_TOKEN` in `.env` — use a strong random value in production
- The gateway itself has no inbound authentication (it's the trust boundary)

**Request tracing:**
- Every gateway request generates a `X-Request-ID` (UUID)
- This ID is propagated to internal services and included in all log output

## manifest.yaml Full Schema

```yaml
# Required: schema version
pack_version: 1

# Scope: which repo and namespace this pack belongs to
scope:
  repo: my-repo              # Must match the directory name under repos/
  namespace: default          # Logical namespace (default: "default")

# Teams or groups responsible for maintaining this pack
owners:
  - platform-architecture

# Files that must exist in .ai/memory/ for the pack to be valid
required_files:
  - instructions.md

# Access classification: controls visibility per persona
# "public" = visible to all personas
# "internal" = visible to human and agent, hidden from external
classification: internal

# Embedding configuration: must match the running model
embedding:
  model: nomic-embed-text    # Model name in Ollama
  dims: 768                  # Vector dimensions
  version: locked            # Version tag for cache invalidation

# References to enterprise standards this repo follows
references:
  standards:
    - enterprise/ado/pipelines/job-templates-v3
    - enterprise/terraform/module-versioning

# Override policy (reserved for future use)
override_policy:
  allow_repo_overrides: false
```

**Validation rules for the parser:**
- All fields have defaults; an empty `manifest.yaml` is valid
- `scope.repo` defaults to empty string (should match directory name)
- `classification` defaults to `"internal"`
- `embedding.model` defaults to `"nomic-embed-text"`
- `embedding.dims` defaults to `768`
- Unknown fields are silently ignored

## Directory Structure Conventions

```
project-root/
├── docker-compose.yml
├── .env.example
├── .env                         # Your local config (gitignored)
├── repos/                       # Mounted as /repos in containers
│   ├── sample-repo-a/
│   │   └── .ai/
│   │       └── memory/
│   │           ├── manifest.yaml
│   │           ├── instructions.md
│   │           └── *.md
│   ├── sample-repo-b/
│   │   └── .ai/memory/...
│   └── enterprise-standards/    # Standards repo (STANDARDS_REPO)
│       ├── local/
│       │   └── enterprise/
│       │       └── <domain>/<standard>.md
│       ├── v3/
│       │   └── enterprise/...
│       └── v4/
│           └── enterprise/...
├── services/
│   ├── gateway/src/server.py
│   ├── index/src/
│   │   ├── server.py
│   │   ├── embeddings.py
│   │   ├── ingest.py
│   │   └── migrations.py
│   ├── standards/src/server.py
│   └── shared/src/
│       ├── auth.py
│       ├── manifest/parser.py
│       └── chunking/chunker.py
└── scripts/
    ├── mcp-cli.py
    └── watch-reindex.py
```

## Database Schema

Three tables in the `memory` database (PostgreSQL with pgvector).

### memory_packs

Tracks indexed repositories and their metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL` PK | Auto-increment ID |
| `namespace` | `TEXT` | Logical namespace (default: `"default"`) |
| `repo` | `TEXT` | Repository name |
| `pack_version` | `INT` | Manifest schema version |
| `owners` | `JSONB` | Owner list from manifest |
| `classification` | `TEXT` | Access classification |
| `embedding_model` | `TEXT` | Model used for embeddings |
| `last_indexed_ref` | `TEXT` | Last indexed version ref |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Last update timestamp |

Unique constraint: `(namespace, repo)`

### memory_chunks

Individual chunks with their embeddings.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL` PK | Auto-increment ID |
| `namespace` | `TEXT` | Logical namespace |
| `source_kind` | `TEXT` | Source type (default: `"repo_memory"`) |
| `repo` | `TEXT` | Repository name |
| `ref_type` | `TEXT` | Ref type (default: `"branch"`) |
| `ref` | `TEXT` | Version ref (default: `"local"`) |
| `path` | `TEXT` | File path relative to repo |
| `anchor` | `TEXT` | Stable slug identifier for the chunk |
| `heading` | `TEXT` | Section heading (or `"(preamble)"`) |
| `chunk_text` | `TEXT` | Full text sent to embedding model |
| `metadata_json` | `JSONB` | YAML front matter metadata |
| `content_hash` | `TEXT` | SHA-256 of chunk_text |
| `embedding_model` | `TEXT` | Model used for this embedding |
| `embedding_version` | `TEXT` | Embedding version tag |
| `embedding` | `vector(768)` | pgvector embedding |
| `classification` | `TEXT` | Access classification |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Last update timestamp |

Unique constraint: `(repo, path, anchor, ref)` — used for upsert on reindex.

### bundle_cache

Cached bundles and bundle records.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `BIGSERIAL` PK | Auto-increment ID |
| `cache_key` | `TEXT` | Unique cache key (SHA-256 hash or `bundle:<uuid>`) |
| `bundle_json` | `JSONB` | Full bundle payload |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp |
| `expires_at` | `TIMESTAMPTZ` | Expiry timestamp |

Unique constraint: `cache_key`

**Cache key formats:**
- Search bundles: SHA-256 of `{namespace}:{repo}:{task_hash[:16]}:{ref}:{standards_version}`
- Bundle records: `bundle:<uuid>` (24-hour TTL, not configurable)

### Indexes

| Index | Type | Table | Columns | Purpose |
|-------|------|-------|---------|---------|
| `idx_chunks_embedding_hnsw` | HNSW | memory_chunks | `embedding` (cosine) | Fast ANN vector search |
| `idx_chunks_namespace_repo_ref` | B-tree | memory_chunks | `namespace, repo, ref` | Filtered queries |
| `idx_chunks_repo_path_anchor_ref` | Unique B-tree | memory_chunks | `repo, path, anchor, ref` | Upsert deduplication |
| `idx_bundle_cache_key` | B-tree | bundle_cache | `cache_key` | Cache lookups |
| `idx_bundle_cache_key_unique` | Unique B-tree | bundle_cache | `cache_key` | Upsert deduplication |

## Monitoring

The gateway exposes Prometheus metrics at `/metrics` when `prometheus_client` is installed. This endpoint is part of the gateway server and is active regardless of whether the monitoring profile is enabled.

### Metrics Endpoint

- **URL:** `http://localhost:8080/metrics`
- **Format:** Prometheus text exposition (text/plain; version=0.0.4)
- **Binding:** Controlled by `METRICS_BIND_HOST` env var (default `127.0.0.1`, set to `0.0.0.0` in docker-compose for container access)

### Available Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mcp_tool_call_duration_seconds` | Histogram | `tool`, `cache_state` | Tool call latency |
| `mcp_tool_call_total` | Counter | `tool`, `status` | Total tool calls (success/error/denied) |
| `mcp_tool_call_errors_total` | Counter | `tool` | Total tool call errors |
| `mcp_dependency_health` | Gauge | `dependency` | Dependency health (1=up, 0=down) |
| `mcp_dependency_health_last_probe_timestamp` | Gauge | `dependency` | Unix epoch of last health probe |

### Monitoring Stack (Optional)

Enable Prometheus and Grafana with the monitoring profile:

```bash
docker compose --profile monitoring up -d
```

- **Prometheus:** `http://localhost:9090` — scrapes gateway `/metrics` every 15s
- **Grafana:** `http://localhost:3000` — default credentials: admin/admin

Import the gateway dashboard:
1. Open Grafana at `http://localhost:3000`
2. Go to Dashboards → Import
3. Upload `monitoring/dashboards/gateway-overview.json`

### Alert Rules

Alert rules are defined in `monitoring/alerts/gateway-alerts.yaml`:

| Alert | Condition | Severity |
|-------|-----------|----------|
| `SearchLatencyP95High` | search p95 > 1.5s for 5m | warning |
| `BundleLatencyP95High` | bundle p95 > 4.0s for 5m | warning |
| `HighErrorRate` | error rate > 1% for 5m | critical |
| `DependencyDown` | dependency health = 0 for 1m | critical |
| `DependencyProbeStale` | probe age > 90s for 2m | warning |

### Environment Variables (Monitoring)

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_BIND_HOST` | `127.0.0.1` | Bind address for metrics. Set to `0.0.0.0` in Docker. |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana admin password |

## Logging Format and Request Tracing

All services use structured logging with request ID propagation.

- The gateway generates a `X-Request-ID` (UUID) for each incoming request
- This ID is forwarded to internal services via request headers
- Log entries include the request ID for cross-service tracing

To trace a request across services, search logs for the request ID:

```bash
docker compose logs | grep <request-id>
```
