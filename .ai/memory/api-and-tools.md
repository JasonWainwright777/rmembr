---
title: API and Tools
---

# API and Tools (HTTP)

All services are FastAPI apps. Only the Gateway is exposed to the host by default.

## Gateway (host port 8080)

## `GET /health`

Returns a rollup health check for gateway + dependencies.

## `POST /tools/get_context_bundle`

Assemble a context bundle.

Request body (common fields):

- `repo` (string, required): repo name under `mcp-memory-local/repos/`
- `task` (string, required): task description (max 2000 chars)
- `persona` (string, default `human`): `human | agent | external`
- `k` (int, default `12`): number of chunks to retrieve from Index (1-100)
- `ref` (string, default `local`): logical ref tag for indexed chunks
- `namespace` (string, default `default`): multi-tenant namespace
- `standards_version` (string, default `local`): standards content version
- `changed_files` (string[], optional): boosts matching paths by +0.1 similarity
- `filters` (object, optional): forwarded to Index search (see below)

Response body:

- `bundle_id` (uuid string)
- `bundle` (object): includes `chunks`, `standards_content`, counts, and metadata
- `markdown` (string): markdown rendering of the bundle
- `cached` (bool)

## `POST /tools/explain_context_bundle`

Request body:

- `bundle_id` (string, required)

Returns a breakdown of how the bundle was built.

## `POST /tools/validate_pack`

Lightweight validation: checks that Index search works for the repo/ref.

Request body:

- `repo` (string, required)
- `ref` (string, default `local`)

## Proxy Endpoints (for the CLI)

Gateway also exposes proxy endpoints that forward to internal services with auth headers:

- `POST /proxy/index/{tool}` -> Index `/tools/{tool}`
- `POST /proxy/standards/{tool}` -> Standards `/tools/{tool}`

These are primarily used by `mcp-memory-local/scripts/mcp-cli.py`.

## Index (internal)

All non-`/health` endpoints require `X-Internal-Token`.

## `POST /tools/index_repo`

Request body:

- `repo` (required)
- `ref` (default `local`)

Returns counts for new/updated/unchanged/deleted chunks.

## `POST /tools/index_all`

Request body:

- `ref` (default `local`)

## `POST /tools/search_repo_memory`

Request body:

- `repo` (required)
- `query` (required)
- `k` (default `8`)
- `ref` (default `local`)
- `namespace` (default `default`)
- `filters` (optional object):
  - allowed keys: `source_kind`, `classification`, `heading`, `path` (all strings)

Response:

- `results`: list of `{path, anchor, heading, snippet, source_kind, classification, similarity, ...}`
- `count`

## `POST /tools/resolve_context`

Same idea as `search_repo_memory`, but input is `task` and it optionally boosts `changed_files`.

## Standards (internal)

All non-`/health` endpoints require `X-Internal-Token`.

## `POST /tools/list_standards`

Request body:

- `version` (default: env `DEFAULT_STANDARDS_VERSION` or `local`)
- `domain` (optional): prefix filter like `enterprise/terraform`

Response:

- `standards`: list of `{id, version}`
- `count`

## `POST /tools/get_standard`

Request body:

- `id` (required): slash-separated ID (validated, lowercase segments)
- `version` (default: env `DEFAULT_STANDARDS_VERSION` or `local`)

Response:

- `id`, `version`, `path`, `content`

## `POST /tools/get_schema`

Like `get_standard`, but looks for schema files: `.schema.json`, `.schema.yaml`, etc.

