# Gateway MCP Tool Surface Contract

**Version:** 0.1.0
**MCP Specification Version:** 2025-03-26 (Streamable HTTP)
**Status:** Locked (Phase 0)
**Last Updated:** 2026-03-05

---

## Overview

This document defines the canonical MCP tool surface for the rMEMbr Context Gateway. All tools are exposed as HTTP POST endpoints under `/tools/` on the Gateway service (port 8080). Internal services (Index on 8081, Standards on 8082) are not directly exposed to MCP clients.

---

## Tool: `search_repo_memory`

**Service:** Index (proxied through Gateway at `/proxy/index/search_repo_memory`)
**Purpose:** Semantic search over a repository's indexed memory chunks.

### Request Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["repo", "query"],
  "properties": {
    "repo": {
      "type": "string",
      "description": "Repository name. Must not contain path traversal characters (.. / \\).",
      "minLength": 1,
      "examples": ["sample-repo-a", "enterprise-standards"]
    },
    "query": {
      "type": "string",
      "description": "Semantic search query.",
      "minLength": 1,
      "maxLength": 2000,
      "examples": ["How do we version Terraform modules?"]
    },
    "k": {
      "type": "integer",
      "description": "Number of results to return.",
      "minimum": 1,
      "maximum": 100,
      "default": 8
    },
    "ref": {
      "type": "string",
      "description": "Git ref or 'local' for local-only content.",
      "default": "local",
      "examples": ["local", "main", "abc1234"]
    },
    "namespace": {
      "type": "string",
      "description": "Tenant namespace. Defaults to 'default'.",
      "minLength": 1,
      "default": "default"
    },
    "filters": {
      "type": ["object", "null"],
      "description": "Optional filters. Allowed keys: source_kind, classification, heading, path.",
      "properties": {
        "source_kind": { "type": "string" },
        "classification": { "type": "string" },
        "heading": { "type": "string" },
        "path": { "type": "string" }
      },
      "additionalProperties": false,
      "default": null
    }
  },
  "additionalProperties": false
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["results", "count"],
  "properties": {
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "path", "anchor", "heading", "snippet", "source_kind", "classification", "similarity"],
        "properties": {
          "id": { "type": "integer", "description": "Chunk ID" },
          "path": { "type": "string", "description": "File path within the memory pack" },
          "anchor": { "type": "string", "description": "Chunk anchor (heading-slug-cN)" },
          "heading": { "type": "string", "description": "Nearest parent heading" },
          "snippet": { "type": "string", "description": "First 500 chars of chunk text" },
          "source_kind": { "type": "string", "enum": ["repo_memory", "enterprise_standard"] },
          "classification": { "type": "string", "enum": ["public", "internal"] },
          "similarity": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      }
    },
    "count": { "type": "integer" }
  }
}
```

### Error Codes

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| 400 | `Validation error on 'repo': must not be empty` | Missing or empty repo |
| 400 | `Validation error on 'query': must not be empty` | Missing or empty query |
| 400 | `Validation error on 'k': must be between 1 and 100` | k out of range |
| 400 | `Validation error on 'filters': unknown filter key '...'` | Invalid filter key |
| 401 | `missing X-Internal-Token header` | No auth token (internal services) |
| 401 | `invalid X-Internal-Token` | Wrong auth token (internal services) |

### Example

**Request:**
```json
{
  "repo": "sample-repo-a",
  "query": "How should we handle secrets in pipelines?",
  "k": 5,
  "ref": "local",
  "namespace": "default"
}
```

**Response:**
```json
{
  "results": [
    {
      "id": 42,
      "path": ".ai/memory/enterprise/security/secrets-management.md",
      "anchor": "secrets-management-c0",
      "heading": "Secrets Management",
      "snippet": "All secrets must be stored in Azure Key Vault...",
      "source_kind": "enterprise_standard",
      "classification": "internal",
      "similarity": 0.847
    }
  ],
  "count": 1
}
```

---

## Tool: `get_context_bundle`

**Service:** Gateway (`/tools/get_context_bundle`)
**Purpose:** Assemble a complete context bundle by orchestrating Index and Standards services. Returns prompt-ready context with enterprise standards, ranked memory chunks, and classification filtering.

### Request Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["repo", "task"],
  "properties": {
    "repo": {
      "type": "string",
      "description": "Repository name.",
      "minLength": 1,
      "examples": ["sample-repo-a"]
    },
    "task": {
      "type": "string",
      "description": "Task description for context retrieval.",
      "minLength": 1,
      "maxLength": 2000,
      "examples": ["Implement a new Terraform module for VNet peering"]
    },
    "k": {
      "type": "integer",
      "description": "Number of context chunks to retrieve.",
      "minimum": 1,
      "maximum": 100,
      "default": 12
    },
    "ref": {
      "type": "string",
      "default": "local"
    },
    "namespace": {
      "type": "string",
      "default": "default"
    },
    "persona": {
      "type": "string",
      "description": "Caller persona. Controls classification-based filtering.",
      "enum": ["human", "agent", "external"],
      "default": "human"
    },
    "standards_version": {
      "type": "string",
      "description": "Version tag for standards content.",
      "default": "local",
      "examples": ["local", "v3"]
    },
    "changed_files": {
      "type": ["array", "null"],
      "description": "List of changed file paths for relevance boosting.",
      "items": { "type": "string" },
      "default": null
    },
    "filters": {
      "type": ["object", "null"],
      "description": "Optional filters passed to search.",
      "default": null
    }
  },
  "additionalProperties": false
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["bundle_id", "bundle", "markdown", "cached"],
  "properties": {
    "bundle_id": { "type": "string", "format": "uuid" },
    "bundle": {
      "type": "object",
      "required": ["bundle_id", "repo", "task", "persona", "ref", "namespace", "standards_version", "standards_content", "chunks", "total_candidates", "filtered_count", "returned_count", "created_at"],
      "properties": {
        "bundle_id": { "type": "string", "format": "uuid" },
        "repo": { "type": "string" },
        "task": { "type": "string" },
        "persona": { "type": "string" },
        "ref": { "type": "string" },
        "namespace": { "type": "string" },
        "standards_version": { "type": "string" },
        "standards_content": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "string" },
              "version": { "type": "string" },
              "path": { "type": "string" },
              "content": { "type": "string" }
            }
          }
        },
        "chunks": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "integer" },
              "path": { "type": "string" },
              "anchor": { "type": "string" },
              "heading": { "type": "string" },
              "snippet": { "type": "string" },
              "source_kind": { "type": "string" },
              "classification": { "type": "string" },
              "similarity": { "type": "number" },
              "_priority_class": { "type": "string", "enum": ["enterprise_must_follow", "repo_must_follow", "task_specific"] }
            }
          }
        },
        "total_candidates": { "type": "integer" },
        "filtered_count": { "type": "integer" },
        "returned_count": { "type": "integer" },
        "created_at": { "type": "string", "format": "date-time" }
      }
    },
    "markdown": { "type": "string", "description": "Human-readable markdown rendering of the bundle" },
    "cached": { "type": "boolean" }
  }
}
```

