# Tool Schema Migration & Version Strategy

## Overview

This document defines how MCP tool schemas evolve, how breaking vs non-breaking changes are classified, and how backward compatibility is enforced during the compatibility window.

**Applies to:** All tools defined in `docs/contracts/gateway-mcp-tools.md`.

---

## Change Classification

### Non-breaking changes (minor version bump)

These changes are backward-compatible and can be deployed without client coordination:

- **Adding optional parameters** with defaults that preserve existing behavior
- **Adding new response fields** (clients should ignore unknown fields)
- **Widening parameter constraints** (e.g., increasing `maxLength`, widening `enum` values)
- **Adding new tools** (existing tools unchanged)
- **Improving error messages** (same status codes, clearer text)
- **Adding response headers** (e.g., `X-Deprecated-Tool`)

### Breaking changes (major version bump)

These changes require the compatibility window and deprecation process:

- **Removing a tool** entirely
- **Removing or renaming a parameter**
- **Changing a parameter from optional to required**
- **Narrowing parameter constraints** (e.g., reducing `maxLength`, removing `enum` values)
- **Changing response structure** (removing fields, changing types)
- **Changing error codes** for existing failure modes
- **Renaming a tool**

---

## Compatibility Window

**Policy:** 2 releases or 6 months, whichever is longer.

When a breaking change is planned:

1. **Deprecation announcement:** Add `X-Deprecated-Tool` header to responses from the old tool. Document the deprecation in `gateway-mcp-tools.md` with the replacement tool name and deprecation date.

2. **Alias period:** The old tool name continues to work as an alias for the new behavior. Both old and new tools are available simultaneously.

3. **Removal:** After the compatibility window expires, the old tool may be removed. Removal requires passing the compatibility CI gate (`scripts/check_compatibility.py`).

---

## Database Schema Migrations

### Current mechanism

Migrations are defined in `mcp-memory-local/services/index/src/migrations.py` as a sequential array. They run automatically on service startup.

### Migration rules

1. **Forward-only in production:** Migrations execute sequentially. Each migration has an index; the service tracks the last applied migration.

2. **Additive preferred:** Prefer `ADD COLUMN` with defaults over `ALTER COLUMN` or `DROP COLUMN`. This avoids breaking running instances during rolling deployments.

3. **Rollback procedure:**
   - For `ADD COLUMN`: the column is ignored by older code (no rollback needed).
   - For `ALTER COLUMN` type changes: provide a reverse migration script in `docs/operations/migration-rollbacks/`.
   - For `DROP COLUMN`: the column must be unused for at least one release before dropping. Provide a restore script.
   - For `CREATE INDEX`: drop the index (`DROP INDEX IF EXISTS`).

4. **Testing:** All migrations must be tested against a fresh database AND against a database with existing data. The migration must be idempotent where possible (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`).

### Version tracking

The `schema_version` table (or equivalent tracking mechanism) records:
- Migration index (sequential integer)
- Applied timestamp
- Migration description

---

## Tool Schema Versioning

### Version metadata

Every tool schema in `gateway-mcp-tools.md` must include:

| Field | Description |
|-------|-------------|
| Contract Version | Semver of the tool contract document |
| MCP Spec Version | The MCP specification version targeted |
| Compatibility Window | Duration of backward compatibility guarantee |
| Deprecation Policy | How deprecated tools are handled |

### Version enforcement

The CI gate (`scripts/check_compatibility.py`) validates:

1. All tool schemas have version metadata in the contract document
2. No tool is removed without completing the deprecation window
3. Deprecated tools have a documented replacement
4. The `X-Deprecated-Tool` header spec is present for deprecated tools

### Waiver process

If a release must proceed despite a compatibility violation:

1. Document the waiver in `DECISION_LOG.md` with tool name, justification, and expiry
2. Add the tool name to `scripts/compatibility_waivers.txt`
3. The CI gate reads the waiver file and excludes listed tools from checks
4. Waivers must be cleaned up after expiry

---

## Release Checklist

Before any release that modifies tool schemas:

- [ ] Classify all changes as breaking or non-breaking
- [ ] Update contract version in `gateway-mcp-tools.md`
- [ ] If breaking: add deprecation headers and aliases
- [ ] If breaking: document compatibility window start date
- [ ] Run `python scripts/check_compatibility.py` and verify exit 0
- [ ] Update `CHANGELOG.md` with schema changes
- [ ] If database migration added: test against fresh and existing databases
