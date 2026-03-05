# CG_MCP_v6 -- Phase 3: Retrieval Engine Separation and Normalization

governance_constitution_version: v0.4
governance_providers_version: 1.3
governance_mode: FULL
source_proposal: governance/proposals/context-gateway-mcp-full-alignment-plan.md
prior_cycle: CG_MCP_v3 (Phase 2 -- Provider-Agnostic Location Index, CLOSED)
prior_version: CG_MCP_v5
implementation_repo: C:\gh_src\rmembr

---

## Audit Resolution Map

| # | Required Change (AUDIT_CG_MCP_v5) | How Addressed | Location in v5 |
|---|-------------------------------------|---------------|-----------------|
| 1 | Section A "Files to modify" omits `docker-compose` while "Order of operations" step 8 plans to modify it -- declared scope and execution steps must match | Added `mcp-memory-local/docker-compose.yml` as row #4 in "Files to modify" table with change description matching step 8 | Section A, "Files to modify" table |

---

## Scope

This cycle covers **Phase 3** from the source proposal: separating retrieval into an explicit module boundary within the Index service, normalizing search results into a provenance-rich chunk model, and introducing configurable ranking pipeline stages.

### Current state of retrieval (confirmed via codebase read)

Retrieval is currently handled by two functions in `services/index/src/search.py`:

- `search_repo_memory()` -- vector similarity search via pgvector, returns flat dicts with `id`, `path`, `anchor`, `heading`, `snippet`, `source_kind`, `classification`, `similarity`
- `resolve_context()` -- wraps `search_repo_memory()` with optional `changed_files` path boosting (+0.1 similarity bonus), returns same flat dict structure

**Gateway's current retrieval flow** (`services/gateway/src/server.py`):
1. Calls Index `/tools/resolve_context` via HTTP
2. Receives flat chunk dicts (no provenance, no provider info, no score breakdown)
3. Applies classification filtering by persona
4. Assigns priority classes (enterprise_must_follow, repo_must_follow, task_specific)
5. Deterministic sort by priority class -> similarity -> path
6. Applies size budget truncation
7. Assembles bundle with standards content

**What does NOT exist yet:**
- No provenance metadata in search results (provider_name, external_id, revision are in DB but not returned)
- No score component breakdown (only final similarity float)
- No configurable ranking pipeline -- path boost is hardcoded in `resolve_context()`
- No common chunk DTO/model -- results are ad-hoc dicts
- No separation between "find matching chunks" and "rank/score them"
- No lexical prefilter stage
- No freshness boost (only path boost exists)

**What already exists and should be preserved:**
- pgvector HNSW cosine similarity search works correctly
- Content-hash change detection (ingestion side, not retrieval)
- `provider_name` and `external_id` columns exist in `memory_chunks` (from Phase 2)
- Gateway classification filtering, priority classification, budget controls work correctly
- Bundle caching in gateway works correctly

---

## SECTION A -- Execution Plan

### Files to create (in rmembr repo)

| # | Path | Purpose |
|---|------|---------|
| 1 | `services/index/src/retrieval/__init__.py` | Package init; exports `RetrievalEngine`, `RetrievalResult`, `ScoreComponents`, `RankingConfig` |
| 2 | `services/index/src/retrieval/types.py` | Normalized chunk model: `RetrievalResult`, `ScoreComponents`, `ProvenanceInfo`, `RankingConfig` |
| 3 | `services/index/src/retrieval/engine.py` | `RetrievalEngine` class: orchestrates search -> rank -> normalize pipeline |
| 4 | `services/index/src/retrieval/ranker.py` | Ranking pipeline: semantic score, path boost, freshness boost, configurable stage weights |
| 5 | `tests/retrieval/__init__.py` | Test package init |
| 6 | `tests/retrieval/test_types.py` | Unit tests for retrieval DTOs and serialization |
| 7 | `tests/retrieval/test_engine.py` | Unit tests for RetrievalEngine with mock DB pool |
| 8 | `tests/retrieval/test_ranker.py` | Unit tests for ranking pipeline stages and configurability |
| 9 | `tests/retrieval/test_integration.py` | Integration test: engine -> DB -> ranked results with provenance |
| 10 | `tests/retrieval/test_fault_paths.py` | Fault-path tests: timeout/degraded-index scenarios yield partial well-formed responses |

