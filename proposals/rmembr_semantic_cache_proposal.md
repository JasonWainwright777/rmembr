# rMEMbr Semantic Cache Expansion Proposal

## Purpose

This document describes a fourth architecture option for rMEMbr in Azure: adding a semantic cache layer in front of the vector retrieval path.

This option is intended for the stage where the platform begins to experience:

- repeated context lookups
- many users asking similar questions
- AI agents calling MCP repeatedly
- automation and CI/CD workflows generating burst traffic

The goal is to improve:

- latency
- cost efficiency
- resilience under repeated reads

while preserving the core Azure architecture direction.

---

# Recommended Stack with Semantic Cache

**Base platform**

- Azure Container Apps
- Azure Cosmos DB (Vector Search)
- Azure Blob Storage
- Azure Service Bus
- Microsoft Entra ID
- Azure Key Vault
- Private Endpoints + Private DNS

**Expansion component**

- Azure Managed Redis

Redis becomes the fast in-memory semantic cache, while Cosmos remains the durable retrieval and metadata store.

---

# High-Level Architecture

```text
Client / LLM / Agent / Automation
            |
            v
      Azure API Management
          (optional)
            |
            v
      Gateway Service
     (Container App)
            |
            v
   +-------------------+
   | Semantic Cache    |
   | Azure Managed     |
   | Redis             |
   +-------------------+
      |            |
    cache        cache
     hit          miss
      |            |
      v            v
  return      Retrieval Pipeline
              -> Index Service
              -> Cosmos Vector Search
              -> Blob fetch if needed
              -> Bundle assembly
              -> cache write-back
              -> return result
```

---

# Before / After Request Flow

## Before Cache

Every request follows the full retrieval path.

```text
Client
  -> Gateway
  -> Index / Retrieval Service
  -> Cosmos DB vector search
  -> Blob Storage content fetch
  -> bundle assembly
  -> return response
```

Characteristics:

- higher per-request latency
- repeated calls repeatedly hit Cosmos and Blob
- more pressure on vector search and storage layers
- more sensitive to burst traffic

---

## After Cache

Repeated requests use the fast path.

```text
Client
  -> Gateway
  -> Redis lookup

If hit:
  -> return cached context bundle

If miss:
  -> Index / Retrieval Service
  -> Cosmos DB vector search
  -> Blob Storage content fetch
  -> bundle assembly
  -> write result to Redis
  -> return response
```

Characteristics:

- much faster repeated reads
- lower pressure on Cosmos and Blob
- better fit for AI agent and automation replay patterns
- more predictable user latency for hot content

---

# What Should Be Cached

A semantic cache should operate at multiple layers rather than caching only raw user text.

## 1. Final Context Bundles

Cache the fully assembled MCP-ready context bundle.

Examples:

- repo context bundles
- standards bundles
- workflow-specific context packages
- repeated onboarding or support bundles

Best use cases:

- identical or near-identical repeated requests
- high-value, high-cost assembly outputs

---

## 2. Retrieval Result Sets

Cache ranked chunk IDs or retrieval result metadata before final assembly.

Examples:

- top chunk IDs for a normalized query
- ranked standards sections
- repo path result lists

Best use cases:

- repeated query shapes with different downstream formatting
- reducing repeated vector-search pressure

---

## 3. Standards and Policy Content

Cache slow-changing reference material.

Examples:

- standards documents
- classification rules
- persona rules
- policy fragments
- common reference bundles

Best use cases:

- very high read rate
- low mutation frequency
- predictable invalidation events

---

## 4. Query Normalization Metadata

Cache normalized representations of frequent query patterns.

Examples:

- normalized intent classification
- query fingerprints
- embedding-related normalization metadata

Best use cases:

- high repetition from agents and automation
- systems that reuse common question templates

---

# Recommended Cache Keys

Keys should be based on normalized inputs and scope boundaries.

## Key Patterns

```text
ctx:{tenant}:{namespace}:{intent_hash}:{version}
std:{tenant}:{standards_version}:{topic}
repo:{tenant}:{repo}:{branch}:{query_hash}
bundle:{tenant}:{workflow}:{scope}:{version}
retr:{tenant}:{namespace}:{query_hash}:{embedding_version}
```

## Design Notes

Keys should include:

- tenant
- namespace or repo scope
- normalized query identity
- version markers

This supports safe invalidation and avoids cache contamination across tenants or teams.

---

# Cache Invalidation Design

Cache invalidation should be event-driven and version-aware.

## Invalidation Events

Recommended invalidation triggers:

- repository reindexed
- branch or content updated
- standards document changed
- policy version changed
- namespace settings changed
- embedding model version changed
- manual admin flush
- emergency security purge

---

## Invalidation Flow

```text
Repo / Standards Update
        |
        v
   Service Bus Event
        |
        v
 Invalidation Worker
 (Container App Job or Worker)
        |
        v
  Redis key deletion
  or version bump
```

Recommended approach:

- publish invalidation events to Service Bus
- process them asynchronously with worker containers
- clear exact keys when possible
- fall back to version-based expiration when exact deletion is difficult

---

## Preferred Strategy

Use a combination of:

- **targeted key deletion** for precise invalidation
- **versioned cache keys** for safe fallback
- **TTL expiration** for cleanup of stale or unused entries

---

# TTL Strategy

Suggested TTL patterns:

| Cache Type | Suggested TTL |
|---|---|
| final context bundles | 5–30 minutes |
| retrieval result sets | 5–15 minutes |
| standards / policy content | 30–120 minutes |
| normalized query metadata | 15–60 minutes |

