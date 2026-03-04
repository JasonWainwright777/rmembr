# Context Gateway MCP --- Detailed Design & Implementation Expansion

**Generated:** 2026-03-04T18:19:13.952151 UTC\
**Audience:** Enterprise Architecture, Platform Engineering, AI
Enablement Teams\
**Purpose:** Expand on the optional *Context Gateway MCP* concept and
define its responsibilities, architecture, contracts, selection logic,
and governance model.

------------------------------------------------------------------------

# 1. Overview

The **Context Gateway MCP** is the unified "front door" for AI context
retrieval.

Instead of every AI client (developer tools, IDE copilots, Azure DevOps
agents) implementing their own retrieval logic, the Gateway centralizes:

-   Context discovery
-   Standards enforcement
-   Version pinning
-   Policy application
-   Size budgeting
-   Explainability
-   Deterministic bundle generation

It returns a **ready-to-use Context Bundle** that can be directly
consumed by LLMs or autonomous agents.

------------------------------------------------------------------------

# 2. Architectural Role

The Gateway sits between clients and backend services.

Clients: - Developer LLM tools - Autonomous ADO agents - Future AI
automation services

Backend Services: - Index MCP (pgvector discovery service) - Standards
MCP (authoritative content service)

Optional: - Repo Fetch service (or local workspace read) - Policy engine
(OPA) for advanced governance

The Gateway orchestrates calls to these services and applies
deterministic logic before returning a context bundle.

------------------------------------------------------------------------

# 3. Core Responsibilities

## 3.1 Orchestration

-   Query Index MCP for repo-specific matches
-   Query Standards MCP for canonical enterprise content
-   Resolve references declared in repo manifest
-   Aggregate and deduplicate results

## 3.2 Deterministic Pinning

-   All retrieval pinned to:
    -   Repo commit SHA
    -   Standards release tag
-   Pins included in bundle header for reproducibility

## 3.3 Policy Enforcement

-   Enforce precedence rules (standards \> repo by default)
-   Enforce classification boundaries
-   Validate override policy compliance
-   Prevent unauthorized cross-repo access

## 3.4 Context Budgeting

-   Curate content within defined size limits
-   Prioritize must-follow guidance
-   Trim narrative sections when necessary

## 3.5 Explainability

-   Provide trace metadata
-   Offer bundle explanation endpoint
-   Surface ranking and policy decisions

------------------------------------------------------------------------

# 4. Gateway MCP Tool Contracts

## 4.1 get_context_bundle

### Inputs

-   repo
-   commit_sha
-   task
-   persona (human \| autonomous)
-   changed_files (optional)
-   k (optional)
-   filters (optional)
-   standards_version (optional override)

### Outputs

-   bundle_id
-   pins (repo_commit_sha, standards_version)
-   selected_items
-   rendered_markdown
-   citations
-   optional trace metadata

------------------------------------------------------------------------

## 4.2 explain_context_bundle

Returns: - Selection reasoning - Excluded candidates and why - Applied
precedence rules - Confidence indicators

------------------------------------------------------------------------

## 4.3 validate_pack

Validates: - Required files present - Manifest schema correctness -
Broken standard references - Override compliance

------------------------------------------------------------------------

# 5. Context Bundle Structure

A bundle should contain:

## 5.1 Header

-   Repo + commit SHA
-   Standards version
-   Task description
-   Persona
-   Bundle ID
-   Timestamp

## 5.2 Canonical Enterprise Guidance

Curated excerpts from enterprise standards.

## 5.3 Repo-Specific Guidance

Repo-level conventions, instructions, templates.

## 5.4 Required Schemas / Templates

JSON/YAML schemas or references required for execution.

## 5.5 Task-Relevant References

Top semantic matches related to the task.

## 5.6 Citations

All file paths + anchors + pinned versions.

## 5.7 Optional Trace Section

-   Retrieval scores
-   Filter logic
-   Policy notes

------------------------------------------------------------------------

# 6. Selection Algorithm (Deterministic Pipeline)

## Step 1 --- Scope & Pins

-   Determine repo commit SHA
-   Determine standards version
-   Load repo manifest.yaml

## Step 2 --- Candidate Gathering

Candidates come from: 1. Required pack files 2. Index MCP search results
3. Manifest-referenced standards 4. Domain-default standards

## Step 3 --- Priority Ordering

Priority classes: 1. Enterprise must-follow standards 2. Repo
must-follow instructions 3. Task-relevant semantic matches 4. Examples
and FAQs

## Step 4 --- Precedence & Deduplication

-   Enforce central standards precedence
-   Validate overrides
-   Remove duplicates

## Step 5 --- Budget Enforcement

-   Allocate content slices (e.g., 40% standards / 40% repo / 20% task)
-   Truncate long excerpts
-   Prefer structured guidance over narrative

## Step 6 --- Bundle Assembly

-   Produce JSON payload
-   Generate rendered Markdown
-   Include citations and metadata

------------------------------------------------------------------------

# 7. Context Profiles (Advanced)

Profiles can alter retrieval behavior:

-   pipeline_change
-   terraform_module_work
-   api_schema_change
-   security_sensitive

Profiles adjust: - Priority rules - Budget allocation - Required
standards inclusion

------------------------------------------------------------------------

# 8. Security & Governance

-   Enforce Entra ID authentication
-   Repo-level authorization
-   Standards classification checks
-   Full audit logging of bundle generation
-   Optional policy engine integration

------------------------------------------------------------------------

# 9. Operational Considerations

## 9.1 Performance Targets

-   Gateway p95 latency: \< 1.5s
-   Index p95 latency: \< 600ms

## 9.2 Caching

-   Cache standards content by version
-   Cache frequent bundles (optional)

## 9.3 Observability

-   Metrics: latency, error rates, bundle size
-   Tracing across Gateway → Index → Standards

------------------------------------------------------------------------

# 10. Strategic Value

Without a Gateway: - Each AI client retrieves inconsistently - Standards
enforcement drifts - Determinism breaks in pipelines - Context windows
bloat

With a Gateway: - Retrieval becomes consistent - Governance is
centralized - Standards adoption measurable - Scaling to hundreds of
repos becomes manageable

------------------------------------------------------------------------

# 11. Future Enhancements

-   Drift detection (deprecated standards)
-   Near-duplicate detection
-   Bundle confidence scoring
-   Federated multi-org indexing
-   Migration to Azure AI Search backend

------------------------------------------------------------------------

# Closing Statement

The Context Gateway MCP transforms retrieval from a search problem into
a governed, deterministic context assembly service. It ensures that
enterprise AI usage remains aligned with architectural standards while
remaining scalable and operationally practical.