### Files to modify (in rmembr repo)

| # | Path | Change |
|---|------|--------|
| 1 | `services/index/src/search.py` | Refactor: replace ad-hoc dict returns with `RetrievalResult` DTOs. `search_repo_memory()` returns results with provenance. `resolve_context()` uses `RetrievalEngine` for ranking. Existing function signatures preserved for backward compatibility -- same parameters, richer return type (dicts now include provenance fields). |
| 2 | `services/index/src/server.py` | Initialize `RetrievalEngine` in lifespan. Pass to search functions. Add `RANKING_CONFIG` env var handling. Update `/tools/search_repo_memory` and `/tools/resolve_context` response shapes to include provenance. |
| 3 | `services/gateway/src/server.py` | Consume new provenance fields from Index responses. Include `provider_name`, `external_id`, `score_components` in bundle chunks. Update `_render_markdown()` to show provenance. |
| 4 | `mcp-memory-local/docker-compose.yml` | Add `RANKING_PATH_BOOST`, `RANKING_FRESHNESS_BOOST`, `RANKING_FRESHNESS_WINDOW_HOURS` env vars to index service with current-behavior defaults (0.1, 0.0, 168 respectively). |

### Normalized chunk model (RetrievalResult)

```python
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass(frozen=True)
class ScoreComponents:
    """Breakdown of how the final score was computed."""
    semantic: float           # Raw cosine similarity (0.0-1.0)
    path_boost: float = 0.0   # Boost from changed_files match
    freshness_boost: float = 0.0  # Boost from recency of update

    @property
    def final(self) -> float:
        return min(1.0, self.semantic + self.path_boost + self.freshness_boost)

@dataclass(frozen=True)
class ProvenanceInfo:
    """Origin tracking for a retrieved chunk."""
    provider_name: Optional[str] = None   # e.g., 'filesystem', 'ado'
    external_id: Optional[str] = None     # Provider-stable ID
    content_hash: str = ""                # SHA-256 of chunk content
    indexed_at: Optional[str] = None      # ISO timestamp of last index

@dataclass(frozen=True)
class RetrievalResult:
    """Normalized chunk returned by the retrieval engine."""
    id: int
    path: str
    anchor: str
    heading: str
    snippet: str                          # chunk_text[:500]
    source_kind: str                      # 'repo_memory' or 'enterprise_standard'
    classification: str                   # 'public', 'internal'
    score: ScoreComponents
    provenance: ProvenanceInfo

    def to_dict(self) -> dict:
        """Serialize to dict for JSON response."""
        d = asdict(self)
        d["similarity"] = self.score.final  # Backward compat
        d["score_components"] = asdict(self.score)
        d["provenance"] = asdict(self.provenance)
        return d
```

### RankingConfig

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RankingConfig:
    """Configurable weights for ranking pipeline stages."""
    path_boost_weight: float = 0.1        # Boost for changed_files match
    freshness_boost_weight: float = 0.0   # Boost for recently updated chunks (0 = disabled)
    freshness_window_hours: int = 168     # 7 days -- chunks updated within window get boost

    @classmethod
    def from_env(cls) -> "RankingConfig":
        """Load config from environment variables."""
        import os
        return cls(
            path_boost_weight=float(os.environ.get("RANKING_PATH_BOOST", "0.1")),
            freshness_boost_weight=float(os.environ.get("RANKING_FRESHNESS_BOOST", "0.0")),
            freshness_window_hours=int(os.environ.get("RANKING_FRESHNESS_WINDOW_HOURS", "168")),
        )
