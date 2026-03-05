# ADR-001: Transport, Authentication, and Tenancy

**Version:** 0.1.0
**Status:** Accepted
**Last Updated:** 2026-03-05
**Deciders:** Architecture team

---

## Context

The rMEMbr Context Gateway MCP system needs decisions on three cross-cutting concerns:

1. **Transport protocol** for MCP tool invocation
2. **Authentication and authorization** across deployment environments
3. **Tenancy model** for data isolation

These decisions affect all services (Gateway, Index, Standards) and all downstream phases.

---

## Decision 1: Transport Protocol

### Chosen: Streamable HTTP (primary), stdio (dev-only shim)

**Primary transport: Streamable HTTP**
- All services run as FastAPI HTTP servers
- Gateway on port 8080, Index on 8081, Standards on 8082
- Tools are invoked via `POST /tools/<tool_name>` with JSON body
- Response is JSON (not streaming for current tools; streaming reserved for future large-bundle scenarios)
- Inter-service communication uses the same HTTP transport with `X-Internal-Token` auth headers

**Dev-only shim: stdio**
- For local development and testing with MCP-compatible clients (e.g., Claude Desktop)
- stdio transport wraps the same tool handlers
- Not supported in any deployed environment (Dev/Test/Prod)
- No SLO targets apply to stdio transport

### Rationale
- HTTP is the standard production transport for MCP servers
- FastAPI provides built-in OpenAPI docs, middleware, and async support
- stdio is convenient for local iteration but not suitable for multi-service orchestration

---

## Decision 2: Authentication Matrix

### Deny-by-default

All endpoints except `/health` require authentication. Unauthenticated requests receive `401 Unauthorized`.

### Per-environment requirements

| Environment | Client -> Gateway | Gateway -> Index | Gateway -> Standards | Mechanism |
|-------------|-------------------|------------------|---------------------|-----------|
| **Local** | None (localhost only) | `X-Internal-Token` (shared secret from `.env`) | `X-Internal-Token` (shared secret from `.env`) | Shared secret via environment variable `INTERNAL_SERVICE_TOKEN` |
| **Dev** | API key (header `X-API-Key`) | `X-Internal-Token` (rotated weekly) | `X-Internal-Token` (rotated weekly) | API key issued per developer; internal token from secrets manager |
| **Test** | API key (header `X-API-Key`) | `X-Internal-Token` (per-deployment) | `X-Internal-Token` (per-deployment) | Same mechanism as Dev; ephemeral tokens per test environment |
| **Prod** | OAuth 2.0 bearer token (header `Authorization: Bearer <token>`) | `X-Internal-Token` (rotated daily, from vault) | `X-Internal-Token` (rotated daily, from vault) | Azure AD / Entra ID for client auth; Azure Key Vault for internal tokens |

### Auth enforcement details

- **Health endpoints** (`GET /health`) are exempt from auth in all environments (required for orchestration health checks)
- **Internal services** (Index, Standards) enforce `X-Internal-Token` via `InternalAuthMiddleware` on all non-health endpoints
- **Gateway** currently does not enforce client auth (Local environment). Dev/Test/Prod client auth is a Phase 1 deliverable.
- **Deny-by-default:** If an environment is not listed above, all requests are denied. No implicit trust.

### Token specifications

| Token | Format | Minimum Length | Rotation |
|-------|--------|---------------|----------|
| `INTERNAL_SERVICE_TOKEN` | Random hex string | 32 characters | Per environment policy (see matrix above) |
| `X-API-Key` (Dev/Test) | UUID v4 | 36 characters | Per-developer, revocable |
| OAuth bearer (Prod) | JWT | N/A | Token lifetime per Azure AD policy |

---

## Decision 3: Tenancy Model

### Chosen: Single-tenant deployment with multi-tenant-capable schema

**Current state:** One Postgres database per organization. All data in the `default` namespace.

**Schema preparation:**
- `namespace` column exists on `memory_packs` and `memory_chunks`
- Unique constraints include `namespace` (e.g., `UNIQUE(namespace, repo)`)
- All queries filter by `namespace`
- No cross-namespace queries exist in the API

**Migration path to multi-tenant:**
- Add namespace-routing middleware at Gateway (map auth identity -> namespace)
- No schema changes required
- No data migration required
- Connection pooling per namespace is optional (single pool with namespace filtering is sufficient at moderate scale)

### What this means for Phase 1+

- All new tables MUST include a `namespace` column
- All new queries MUST filter by `namespace`
- No API endpoint may return data from multiple namespaces in a single response

---

## Decision 4: Compatibility Policy

### 2-release / 6-month (6 months) compatibility window

When a tool is renamed, its schema changed in a breaking way, or deprecated:

1. **Old name/schema continues to work** as an alias for the duration of the compatibility window
2. **Alias responses include** an `X-Deprecated-Tool` header with the replacement tool name
3. **Telemetry events** are emitted for each alias invocation (tool name, caller identity if available)
4. **After the window closes**, the alias is removed. Callers using the old name receive `404 Not Found`.

**Compatibility window duration:** Whichever is longer:
- 2 releases of the Gateway service
- 6 calendar months from the deprecation announcement

### Non-breaking changes (no compatibility window needed)

- Adding optional fields to request schemas
- Adding new fields to response schemas
- Adding new tools
- Relaxing validation constraints (e.g., increasing `maxLength`)

### Breaking changes (compatibility window required)

- Removing or renaming tools
- Removing or renaming required request fields
- Changing field types
- Tightening validation constraints
- Changing response structure (removing fields, changing nesting)

---

## Consequences

### Positive
- Clear, auditable auth requirements per environment
- Tenancy isolation at the schema level from day one
- Predictable deprecation timeline for API consumers

### Negative
- Local environment has no client auth, which means local-only security boundary
- Multi-tenant routing logic is deferred (adds complexity when implemented)
- Compatibility aliases add maintenance burden during transition periods

### Risks
- If `INTERNAL_SERVICE_TOKEN` leaks, all inter-service auth is compromised for that environment. Mitigation: rotation policy, secrets manager in non-Local environments.
- Namespace isolation is enforced by application code (SQL WHERE clause), not database-level row security. Mitigation: consider Postgres RLS in Phase 2+ if threat model warrants it.