### Error Codes

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| 400 | Validation errors | Missing/invalid repo, task, k, namespace, or filters |
| 502 | `Index service error: ...` | Index service unreachable or returned error |

---

## Tool: `explain_context_bundle`

**Service:** Gateway (`/tools/explain_context_bundle`)
**Purpose:** Explain how a previously assembled bundle was constructed (chunk counts, priority breakdown, filtering decisions).

### Request Schema

```json
{
  "type": "object",
  "required": ["bundle_id"],
  "properties": {
    "bundle_id": {
      "type": "string",
      "format": "uuid",
      "description": "ID of a previously returned bundle."
    }
  },
  "additionalProperties": false
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["bundle_id", "repo", "task", "persona", "total_candidates", "after_classification_filter", "after_budget_trim", "standards_included", "priority_breakdown", "chunks_summary"],
  "properties": {
    "bundle_id": { "type": "string" },
    "repo": { "type": "string" },
    "task": { "type": "string" },
    "persona": { "type": "string" },
    "total_candidates": { "type": "integer" },
    "after_classification_filter": { "type": "integer" },
    "after_budget_trim": { "type": "integer" },
    "standards_included": { "type": "array", "items": { "type": "string" } },
    "priority_breakdown": { "type": "object", "additionalProperties": { "type": "integer" } },
    "chunks_summary": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "heading": { "type": "string" },
          "priority": { "type": "string" },
          "similarity": { "type": "number" },
          "classification": { "type": "string" }
        }
      }
    }
  }
}
```