```

### RetrievalEngine

```python
class RetrievalEngine:
    """Orchestrates search -> rank -> normalize pipeline."""

    def __init__(self, config: RankingConfig):
        self.config = config
        self._ranker = Ranker(config)

    async def search(
        self,
        pool,
        repo: str,
        query: str,
        k: int = 8,
        ref: str = "local",
        namespace: str = "default",
        filters: dict | None = None,
        changed_files: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Execute search and return normalized, ranked results."""
        # 1. Embed query
        query_embedding = await embed_query(query)

        # 2. Fetch raw candidates from DB (with provenance columns)
        raw_rows = await self._fetch_candidates(
            pool, repo, query_embedding, k, ref, namespace, filters
        )

        # 3. Normalize into RetrievalResult DTOs
        results = [self._normalize(row) for row in raw_rows]

        # 4. Apply ranking pipeline
        ranked = self._ranker.rank(results, changed_files=changed_files)

        # 5. Return top-k after ranking
        return ranked[:k]

    async def _fetch_candidates(self, pool, repo, embedding, k, ref, namespace, filters):
        """Fetch candidate chunks from DB with provenance columns."""
        # Same SQL as current search.py but also SELECT provider_name, external_id, content_hash, updated_at
        ...

    def _normalize(self, row) -> RetrievalResult:
        """Convert DB row to RetrievalResult."""
        ...
```

### Ranker

```python
class Ranker:
    """Configurable ranking pipeline with discrete stages."""

    def __init__(self, config: RankingConfig):
        self.config = config

    def rank(
        self,
        results: list[RetrievalResult],
        changed_files: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Apply ranking stages and return sorted results."""
        ranked = []
        for r in results:
            path_boost = self._path_boost(r, changed_files)
            freshness_boost = self._freshness_boost(r)
            score = ScoreComponents(
                semantic=r.score.semantic,
                path_boost=path_boost,
                freshness_boost=freshness_boost,
            )
            ranked.append(RetrievalResult(
                id=r.id, path=r.path, anchor=r.anchor, heading=r.heading,
                snippet=r.snippet, source_kind=r.source_kind,
                classification=r.classification, score=score,
                provenance=r.provenance,
            ))
        ranked.sort(key=lambda r: r.score.final, reverse=True)
        return ranked

    def _path_boost(self, result: RetrievalResult, changed_files: list[str] | None) -> float:
        if not changed_files:
            return 0.0
        for cf in changed_files:
            if cf in result.path:
                return self.config.path_boost_weight
        return 0.0

    def _freshness_boost(self, result: RetrievalResult) -> float:
        if self.config.freshness_boost_weight == 0.0:
            return 0.0
        # Compare result.provenance.indexed_at against freshness window
        ...
```

### Minimal safe change strategy

1. **New module, additive.** All retrieval logic goes into a new `retrieval/` package. Existing `search.py` functions are updated to delegate to `RetrievalEngine` but preserve their external call signatures. No existing function is removed.

2. **Backward-compatible response enrichment.** Index HTTP endpoints return the same fields as before PLUS new `provenance` and `score_components` fields. Gateway and any external callers that ignore unknown fields are unaffected.

3. **Default-off freshness boost.** `RANKING_FRESHNESS_BOOST=0.0` by default. Path boost defaults to 0.1 (matching current hardcoded behavior). Current ranking behavior is exactly preserved unless env vars are explicitly changed.

4. **No schema migrations.** All required DB columns (`provider_name`, `external_id`, `content_hash`, `updated_at`) already exist from Migrations 1 and 2. Retrieval only reads existing columns -- no DDL changes.

5. **No new external dependencies.** Uses stdlib `dataclasses`, `typing`. No new pip packages.

6. **Gateway changes are consumption-only.** Gateway reads new fields from Index responses and passes them through to bundle output. No new Gateway business logic.

### Order of operations

1. **Create retrieval types** -- `retrieval/types.py` with `ScoreComponents`, `ProvenanceInfo`, `RetrievalResult`, `RankingConfig` dataclasses.

2. **Create ranker** -- `retrieval/ranker.py` with `Ranker` class implementing path_boost, freshness_boost stages.

3. **Create retrieval engine** -- `retrieval/engine.py` with `RetrievalEngine` class. Extracts DB query from `search.py`, adds provenance column reads, delegates to ranker.

4. **Create package init** -- `retrieval/__init__.py` exporting public API.

5. **Refactor search.py** -- `search_repo_memory()` delegates to `RetrievalEngine.search()`, converts results back to dicts (preserving backward compat). `resolve_context()` delegates to `RetrievalEngine.search(changed_files=...)`.

6. **Update server.py (Index)** -- Initialize `RetrievalEngine` in lifespan with `RankingConfig.from_env()`. Pass to search functions. Update response shapes to include provenance/score_components.

7. **Update server.py (Gateway)** -- Consume new provenance fields from Index responses. Pass through to bundle chunks. Update `_render_markdown()` to include provenance info.

8. **Update docker-compose** -- Add `RANKING_PATH_BOOST`, `RANKING_FRESHNESS_BOOST`, `RANKING_FRESHNESS_WINDOW_HOURS` env vars to index service in `mcp-memory-local/docker-compose.yml` (all with current-behavior defaults).

9. **Write tests** -- Types tests, ranker tests, engine tests, integration tests, fault-path tests (files 6-10 above).

10. **Validate** -- Run full test suite including existing contract tests to confirm no regression.

### Deployment steps

1. Merge with default ranking config (behavioral no-op -- path boost 0.1 matches current, freshness boost 0.0 = disabled).
2. Run existing contract tests + new retrieval tests.
3. Run `search_repo_memory` and `resolve_context` via HTTP and verify results include provenance fields and score_components.
4. Verify gateway bundles include provenance info for each chunk.
5. Compare top-k ordering before/after to confirm ranking parity.

---

## SECTION B -- Risk Surface

### What could break

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| search.py refactor introduces regression in result ordering | Medium | High | Default `RankingConfig` exactly replicates current behavior (path_boost=0.1, freshness=0.0). Parity test compares result ordering before/after. |
| Gateway breaks on new response fields | Low | Medium | New fields are additive. Gateway already uses `.get()` for optional fields. Integration test verifies end-to-end. |
| RetrievalResult.to_dict() serialization differs from current dicts | Medium | Medium | `to_dict()` includes `similarity` key for backward compat. Contract tests validate response shape. |
| Freshness boost causes unexpected ranking changes when enabled | Low | Medium | Freshness boost is disabled by default (`RANKING_FRESHNESS_BOOST=0.0`). Only activates via explicit env var. |
| Performance regression from additional SELECT columns | Low | Low | Adding 4 columns to SELECT does not meaningfully affect query plan. HNSW index drives performance. |
| Circular import between search.py and retrieval/ | Low | Low | RetrievalEngine is self-contained. search.py imports from retrieval/ but not vice versa. |
| Index timeout or degraded DB returns malformed response | Low | Medium | Fault-path tests (closure #9) verify partial results are well-formed `RetrievalResult` DTOs even under degraded conditions. Engine returns whatever valid results it has before timeout. |

### Hidden dependencies

- **search.py callers.** Both `server.py` (Index) endpoints and `resolve_context()` call `search_repo_memory()`. The refactor must preserve the call chain: `resolve_context()` -> `search_repo_memory()` is replaced by `resolve_context()` -> `RetrievalEngine.search(changed_files=...)`.
- **Gateway response parsing.** Gateway's `handle_get_context_bundle()` reads `pointers` from Index response and applies its own filtering/sorting. New provenance fields must flow through without breaking the gateway pipeline functions (`_filter_by_classification`, `_classify_chunk`, `_deterministic_sort`, `_apply_budget`).
- **MCP tool schemas.** `mcp_tools.py` defines response schemas for `search_repo_memory` and `resolve_context`. New fields are additive -- existing schemas remain valid. No schema version bump required since new fields are optional extensions.
- **Bundle explain.** `explain_context_bundle` reads stored bundle JSON. New provenance fields will appear in new bundles but old cached bundles will not have them. `explain_context_bundle` must handle both gracefully (already does via `.get()`).

### Rollback strategy

Per CONSTITUTION.md v0.4:

1. **Config rollback:** Ranking config env vars have defaults matching current behavior. Removing them is a no-op.
2. **Code rollback:** `git revert` the retrieval commits. New `retrieval/` directory is deleted. `search.py` and `server.py` revert to prior state. Gateway reverts to ignoring provenance fields. No schema changes to revert.
3. **No schema rollback needed.** No DDL changes in this cycle. All columns already exist.
4. **Rollback time:** ~5 min for code revert, ~2 min for docker compose restart.

---

## SECTION C -- Validation Steps

### Acceptance criteria (from source proposal Phase 3)

1. Retrieval accepts location references from index without direct provider calls from gateway.
2. Returned chunks include full provenance metadata.
3. Ranking behavior is configurable and test-covered.

### Closure artifacts required

1. **Regression pass:** Existing `tests/contracts/` tests pass after `search.py` refactor.
2. **Retrieval types tests pass:** `test_types.py` validates `RetrievalResult`, `ScoreComponents`, `ProvenanceInfo` creation, serialization, and backward-compat `similarity` field.
3. **Ranker tests pass:** `test_ranker.py` validates path_boost, freshness_boost stages with configurable weights, and default behavior matching current implementation.
4. **Engine tests pass:** `test_engine.py` validates end-to-end search -> rank -> normalize pipeline with mock DB pool.
5. **Integration test pass:** `test_integration.py` validates full pipeline (engine -> DB -> ranked results with provenance) against running services.
6. **Provenance verification:** `search_repo_memory` response includes `provenance.provider_name`, `provenance.external_id`, `provenance.content_hash`, `provenance.indexed_at` for each result.
7. **Ranking parity:** Default config produces identical top-k ordering as pre-refactor code for same query/repo/ref.
8. **Gateway bundle provenance:** `get_context_bundle` response chunks include provenance fields.
9. **Fault-path validation:** `test_fault_paths.py` proves that when the DB pool times out or returns partial results, `RetrievalEngine.search()` returns a well-formed (possibly empty) `list[RetrievalResult]` rather than raising an unhandled exception or returning malformed data. Pass criteria: (a) DB connection timeout (simulated via mock raising `asyncpg.PostgresConnectionError` or `asyncio.TimeoutError`) -> engine returns `[]` and logs warning; (b) DB returns fewer rows than requested `k` -> engine returns all available rows as valid `RetrievalResult` DTOs with complete provenance fields (nullable fields may be None); (c) response JSON schema is identical whether 0, 1, or k results are returned.
10. **Ranking reproducibility:** For a fixed dataset and query, two consecutive calls to `RetrievalEngine.search()` with identical parameters and default `RankingConfig` produce **exactly identical** top-k ordering (same IDs in same positions). Tolerance: zero -- exact match required (ranking is deterministic given deterministic input). Procedure: (a) before refactor, run `scripts/capture_ranking_baseline.sh` which calls `POST /tools/search_repo_memory` with 3 canonical queries against the test dataset and writes `{query_hash, result_ids[]}` tuples to `tests/retrieval/fixtures/ranking_baseline.json`; (b) after refactor, `test_engine.py::test_ranking_reproducibility` loads the baseline fixture, executes the same queries with default config, and asserts `result_ids` match exactly; (c) if a tie-breaking ambiguity exists (two chunks with identical `score.final` AND identical `path`), the test sorts tied entries by `id` ascending before comparison to ensure stable ordering.

### Exact commands to produce closure artifacts

```bash
# All commands run from rmembr/ with services up via docker compose

# 1. Regression -- existing contract tests
python -m pytest tests/contracts/validate_tool_schemas.py -v
python -m pytest tests/contracts/test_negative_payloads.py -v
python -m pytest tests/contracts/test_deprecation_warnings.py -v

# 2. Retrieval types tests
python -m pytest tests/retrieval/test_types.py -v

# 3. Ranker tests
python -m pytest tests/retrieval/test_ranker.py -v

# 4. Engine tests
python -m pytest tests/retrieval/test_engine.py -v

# 5. Integration test (requires running services)
docker compose up -d
python -m pytest tests/retrieval/test_integration.py -v

# 6. Provenance verification (manual or scripted)
curl -s -X POST http://localhost:8081/tools/search_repo_memory \
  -H "Content-Type: application/json" \
  -d '{"repo":"test-repo","query":"test","k":3}' | python -m json.tool
# Verify: each result has provenance.provider_name, provenance.external_id,
# provenance.content_hash, provenance.indexed_at fields

# 7. Ranking parity (manual comparison)
# Before refactor: capture search_repo_memory results for a known query
# After refactor: run same query with default config, compare ordering

# 8. Gateway bundle provenance
curl -s -X POST http://localhost:8080/tools/get_context_bundle \
  -H "Content-Type: application/json" \
  -d '{"repo":"test-repo","task":"test task"}' | python -m json.tool
# Verify: bundle chunks include provenance fields

# 9. Fault-path validation
python -m pytest tests/retrieval/test_fault_paths.py -v
# Pass criteria:
#   - test_db_connection_timeout: engine returns [] on asyncio.TimeoutError
#   - test_db_partial_results: engine returns valid DTOs when fewer than k rows
#   - test_empty_result_schema: JSON schema identical for 0, 1, k results

# 10. Ranking reproducibility
# Before refactor (baseline capture):
bash scripts/capture_ranking_baseline.sh
# After refactor (automated comparison):
python -m pytest tests/retrieval/test_engine.py::test_ranking_reproducibility -v
# Pass criteria: exact match of result IDs in order for all 3 canonical queries
```

---

## SECTION D -- Auditor Sensitivity

1. **search.py refactor fidelity.** Modifying `search.py` to delegate to `RetrievalEngine` is the highest-risk change. Auditor will verify that the refactored path produces identical results for the default config. Mitigation: ranking parity test (closure #7) and ranking reproducibility test (closure #10) compare result ordering before/after with default config.

2. **Backward compatibility of response shape.** Auditor will verify that existing callers (Gateway, MCP tools) are not broken by new fields in search responses. Mitigation: new fields are additive. `similarity` key preserved via `RetrievalResult.to_dict()`. Gateway uses `.get()` for all chunk fields.

3. **Ranking configurability scope.** Auditor may question whether the ranking config surface is sufficient or too broad. Mitigation: only 3 env vars (`RANKING_PATH_BOOST`, `RANKING_FRESHNESS_BOOST`, `RANKING_FRESHNESS_WINDOW_HOURS`). All default to current behavior. No dynamic/runtime config -- only env var at startup.

4. **Provenance data completeness.** Auditor will verify that provenance fields are populated from existing DB columns, not fabricated. Mitigation: `provider_name`, `external_id` come from Phase 2 columns. `content_hash` already stored. `updated_at` is existing timestamp column. All are SELECT'd from `memory_chunks`.

5. **No new external dependencies.** Auditor should confirm no new pip packages. Only stdlib `dataclasses`, `typing`. This is a structural refactor + enrichment.

6. **Test coverage for ranking stages.** Auditor will check that each ranking stage (semantic, path_boost, freshness_boost) is independently tested with explicit input/output assertions, not just "it runs without error." Mitigation: `test_ranker.py` has parameterized tests for each stage with known inputs and expected score outputs.

7. **Fault-path resilience.** Auditor will verify that the fault-path tests (closure #9) cover realistic failure modes (DB timeout, partial results) and that the engine degrades gracefully. Mitigation: `test_fault_paths.py` uses mock pool to simulate `asyncio.TimeoutError` and partial row returns, asserts well-formed responses in all cases.

8. **Ranking reproducibility.** Auditor will verify that the reproducibility procedure (closure #10) is automated, uses fixed test data, and has a zero-tolerance exact-match criterion. Mitigation: baseline captured pre-refactor via script, compared post-refactor via pytest assertion on ID ordering. Tie-breaking rule (sort by `id` ascending) eliminates non-determinism from equal scores.

9. **Scope completeness.** Auditor will verify that declared modification scope (Files to modify) matches execution steps (Order of operations). Mitigation: v6 adds `mcp-memory-local/docker-compose.yml` to "Files to modify" row #4, aligning with step 8.

---

## Spec Completeness Gate (Builder self-check)

- [x] All output schemas defined -- `RetrievalResult` (9 fields: id int required, path str required, anchor str required, heading str required, snippet str required, source_kind str required, classification str required, score ScoreComponents required, provenance ProvenanceInfo required). `ScoreComponents` (3 fields: semantic float required, path_boost float default 0.0, freshness_boost float default 0.0; computed property final float). `ProvenanceInfo` (4 fields: provider_name str optional, external_id str optional, content_hash str required, indexed_at str optional). `RankingConfig` (3 fields: path_boost_weight float default 0.1, freshness_boost_weight float default 0.0, freshness_window_hours int default 168). Response dict includes backward-compat `similarity` key = `score.final`.
- [x] All boundary conditions named -- `RankingConfig` defaults: path_boost_weight=0.1 (matches current hardcoded value), freshness_boost_weight=0.0 (disabled by default), freshness_window_hours=168 (7 days). `score.final` capped at 1.0 via `min()`. Freshness boost only applies when `freshness_boost_weight > 0.0` AND `indexed_at` is within window. Path boost only applies when `changed_files` is non-empty and path substring matches. Provenance fields are nullable (legacy rows have NULL provider_name/external_id).
- [x] All behavioral modes specified -- standard (default ranking config, path_boost=0.1, freshness=0.0, identical to current behavior), enhanced (freshness_boost > 0.0, recently-updated chunks get boost), no-boost (path_boost=0.0, freshness=0.0, pure semantic ranking only), degraded (DB timeout or partial results -> empty or partial well-formed response list). No unhandled exception mode -- retrieval always returns `list[RetrievalResult]`.
- [x] Rollback procedure cites current CONSTITUTION.md version -- CONSTITUTION.md v0.4; rollback via `git revert` (new `retrieval/` dir deleted, modified files restored); no schema changes to revert; ranking config env vars default to current behavior so removal is no-op.
- [x] Governance citations validated against current file paths -- CONSTITUTION.md at `governance/CONSTITUTION.md` (confirmed v0.4), providers.md at `governance/providers.md` (confirmed version 1.3), source proposal at `governance/proposals/context-gateway-mcp-full-alignment-plan.md` (Phase 3 section confirmed), prior cycle at `governance/plans/CG_MCP/CG_MCP_v3.md` (confirmed Phase 2 plan, audit PASS), implementation repo at `C:\gh_src\rmembr` (confirmed `services/index/src/search.py` and `services/gateway/src/server.py` exist and match described state).
- [x] Declared modification scope matches execution steps -- "Files to modify" table (4 rows) aligns 1:1 with "Order of operations" steps 5-8. No undeclared file modifications.

READY FOR AUDITOR REVIEW
