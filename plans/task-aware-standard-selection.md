# Plan: Task-Aware Standard Selection

## Problem

The gateway currently fetches the **first 5 standards alphabetically** and includes them in every context bundle, regardless of whether they're relevant to the task. With 9+ standards, this means:

- Irrelevant standards waste token budget (e.g., Terraform guidance when writing Bicep)
- Only 5 of 9 standards are ever included
- No connection between what the task is about and which governance applies

## Goal

When a user asks an AI to write Bicep in another repo, and that AI calls `get_context_bundle`, rMEMbr should:

1. Retrieve repo-specific context (where files are, patterns, etc.)
2. **Automatically select** the relevant enterprise standards (Bicep, maybe security) based on the task
3. Skip irrelevant standards (ADO pipelines, Terraform, etc.)

## Current Architecture (What Exists)

- **Gateway `handle_get_context_bundle`** (server.py:365-492): Calls `list_standards` then fetches first 5 via `get_standard`
- **Standards service**: Stateless file server, returns `{id, version, content}` per standard
- **Manifest `references.standards`**: Already parsed into `ManifestData.references_standards` but **never used** in bundle assembly
- **Standard metadata**: Each standard has YAML front matter with `title`, `domain`, `standard_id`, `classification`
- **list_standards** already supports a `domain` filter parameter

## Design

Two-layer selection: **manifest pinning** (repo declares which standards it always wants) + **semantic matching** (task description matched against standard titles/domains).

### Selection Algorithm

```
1. Get all available standards via list_standards
2. Build candidate set:
   a. Pinned standards: from manifest references.standards (always included)
   b. Semantic matches: score each standard's title+domain against the task string
3. Rank candidates by semantic relevance
4. Apply max_standards budget (default: 5)
5. Fetch full content only for selected standards
```

### Why Two Layers?

- **Manifest pinning** lets repo owners enforce governance ("this repo always needs secrets-management")
- **Semantic matching** catches task-relevant standards the repo didn't explicitly pin
- Together they provide both explicit governance and intelligent discovery

---

## Implementation Steps

### Step 1: Standards Service — Return Metadata in list_standards

**File:** `services/standards/src/server.py`

**Change:** Modify `list_standards` to return `title` and `domain` alongside `id` and `version`. These are already in the YAML front matter of each standard file.

**Current response:**
```json
{"standards": [{"id": "enterprise/bicep/infrastructure-as-code", "version": "local"}]}
```

**New response:**
```json
{"standards": [{"id": "enterprise/bicep/infrastructure-as-code", "version": "local", "title": "Bicep Infrastructure as Code Standards", "domain": "bicep"}]}
```

**Implementation:**
- When listing standards, read the first ~20 lines of each file to extract front matter
- Parse `title` and `domain` from YAML front matter
- Cache parsed metadata in memory (standards files rarely change)

**Acceptance Criteria:**
- `list_standards` returns `title` and `domain` for every standard
- Existing callers (gateway, MCP proxy) are unaffected (additive fields)
- Response time stays under 100ms

**Testing:**
- Unit test: `list_standards` returns metadata fields for all 9 standards
- Unit test: missing front matter defaults to `title=id`, `domain=""`

---

### Step 2: Gateway — Read Manifest references.standards

**File:** `services/gateway/src/server.py`

**Change:** In `handle_get_context_bundle`, after resolving context from the index service, fetch the repo's manifest to get `references.standards` (the pinned standards list).