### Error Codes

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| 400 | `bundle_id is required` | Missing bundle_id |
| 404 | `Bundle '...' not found` | Bundle expired or never existed |

---

## Tool: `validate_pack`

**Service:** Gateway (`/tools/validate_pack`)
**Purpose:** Validate that a repository's memory pack is indexed and queryable.

### Request Schema

```json
{
  "type": "object",
  "required": ["repo"],
  "properties": {
    "repo": { "type": "string", "minLength": 1 },
    "ref": { "type": "string", "default": "local" }
  },
  "additionalProperties": false
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["repo", "ref", "valid", "issues"],
  "properties": {
    "repo": { "type": "string" },
    "ref": { "type": "string" },
    "valid": { "type": "boolean" },
    "issues": { "type": "array", "items": { "type": "string" } }
  }
}
```

---

## Tool: `index_repo`

**Service:** Index (proxied through Gateway at `/proxy/index/index_repo`)
**Purpose:** Trigger indexing (chunk + embed) for a single repository's memory pack.

### Request Schema

```json
{
  "type": "object",
  "required": ["repo"],
  "properties": {
    "repo": { "type": "string", "minLength": 1 },
    "ref": { "type": "string", "default": "local" }
  },
  "additionalProperties": false
}
```

---

## Tool: `index_all`

**Service:** Index (proxied through Gateway at `/proxy/index/index_all`)
**Purpose:** Trigger indexing for all discovered repositories.

### Request Schema

```json
{
  "type": "object",
  "properties": {
    "ref": { "type": "string", "default": "local" }
  },
  "additionalProperties": false
}
```

---

## Tool: `list_standards`

**Service:** Standards (proxied through Gateway at `/proxy/standards/list_standards`)
**Purpose:** List available enterprise standard IDs.

### Request Schema

```json
{
  "type": "object",
  "properties": {
    "domain": { "type": ["string", "null"], "description": "Filter by domain prefix" },
    "version": { "type": "string", "default": "local" }
  },
  "additionalProperties": false
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["standards", "count"],
  "properties": {
    "standards": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "version"],
        "properties": {
          "id": { "type": "string", "examples": ["enterprise/terraform/module-versioning"] },
          "version": { "type": "string" }
        }
      }
    },
    "count": { "type": "integer" }
  }
}
```

---

## Tool: `get_standard`

**Service:** Standards (proxied through Gateway at `/proxy/standards/get_standard`)
**Purpose:** Retrieve the content of a specific enterprise standard.

### Request Schema

```json
{
  "type": "object",
  "required": ["id"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Standard ID. Must match pattern: lowercase alphanumeric segments separated by '/'.",
      "pattern": "^[a-z0-9\\-]+(/[a-z0-9\\-]+)*$",
      "examples": ["enterprise/terraform/module-versioning"]
    },
    "version": { "type": "string", "default": "local" }
  },
  "additionalProperties": false
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["id", "version", "path", "content"],
  "properties": {
    "id": { "type": "string" },
    "version": { "type": "string" },
    "path": { "type": "string" },
    "content": { "type": "string" }
  }
}
```

### Error Codes

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| 400 | Validation error on 'id' | Invalid standard ID format |
| 404 | `Standard '...' not found` | Standard does not exist at specified version |

---

## Tool: `get_schema`

**Service:** Standards (proxied through Gateway at `/proxy/standards/get_schema`)
**Purpose:** Retrieve a JSON/YAML schema file associated with a standard.

### Request Schema

```json
{
  "type": "object",
  "required": ["id"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z0-9\\-]+(/[a-z0-9\\-]+)*$"
    },
    "version": { "type": "string", "default": "local" }
  },
  "additionalProperties": false
}
```

---

## Versioning Metadata

| Field | Value |
|-------|-------|
| Contract Version | 0.1.0 |
| MCP Spec Version | 2025-03-26 |
| Compatibility Window | 2 releases or 6 months (whichever is longer) |
| Deprecation Policy | Old tool names remain as aliases during compatibility window; aliases emit `X-Deprecated-Tool` response header |
