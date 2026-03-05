# CG_MCP_v3 -- Phase 2: Provider-Agnostic Location Index

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md
prior_cycle: CG_MCP_v1 (Phase 1 -- Gateway as First-Class MCP Server, CLOSED)
prior_version: CG_MCP_v2
implementation_repo: C:\gh_src\rmembr

---

## Audit Resolution Map

| # | Required Change (from AUDIT_CG_MCP_v2.md) | How Addressed | Sections Modified |
|---|-------------------------------------------|---------------|-------------------|
| 1 | Normalize `provider_name` migration semantics to one authoritative definition | Standardized on: `provider_name VARCHAR nullable, no default (NULL)`. Legacy rows remain NULL; application code sets `provider_name` on all new inserts. | Section A (Files to modify #3), Section A (Order of operations step 7), Section B (Rollback strategy), Section C (Closure artifacts #5, #7), Section D (point 3), Spec Completeness Gate |
| 2 | Update all dependent claims to match (Risk Surface, Spec Gate, validation expectations) | All references now consistently state nullable + no default. Closure artifact #5 updated to expect NULL for pre-existing rows and provider_name populated for newly ingested rows. | Section B (Risk Surface table row 3), Section C (Closure artifacts), Section D (point 3), Spec Completeness Gate |

---

## Scope

This cycle covers **Phase 2** from the source proposal: introducing a `LocationProvider` interface to the rMEMbr Index service so that repository discovery, document enumeration, and content fetching are abstracted behind a pluggable provider contract. The current filesystem-based ingestion becomes the first provider implementation.

### Current state of the Index service (confirmed via codebase read)

The Index service is a **FastAPI HTTP service** at `rmembr/mcp-memory-local/services/index/src/server.py` (port 8081). It exposes:

- `/tools/index_repo` -- ingest a single repo
- `/tools/index_all` -- ingest all repos under REPOS_ROOT
- `/tools/search_repo_memory` -- semantic vector search
- `/tools/resolve_context` -- ranked context pointers with path boosting

**Current ingestion path** (`services/index/src/ingest.py`):
1. Reads `.ai/memory/**` files from a local filesystem path (`REPOS_ROOT` env var)
2. Parses `manifest.yaml` for metadata (namespace, classification, embedding_model)
3. Chunks markdown/YAML via shared chunker (`services/shared/src/chunking/chunker.py`)
4. Embeds via Ollama (`nomic-embed-text`, 768 dims)
5. Upserts to Postgres with SHA-256 content_hash change detection
6. Deletes stale chunks (present in DB but absent from disk)

**Database schema** (from `services/index/src/migrations.py` and `docs/contracts/location-index-schema.md`):
- `memory_packs` -- per-repo metadata (namespace, repo, pack_version, owners, classification, embedding_model)
- `memory_chunks` -- 27 columns including namespace, repo, path, anchor, heading, chunk_text, embedding (pgvector 768), content_hash, source_kind, metadata_json (JSONB)
- `bundle_cache` -- TTL-based context bundle cache

**What is already provider-agnostic:**
- No ADO, GitHub, or other provider-specific hardcodes exist anywhere
- `metadata_json` JSONB column is explicitly reserved for provider-specific extensions
- `namespace` field provides logical tenant isolation at data layer
- Content_hash-based change detection works regardless of content source
- `source_kind` column distinguishes `repo_memory` from `enterprise_standard`

**What does NOT exist yet:**
- No `LocationProvider` interface or abstract class
- No separation between "discover/enumerate/fetch content" and "chunk/embed/store"
- Ingestion is coupled to local filesystem traversal (`os.listdir`, `pathlib.Path`)
- No stable external IDs beyond filesystem paths
- No re-index workflow that tracks provider-specific version refs for delta detection
- No pluggable provider registration or configuration mechanism

---

## SECTION A -- Execution Plan

### Files to create (in rmembr repo)

| # | Path | Purpose |
|---|------|---------|
| 1 | `services/index/src/providers/__init__.py` | Package init; exports `LocationProvider` protocol and `ProviderRegistry` |
| 2 | `services/index/src/providers/base.py` | `LocationProvider` Protocol class defining the provider contract |
| 3 | `services/index/src/providers/filesystem.py` | `FilesystemProvider` -- extracts current `ingest.py` filesystem traversal into provider interface |
| 4 | `services/index/src/providers/registry.py` | `ProviderRegistry` -- maps provider names to implementations; env-var driven activation |
| 5 | `services/index/src/providers/types.py` | Shared data types: `RepoDescriptor`, `DocumentDescriptor`, `DocumentContent`, `VersionRef` |
| 6 | `tests/providers/test_provider_contract.py` | Contract tests that any `LocationProvider` implementation must pass |
| 7 | `tests/providers/test_filesystem_provider.py` | Unit tests for `FilesystemProvider` against fixture repos |
| 8 | `tests/providers/test_registry.py` | Unit tests for `ProviderRegistry` activation and lookup |
| 9 | `tests/providers/test_ingest_integration.py` | Integration test: provider -> ingest pipeline -> DB, verifying end-to-end flow |
| 10 | `tests/providers/conftest.py` | Shared fixtures: temp repos with `.ai/memory/` structure, mock providers |

### Files to modify (in rmembr repo)

| # | Path | Change |
|---|------|--------|
| 1 | `services/index/src/ingest.py` | Refactor: replace direct filesystem calls with `LocationProvider` calls. The current `index_repo()` and `index_all()` functions accept a provider instance instead of reading REPOS_ROOT directly. |
| 2 | `services/index/src/server.py` | Initialize `ProviderRegistry` in lifespan. Pass provider to ingest functions. Add `ACTIVE_PROVIDERS` env var handling. |
| 3 | `services/index/src/migrations.py` | Add `external_id` and `provider_name` columns to `memory_chunks` table (both nullable, no default). Legacy rows retain NULL for both columns; application code populates them on all new inserts. |
| 4 | `services/index/requirements.txt` | No new dependencies expected (stdlib + existing deps sufficient). |
| 5 | `docker-compose.yml` | Add `ACTIVE_PROVIDERS` env var to index service (default: `filesystem`). |

### LocationProvider Protocol definition

```python
from typing import Protocol, AsyncIterator
from .types import RepoDescriptor, DocumentDescriptor, DocumentContent

class LocationProvider(Protocol):
    """Contract for pluggable content sources."""

    @property
    def name(self) -> str:
        """Provider identifier (e.g., 'filesystem', 'ado', 'github')."""
        ...

    async def enumerate_repos(self) -> AsyncIterator[RepoDescriptor]:
        """Yield all repos available from this provider."""
        ...

    async def enumerate_documents(
        self, repo: RepoDescriptor
    ) -> AsyncIterator[DocumentDescriptor]:
        """Yield all indexable documents in a repo."""
        ...

    async def fetch_content(
        self, doc: DocumentDescriptor
    ) -> DocumentContent:
        """Fetch full content of a document for chunking."""
        ...
```

### Shared data types

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RepoDescriptor:
    namespace: str          # Tenant isolation key
    repo: str               # Logical repo name
    provider_name: str      # Source provider (filesystem, ado, github)
    external_id: str        # Provider-stable ID (path, ADO repo ID, GitHub full_name)
    version_ref: Optional[str] = None  # Branch/tag/commit for delta detection
    metadata: Optional[dict] = None    # Provider-specific (flows to metadata_json)

@dataclass(frozen=True)
class DocumentDescriptor:
    repo: RepoDescriptor
    path: str               # Relative path within repo
    anchor: Optional[str]   # Stable sub-document anchor (heading slug)
    external_id: str        # Provider-stable doc ID
    version_ref: Optional[str] = None  # File-level version for delta detection
    content_hash: Optional[str] = None # Pre-computed hash if provider supports it

@dataclass(frozen=True)
class DocumentContent:
    doc: DocumentDescriptor
    text: str               # Full content for chunking
    content_hash: str       # SHA-256 of text
    metadata: Optional[dict] = None  # Additional metadata from provider
```

### ProviderRegistry

```python
class ProviderRegistry:
    """Maps provider names to implementations. Configured via ACTIVE_PROVIDERS env var."""

    _providers: dict[str, LocationProvider]

    def __init__(self):
        self._providers = {}

    def register(self, provider: LocationProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> LocationProvider:
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        return self._providers[name]

    def active_providers(self) -> list[LocationProvider]:
        """Return providers activated by ACTIVE_PROVIDERS env var."""
        active = os.environ.get("ACTIVE_PROVIDERS", "filesystem").split(",")
        return [self._providers[n.strip()] for n in active if n.strip() in self._providers]
```

### Minimal safe change strategy

1. **Refactor before extending.** Extract filesystem-specific logic from `ingest.py` into `FilesystemProvider`. The refactored `ingest.py` accepts a `LocationProvider` instance. Existing behavior is unchanged -- `FilesystemProvider` is the only active provider and the default.

2. **Additive schema migration.** New columns (`external_id`, `provider_name`) are both nullable with no default. No existing rows break. Legacy rows retain NULL for both columns. Application code sets `provider_name` on all new inserts. The migration is applied via the existing `migrations.py` pattern (CREATE TABLE IF NOT EXISTS / ALTER TABLE ADD COLUMN IF NOT EXISTS).

3. **Feature-flagged provider selection.** `ACTIVE_PROVIDERS` env var (default: `filesystem`). Only registered and activated providers run during `index_all`. Unknown provider names log a warning and are skipped.

4. **No new external dependencies.** The `LocationProvider` protocol uses `typing.Protocol` (stdlib). No new pip packages required.

5. **Backward-compatible API.** The MCP/HTTP tool signatures (`index_repo`, `index_all`, `search_repo_memory`) do not change. Provider selection is internal to the Index service.

### Order of operations

1. **Add provider types** -- Create `providers/types.py` with `RepoDescriptor`, `DocumentDescriptor`, `DocumentContent` dataclasses.

2. **Define provider protocol** -- Create `providers/base.py` with `LocationProvider` Protocol.

3. **Implement FilesystemProvider** -- Create `providers/filesystem.py`. Extract filesystem traversal logic from `ingest.py:index_repo()` and `ingest.py:index_all()` into the provider methods. This is the highest-risk step.

4. **Implement ProviderRegistry** -- Create `providers/registry.py` with env-var-driven activation.

5. **Refactor ingest.py** -- Replace direct filesystem calls with provider calls. `index_repo(provider, repo_name, namespace)` becomes `index_repo(repo_descriptor)` using provider to enumerate documents and fetch content. Chunking, embedding, and upsert logic stays in `ingest.py`.

6. **Update server.py** -- Initialize `ProviderRegistry` in lifespan (alongside DB pool and HTTP clients). Register `FilesystemProvider`. Pass active providers to ingest functions.

7. **Schema migration** -- Add `external_id` (VARCHAR, nullable, no default) and `provider_name` (VARCHAR, nullable, no default) to `memory_chunks`. Add composite index on `(provider_name, external_id)`. Legacy rows retain NULL; application code populates both columns on all new inserts.

8. **Update docker-compose** -- Add `ACTIVE_PROVIDERS=filesystem` env var to index service.

9. **Write tests** -- Contract tests, filesystem provider tests, registry tests, integration tests (files 6-10 above).

10. **Validate** -- Run full test suite including existing contract tests to confirm no regression.

### Deployment steps

1. Merge behind `ACTIVE_PROVIDERS=filesystem` (behavioral no-op -- same as current).
2. Run existing contract tests + new provider tests.
3. Run `index_all` via MCP/HTTP and verify identical DB state (content_hash comparison).
4. Verify new `external_id` and `provider_name` columns populated for new ingestions; legacy rows retain NULL for both columns.

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Ingest refactor introduces regression in indexing behavior | Medium | High | Run existing contract tests and manual `index_all` comparison before/after. Content_hash-based comparison ensures identical chunks. |
| FilesystemProvider does not perfectly replicate current traversal order or filtering | Medium | Medium | Unit tests compare provider output against known fixture repos. Order does not affect correctness (upsert is idempotent by content_hash). |
| Schema migration fails on existing Postgres with data | Low | High | Migration uses `ALTER TABLE ADD COLUMN IF NOT EXISTS` (idempotent). New columns are nullable with no default. No existing data modified. Adding nullable columns with no default is a metadata-only operation in Postgres -- no table rewrite. |
| Provider protocol too rigid -- blocks future ADO/GitHub implementation | Medium | Medium | Protocol uses AsyncIterator (lazy enumeration). `metadata` dict on descriptors is the escape hatch for provider-specific data. Review against known ADO API shape. |
| asyncpg pool exhaustion if provider enumeration is slow | Low | Medium | Provider calls are external to DB pool. Only chunking/embedding/upsert uses DB. No change to pool sizing. |
| PYTHONPATH issues with new `providers/` subpackage | Low | Low | Dockerfile already sets `PYTHONPATH="/app/shared/src:/app/index"`. New package is under `index/src/providers/`, already covered. Verify in container. |

### Hidden dependencies

- **Ingest.py internal structure.** The refactor assumes `ingest.py` has clean function boundaries. If filesystem logic is deeply interleaved with chunking/embedding logic, extraction is harder. (Exploration confirms `ingest.py` has a clear top-level flow: read files -> chunk -> embed -> upsert, so extraction is feasible.)
- **Manifest.yaml coupling.** The `FilesystemProvider` must read `manifest.yaml` to populate `RepoDescriptor` metadata. Future providers (ADO, GitHub) will have different metadata sources. The provider interface must not assume manifest.yaml exists.
- **Shared chunker dependency.** Chunking stays in `ingest.py`, not in the provider. Provider only delivers raw content. This is intentional -- chunking strategy should be provider-independent.

### Rollback strategy

Per CONSTITUTION.md v0.4:

1. **Feature flag rollback:** Set `ACTIVE_PROVIDERS=filesystem` (already the default). No behavior change.
2. **Code rollback:** `git revert` the provider commits. New files are deleted. The only modified existing files are `ingest.py`, `server.py`, and `migrations.py`. `ingest.py` and `server.py` revert cleanly. Migration adds nullable columns (no default) that remain harmless if code is reverted -- NULL values in unused columns have no operational impact.
3. **Schema rollback:** `external_id` and `provider_name` columns are nullable with no default and unused by existing code post-revert. They can remain (harmless) or be dropped via manual `ALTER TABLE DROP COLUMN` if needed. Rollback time: ~5 min for code revert, ~2 min for docker compose restart.

---

## SECTION C -- Validation Steps

### Acceptance criteria (from source proposal Phase 2)

1. Index can ingest from at least two providers via the same interface (filesystem + a mock/test provider).
2. A single repo logical identity can be mapped to provider-specific identifiers.
3. No retrieval logic depends on provider-specific path parsing.
4. Canonical location/index records are tenant-scoped by design (namespace required key).

### Closure artifacts required

1. **Ingest refactor regression pass:** Existing `tests/contracts/` tests pass after `ingest.py` refactor.
2. **Provider contract tests pass:** `test_provider_contract.py` validates `LocationProvider` protocol compliance for `FilesystemProvider` and a `MockProvider`.
3. **FilesystemProvider unit tests pass:** Fixture repos produce expected `RepoDescriptor` and `DocumentDescriptor` outputs.
4. **Registry tests pass:** Provider activation via `ACTIVE_PROVIDERS` env var works correctly.
5. **Integration test pass:** Full pipeline (provider -> ingest -> DB) produces correct `memory_chunks` rows with `external_id` and `provider_name` populated for newly ingested rows. Pre-existing legacy rows retain NULL for both columns.
6. **Parity verification:** `index_all` via refactored code produces identical chunk content_hashes as pre-refactor code.
7. **Schema migration verified:** New columns exist, are nullable with no default, and are queryable after migration. Legacy rows confirmed to have NULL for both `external_id` and `provider_name`.

### Exact commands to produce closure artifacts

```bash
# All commands run from rmembr/mcp-memory-local/ with services up via docker compose

# 1. Regression -- existing contract tests
python -m pytest tests/contracts/validate_tool_schemas.py -v
python -m pytest tests/contracts/test_negative_payloads.py -v
python -m pytest tests/contracts/test_deprecation_warnings.py -v

# 2. Provider contract tests
python -m pytest tests/providers/test_provider_contract.py -v

# 3. FilesystemProvider unit tests
python -m pytest tests/providers/test_filesystem_provider.py -v

# 4. Registry tests
python -m pytest tests/providers/test_registry.py -v

# 5. Integration test (requires running services)
docker compose up -d
python -m pytest tests/providers/test_ingest_integration.py -v

# 6. Parity verification (manual or scripted)
# Run index_all before and after refactor, compare content_hashes:
# Before: capture SELECT repo, path, anchor, content_hash FROM memory_chunks ORDER BY repo, path, anchor;
# After:  run same query, diff output. Zero differences expected.

# 7. Schema migration verification
docker compose exec postgres psql -U rmembr -d rmembr -c "\d memory_chunks" | grep -E "external_id|provider_name"
# Verify: both columns show as nullable with no default
# Verify legacy rows: SELECT COUNT(*) FROM memory_chunks WHERE provider_name IS NULL;
```

---

## SECTION D -- Auditor Sensitivity

1. **Ingest refactor risk.** Modifying `ingest.py` to accept a provider instead of reading the filesystem directly is the highest-risk change. Auditor will verify the refactor preserves all existing behavior (file filtering, manifest parsing, chunk deduplication, stale chunk deletion). Mitigation: parity verification artifact (closure #6) compares content_hashes before/after.

2. **Protocol design adequacy.** Auditor may question whether the `LocationProvider` protocol is sufficient for ADO/GitHub providers that have pagination, rate limiting, and authentication requirements. Mitigation: `AsyncIterator` supports lazy/paginated enumeration. Auth is provider-internal (not part of the protocol). Rate limiting is provider-internal. `metadata` dict on descriptors provides escape hatch. The protocol intentionally does NOT try to solve auth/rate-limiting generically.

3. **Schema migration safety.** Adding columns to a table with existing data. Auditor will verify: nullable columns, no default value, no NOT NULL constraint, idempotent migration. Mitigation: `ALTER TABLE ADD COLUMN IF NOT EXISTS` with nullable columns and no default. Adding nullable columns without a default is a metadata-only operation in Postgres -- no table rewrite, no lock escalation. Legacy rows retain NULL; application code populates values on new inserts.

4. **Tenant isolation preservation.** `namespace` is the tenant isolation key. Auditor will verify that the provider refactor does not bypass namespace filtering in queries or allow cross-namespace data access. Mitigation: `RepoDescriptor` requires `namespace`. Existing query filters in `search.py` and `ingest.py` are unchanged.

5. **No new external dependencies.** Auditor should confirm no new pip packages are added. `typing.Protocol` is stdlib. `dataclasses` is stdlib. This is purely a structural refactor.

6. **Test coverage breadth.** Auditor will check that contract tests cover both `FilesystemProvider` and at least one mock/test provider to validate the interface is genuinely pluggable (not just a wrapper around the filesystem implementation). Mitigation: `test_provider_contract.py` runs the same contract suite against both `FilesystemProvider` and `MockProvider`.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined -- `RepoDescriptor` (6 fields: namespace str required, repo str required, provider_name str required, external_id str required, version_ref str optional, metadata dict optional), `DocumentDescriptor` (6 fields: repo RepoDescriptor required, path str required, anchor str optional, external_id str required, version_ref str optional, content_hash str optional), `DocumentContent` (4 fields: doc DocumentDescriptor required, text str required, content_hash str required, metadata dict optional). New DB columns: `external_id` VARCHAR nullable no default, `provider_name` VARCHAR nullable no default. Legacy rows retain NULL; application code sets both on new inserts.
- [x] All boundary conditions named -- `ACTIVE_PROVIDERS` env var (default: `filesystem`, comma-separated); unknown provider names logged and skipped; `external_id` max length follows existing VARCHAR limits; `provider_name` constrained to registered provider names at runtime; manifest.yaml required for `FilesystemProvider` (consistent with current behavior); empty repos (no `.ai/memory/` dir) produce zero documents (current behavior preserved).
- [x] All behavioral modes specified -- standard (filesystem provider active, `ACTIVE_PROVIDERS=filesystem`), multi-provider (multiple comma-separated providers active), degraded (provider raises exception during enumeration -> logged, skipped, other providers continue), no-provider (empty `ACTIVE_PROVIDERS` -> `index_all` is no-op with warning log).
- [x] Rollback procedure cites current CONSTITUTION.md version -- CONSTITUTION.md v0.4; rollback via `git revert` (new files deleted, modified files restored); nullable schema columns (no default) harmless if code reverted; feature flag `ACTIVE_PROVIDERS=filesystem` is behavioral no-op.
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at `governance/CONSTITUTION.md` (confirmed v0.4), providers.md at `governance/providers.md` (confirmed version 1.3), source proposal at `governance/proposals/context-gateway-mcp-full-alignment-plan.md` (Phase 2 section confirmed), Phase 0 contracts at `rmembr/docs/contracts/location-index-schema.md` (confirmed schema definitions), prior cycle at `governance/plans/CG_MCP/CG_MCP_v1.md` (confirmed CLOSED via closure artifact).

READY FOR AUDITOR REVIEW