**Implementation:**
- Add a new internal endpoint to the index service: `GET /internal/manifest/{repo}` that returns the parsed manifest for a repo (or read from `memory_packs` table if manifest data is stored there)
- Alternatively, store `references_standards` in the `memory_packs` table during indexing (it's already parsed but not persisted)
- In the gateway, call this to get the pinned list

**Acceptance Criteria:**
- Gateway can retrieve the pinned standards list for any indexed repo
- If the repo has no manifest or no `references.standards`, returns an empty list
- Does not add more than 50ms to bundle assembly

**Testing:**
- Unit test: repo with `references.standards: [enterprise/bicep/infrastructure-as-code]` returns that list
- Unit test: repo with no references returns empty list

---

### Step 3: Gateway — Semantic Standard Matching

**File:** `services/gateway/src/server.py` (new helper function)

**Change:** Add a function that scores each standard's relevance to the task description using lightweight text matching.

**Implementation:**

```python
def _select_standards(
    task: str,
    available: list[dict],        # from list_standards (with title, domain)
    pinned: list[str],            # from manifest references.standards
    max_standards: int = 5,
) -> list[dict]:
    """Select relevant standards for a task.

    1. Always include pinned standards
    2. Score remaining by keyword overlap between task and title+domain
    3. Return up to max_standards, pinned first then by score
    """
```

**Scoring approach — keyword matching (no embedding call needed):**
- Tokenize the task description into lowercase words
- For each standard, tokenize `title + domain + id`
- Score = number of overlapping tokens (with basic stopword removal)
- Standards with score > 0 are candidates
- Sort by score descending

**Why not embeddings?** Embedding the task against 9 standard titles would require an extra Ollama call for each bundle request. Keyword matching is fast, deterministic, and sufficient since standard titles/domains are descriptive (e.g., "Bicep Infrastructure as Code Standards" will match a task containing "bicep" or "infrastructure").

**Acceptance Criteria:**
- Task "write a Bicep module for storage" selects `enterprise/bicep/infrastructure-as-code`
- Task "add .NET API endpoint" selects `enterprise/dotnet/application-standards` and `enterprise/api/rest-api-design`
- Pinned standards are always included regardless of task text
- Total selected standards <= max_standards
- Function executes in < 5ms (pure string operations)

**Testing:**
- Unit test: keyword match selects correct standards for 5+ different task descriptions
- Unit test: pinned standards always appear even if task text doesn't mention them
- Unit test: max_standards budget is respected
- Unit test: no standards selected when task has zero keyword overlap (e.g., "general question about the repo")

---

### Step 4: Gateway — Wire Selection into Bundle Assembly

**File:** `services/gateway/src/server.py`

**Change:** Replace the current "fetch first 5" logic with the selection algorithm.

**Current code (lines 429-449):**
```python
# Step 6: Fetch standards content
standards_content = []
standards_list_resp = await client.post(
    f"{STANDARDS_URL}/tools/list_standards",
    headers=_internal_headers(),
    json={"version": standards_version},
)
standards_refs = []
if standards_list_resp.status_code == 200:
    standards_list = standards_list_resp.json().get("standards", [])
    for std in standards_list[:5]:  # <-- REPLACE THIS
        ...
```

**New code:**
```python
# Step 6: Select and fetch relevant standards
standards_content = []
standards_refs = []

# 6a: Get all available standards with metadata
standards_list_resp = await client.post(...)
available_standards = standards_list_resp.json().get("standards", [])

# 6b: Get pinned standards from repo manifest
pinned = await _get_pinned_standards(client, repo, namespace)

# 6c: Select relevant standards
selected = _select_standards(task, available_standards, pinned, max_standards=5)

# 6d: Fetch content only for selected standards
for std in selected:
    std_resp = await client.post(...)
    ...
```

**Acceptance Criteria:**
- Bundle assembly uses selected standards instead of first 5
- Bundle response includes a `standards_selection` field showing why each was included (pinned vs matched)
- Cache key includes standard selection to avoid stale bundles
- explain_context_bundle shows which standards were selected and why

**Testing:**
- Integration test: bundle for "write bicep" includes bicep standard, excludes ADO
- Integration test: bundle for repo with pinned standards always includes them
- Integration test: bundle for generic task includes fewer standards than before

---

### Step 5: Add max_standards to BudgetPolicy

**Files:** `services/gateway/src/policy/types.py`, `policy/default_policy.json`

**Change:** Make the maximum number of standards per bundle configurable via policy.

**Implementation:**
- Add `max_standards: int = 5` to `BudgetPolicy`
- Add `"max_standards": 5` to `default_policy.json` under `budgets`
- Use `policy.budgets.max_standards` in `_select_standards`

**Acceptance Criteria:**
- `max_standards` is configurable via policy file
- Defaults to 5 if not specified
- Changing the value changes how many standards are included

**Testing:**
- Unit test: policy with `max_standards: 3` limits to 3 standards
- Unit test: missing field defaults to 5

---

### Step 6: Update explain_context_bundle

**File:** `services/gateway/src/server.py`

**Change:** Add standard selection reasoning to bundle explanation.

**Implementation:**
- Store selection metadata in the cached bundle (which standards were pinned, which were matched, scores)
- In `handle_explain_context_bundle`, include a `standards_selection` section showing:
  - Which standards were included and why (pinned vs keyword match)
  - Which standards were available but not selected
  - The keyword scores for each candidate

**Acceptance Criteria:**
- `explain_context_bundle` shows standard selection reasoning
- Users can understand why a standard was or wasn't included

**Testing:**
- Unit test: explanation includes pinned standards labeled as "pinned"
- Unit test: explanation includes matched standards with scores

---

### Step 7: Update Documentation and Memory

**Files:**
- `.ai/memory/system-architecture.md` — document the selection algorithm
- `.ai/memory/configuration.md` — document `max_standards` budget
- `docs/USAGE.md` — explain how manifest pinning works
- `prompts/setup-rmembr-on-new-repo.md` — mention `references.standards` in manifest

**Acceptance Criteria:**
- All docs reflect the new behavior
- Setup guide explains how to pin standards in manifest

---

## Sequence Diagram

```
Client                  Gateway                 Index              Standards
  |                       |                       |                    |
  |-- get_context_bundle->|                       |                    |
  |                       |-- resolve_context ---->|                    |
  |                       |<-- chunk pointers -----|                    |
  |                       |                       |                    |
  |                       |-- get manifest ------->|                    |
  |                       |<-- references.stds ----|                    |
  |                       |                       |                    |
  |                       |-- list_standards (with metadata) --------->|
  |                       |<-- [{id, title, domain}, ...] ------------|
  |                       |                       |                    |
  |                       |  _select_standards()  |                    |
  |                       |  (pinned + keyword)   |                    |
  |                       |                       |                    |
  |                       |-- get_standard (selected only) ---------->|
  |                       |<-- standard content ----------------------|
  |                       |                       |                    |
  |<-- bundle (chunks + selected standards) ---|                    |
```

## Risk & Rollback

- **Low risk**: keyword matching is additive — worst case is the same standards as before
- **Rollback**: revert to `standards_list[:5]` if selection logic is problematic
- **No DB migrations required**
- **No breaking API changes** — bundle format is the same, just smarter selection

## Open Questions

1. **Should semantic embedding be an option?** Keyword matching is fast and likely sufficient, but embedding the task against standard descriptions could catch non-obvious matches. Could be a future enhancement.
2. **Should `max_standards` be per-repo via manifest?** A repo might want all 9 standards. Currently it's a global budget.
3. **Should the standards service cache front matter parsing?** With 9 standards, parsing is trivial. At 100+, caching would matter.