These values should be tuned based on freshness requirements and traffic patterns.

---

# Azure Component Roles

## Azure Managed Redis

Purpose:

- hot-path cache
- repeated-read acceleration
- temporary in-memory semantic responses

Use Redis for:

- final bundle cache
- retrieval result cache
- standards cache
- invalidation-aware hot data

Do not use Redis as the system of record.

---

## Cosmos DB

Purpose:

- vector search
- durable chunk metadata
- namespace and repository metadata
- durable retrieval store

Cosmos remains authoritative for retrieval-related state.

---

## Blob Storage

Purpose:

- raw source files
- normalized markdown
- cached large artifacts
- context package snapshots
- archives

Blob stores the large objects that should not live in Redis or Cosmos.

---

## Service Bus

Purpose:

- async indexing
- invalidation events
- rebuild jobs
- automation-driven workloads

Service Bus separates interactive traffic from background processing.

---

## Container Apps

Purpose:

- gateway runtime
- retrieval services
- standards service
- worker services
- invalidation workers

Container Apps continues to be the main application runtime.

---

# Network and Security Model

The semantic cache option still supports the private-network enterprise requirement.

## Network Principles

- private VNet deployment
- private endpoints for Redis, Cosmos, Blob, Key Vault, and other PaaS services
- public network access disabled where supported
- private DNS zones for internal resolution

## Security Principles

- Entra ID for external authentication
- managed identity for service-to-service access
- Key Vault for secrets and certificates
- tenant-aware cache keys
- authorization checks performed before cache access is returned

Important note:

A cached response should never bypass authorization scope checks.

---

# Performance Benefits

## Lower Latency

Repeated requests return from Redis instead of repeating:

- vector search
- metadata lookup
- blob fetch
- bundle assembly

## Lower Data-Plane Pressure

The cache reduces repeated load on:

- Cosmos RU consumption
- Blob reads
- retrieval pipeline CPU

## Better Burst Handling

Automation workloads often repeat similar calls at very high speed.

A semantic cache absorbs repeated reads and helps protect the primary retrieval layer from burst amplification.

---

# Cost Considerations

Potential cost benefits:

- fewer repeated Cosmos queries
- fewer repeated Blob reads
- lower bundle assembly workload
- lower compute pressure on retrieval services

Potential cost tradeoffs:

- Redis becomes an additional paid service
- engineering effort for invalidation and observability increases

This option is usually justified once repeated-read traffic is significant.

---

# Operational Risks

A semantic cache adds performance, but also introduces operational complexity.

## Main Risks

- stale cache data
- invalidation mistakes
- hidden authorization bugs if keys are not properly scoped
- harder debugging across cache and source-of-truth layers
- metrics and tracing become more important

## Mitigations

- use tenant/version-aware keys
- require auth scope validation before cache return
- implement event-driven invalidation
- include cache hit/miss and stale-read metrics
- trace cache hit/miss state in logs

---

# Recommended Metrics

Track at minimum:

- cache hit rate
- cache miss rate
- average retrieval latency
- average cached response latency
- invalidation event count
- invalidation failure count
- Redis memory usage
- Cosmos query volume
- Blob read volume
- queue depth for invalidation workers

These metrics will help determine whether the cache is paying for itself.

---

# Adoption Timing

## When to Add It

Add the semantic cache when one or more of these are true:

- repeated bundles are being requested often
- standards or policy content dominates reads
- AI agents reuse the same retrieval patterns
- automation generates repeated hot-path lookups
- retrieval latency or Cosmos load becomes a bottleneck

## When Not to Add It Yet

Delay it if:

- traffic is still low
- most requests are unique
- invalidation logic is not ready
- the team wants to simplify the initial rollout

---

# Recommended Rollout Plan

## Phase 1 – Base Enterprise Platform

Deploy:

- Container Apps
- Cosmos DB vector search
- Blob Storage
- Service Bus
- Entra ID
- Key Vault
- private endpoints

Goal:

Make the platform secure, private, and operational.

---

## Phase 2 – Instrumentation First

Add:

- latency dashboards
- query pattern tracking
- bundle repetition analysis
- Cosmos RU monitoring
- Blob read monitoring

Goal:

Confirm that repeated-read patterns justify a cache.

---

## Phase 3 – Add Semantic Cache

Deploy:

- Azure Managed Redis
- cache lookup logic in Gateway / Retrieval path
- write-back cache behavior
- invalidation worker

Goal:

Accelerate repeated-read paths without changing the source-of-truth design.

---

## Phase 4 – Optimize and Tune

Tune:

- TTL policies
- invalidation granularity
- hot-key detection
- prewarming for known workflows
- standards cache policy

Goal:

Reduce cost and improve latency under automation-heavy load.

---

# Final Recommendation

The semantic cache should be treated as a **performance expansion path**, not necessarily a day-one requirement.

## Recommended Base Platform

- Azure Container Apps
- Azure Cosmos DB (Vector Search)
- Azure Blob Storage
- Azure Service Bus
- Microsoft Entra ID
- Azure Key Vault
- Private Endpoints + Private DNS

## Recommended Future Expansion

- Azure Managed Redis as a semantic cache layer

This gives rMEMbr:

- private enterprise networking
- durable vector retrieval
- scalable blob-backed content storage
- clean async workload separation
- a clear path to faster and cheaper repeated retrieval at scale
