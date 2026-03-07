# rMEMbr Azure Enterprise Proposal (Engineering Review Edition)
## Private VNet Architecture, Federated Source Retrieval, Semantic Cache, and 100% IaC using Bicep

---

# 0. One-Page Architecture Summary

## Platform Intent

rMEMbr is a **context and instruction delivery platform**, not an AI inference platform.

It is responsible for:

- locating relevant content across source systems
- retrieving standards and policy
- retrieving repository and documentation memory
- assembling context bundles
- enforcing identity and authorization
- delivering scoped context to downstream tools, automation, and AI systems

Reasoning and inference remain outside the core platform boundary.

---

## Core Design Clarification

rMEMbr is **not designed to become the primary content store**.

The architecture is intentionally **source-of-truth preserving**:

- users continue working in their systems of choice
- content remains owned by those systems
- rMEMbr indexes **locations and metadata**
- rMEMbr retrieves content on demand from those systems
- rMEMbr adds governance, standards, and scoped context around that retrieved content

Examples of source systems:

- GitHub
- Azure DevOps
- Confluence
- SharePoint
- Wikis
- file shares
- future enterprise content sources

In this model:

- **Cosmos DB vector search** stores vectors, metadata, references, and location pointers
- **Blob Storage** is primarily a **cache and artifact layer**, not the authoritative home of all content
- **Redis** is the fast semantic cache for repeated requests
- the original systems remain the systems of record

---

## High-Level Architecture Diagram

```text
                                   +-------------------------+
                                   |  Users / Tools / Agents |
                                   |  CI/CD / Automation     |
                                   +------------+------------+
                                                |
                                                v
                                      +-------------------+
                                      | Microsoft Entra ID|
                                      | AuthN / AuthZ     |
                                      +---------+---------+
                                                |
                                                v
                                  +-------------------------------+
                                  | Azure API Management          |
                                  | (optional enterprise gateway) |
                                  +---------------+---------------+
                                                  |
                                                  v
                              +------------------------------------------+
                              | Gateway Service                          |
                              | Azure Container App                      |
                              | - auth validation                        |
                              | - request orchestration                  |
                              | - cache lookup                           |
                              +-------------------+----------------------+
                                                  |
                           +----------------------+----------------------+
                           |                                             |
                           v                                             v
              +---------------------------+               +-----------------------------+
              | Azure Managed Redis       |               | Retrieval / Policy Path     |
              | Semantic Cache            |               | Index + Standards Services   |
              | - bundles                 |               | Azure Container Apps         |
              | - retrieval results       |               +---------------+-------------+
              | - standards fragments     |                               |
              +-------------+-------------+                               |
                            |                                             |
                      cache hit                                             cache miss
                            |                                             |
                            v                                             v
                        +-------+                           +-----------------------------+
                        |return |                           | Azure Cosmos DB             |
                        +-------+                           | Vector Search + Metadata    |
                                                            | + source location pointers  |
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                            +-----------------------------+
                                                            | Federated Source Connectors |
                                                            | GitHub / ADO / Confluence / |
                                                            | SharePoint / Wikis / etc.   |
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                            +-----------------------------+
                                                            | Source-of-Truth Content     |
                                                            | remains in external systems |
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                            +-----------------------------+
                                                            | optional Blob cache/artifact|
                                                            | layer for faster re-fetch   |
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                            +-----------------------------+
                                                            | bundle assembly / governance|
                                                            | context / cache writeback   |
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                                          return

Background Processing:
+------------------------+      +-----------------------------+      +----------------------+
| Azure Service Bus      | ---> | Worker Container Apps / Jobs| ---> | reindex / invalidate |
| queues / topics        |      | async processing            |      | refresh / maintenance|
+------------------------+      +-----------------------------+      +----------------------+
```

---

## Private Networking Diagram

```text
Hub / Shared Services VNet (if applicable)
    |
    +-- peering / routed connectivity
    |
Spoke VNet: rmembr
    |
    +-- Subnet: container-apps-env
    |      - Gateway
    |      - Index
    |      - Standards
    |      - Workers / Jobs
    |
    +-- Subnet: private-endpoints
    |      - Cosmos DB private endpoint
    |      - Blob Storage private endpoint
    |      - Redis private endpoint
    |      - Service Bus private endpoint
    |      - Key Vault private endpoint
    |      - ACR private endpoint (if used in scope)
    |
    +-- Private DNS Zones
           - privatelink.documents.azure.com
           - privatelink.blob.core.windows.net
           - privatelink.redis.cache.windows.net
           - privatelink.servicebus.windows.net
           - privatelink.vaultcore.azure.net
           - additional zones as required by enterprise standards
```

---

## Request Sequence Diagram

```text
Client / Tool / Agent
        |
        | 1. authenticate request
        v
Gateway Service
        |
        | 2. validate identity + authorization scope
        |
        | 3. normalize request + build retrieval/cache key
        v
Redis Semantic Cache
        |
   +----+----+
   |         |
   | hit     | miss
   |         |
   v         v
Return   Index / Standards Service
              |
              | 4. query vector metadata and source pointers
              v
         Cosmos Vector Search
              |
              | 5. identify best matching source locations
              v
         Source Connector Layer
              |
              | 6. fetch authoritative content from source system
              v
    GitHub / ADO / Confluence / SharePoint / Wiki / Other Source
              |
              | 7. optionally cache fetched content/artifacts
              v
         Blob Storage Cache (optional)
              |
              | 8. assemble governance-aware bundle
              v
         Bundle Assembly
              |
              | 9. write eligible result to Redis
              v
         Redis Semantic Cache
              |
              | 10. return final scoped bundle
              v
            Client
```

---

# 1. Purpose

This document proposes a complete Azure enterprise architecture for **rMEMbr**, including a staged migration plan from the current local container deployment to a scalable Azure platform.

This document is intended for **engineering review**, ensuring the design aligns with:

- enterprise networking requirements
- Azure platform capabilities
- internal infrastructure standards
- scalable AI tooling patterns
- maintainable Infrastructure as Code practices

All infrastructure must be delivered **100% as Infrastructure as Code (IaC)** using **Bicep** and must conform to existing enterprise patterns and standards.

---

# 2. Architectural Principle

rMEMbr is **not an AI inference platform**.

rMEMbr is a **context and instruction delivery platform** responsible for:

- locating relevant content across source systems
- retrieving contextual information
- retrieving standards and policy documentation
- retrieving repository memory
- assembling context bundles
- enforcing identity and authorization
- delivering context to downstream tools and AI systems

The platform intentionally **separates context delivery from AI reasoning**.

This allows rMEMbr to serve:

- developer tools
- automation systems
- CI/CD pipelines
- AI agents
- LLM-powered assistants

without coupling the platform to a specific AI provider and without requiring users to move their documentation into rMEMbr-owned storage.

---

# 3. Model and Embedding Strategy

## 3.1 Embedding Provider Abstraction

Embedding generation is handled by the **Index service** through a **provider abstraction layer**.

Current provider:

- **Ollama**

Future optional providers:

- Azure OpenAI
- OpenAI API
- HuggingFace models
- locally hosted embedding models

The architecture must not assume a specific embedding provider.

---

# 4. Target Azure Architecture

## Core Platform

- Azure Container Apps
- Azure Cosmos DB (Vector Search)
- Azure Blob Storage
- Azure Service Bus
- Azure Managed Redis (Enterprise)
- Microsoft Entra ID
- Azure Key Vault
- Private Endpoints + Private DNS
- Azure Container Registry (ACR)

Optional enterprise gateway:

- Azure API Management

---

# 5. Federated Retrieval Design

The platform uses a **federated retrieval model**.

## Systems of record remain external

rMEMbr does not require teams to move or rewrite their documentation into a central platform-owned store.

Instead:

- teams author content in their preferred systems
- rMEMbr indexes discoverable metadata and content locations
- rMEMbr retrieves authoritative content from those systems when needed
- rMEMbr optionally caches fetched content to improve performance
- rMEMbr adds governance context, standards, and policy overlays

## Role of each storage layer

### Cosmos DB
Stores:

- vectors
- chunk metadata
- system-agnostic content references
- source identifiers
- source locations
- governance metadata
- namespace / tenant boundaries

### Blob Storage
Stores:

- optional fetched-content cache
- normalized transient artifacts
- assembled bundle artifacts where useful
- archive or diagnostic artifacts

Blob Storage is primarily a **cache and artifact layer**, not the authoritative repository for all enterprise content.

### Redis
Stores:

- hot-path semantic cache
- repeated retrieval results
- final context bundles
- standards fragments

---

# 6. Networking Model

All platform resources must operate in **private-network mode**.

Requirements:

- public access disabled where supported
- all PaaS services accessed via **Private Endpoints**
- Container Apps deployed into a **private VNet environment**
- DNS resolution through **Private DNS Zones**
- outbound internet access restricted to approved endpoints

---

# 7. Azure Service Responsibilities

## Azure Container Apps

Runtime for:

- Gateway Service
- Index Service
- Standards Service
- Worker Services
- Connector adapters if hosted as internal services

Benefits:

- managed scaling
- revision deployments
- managed identity support
- integration with Service Bus scaling
- private networking support

---

## Azure Cosmos DB (Vector Search)

Stores:

- chunk metadata
- embeddings
- source-system-agnostic content references
- repository and document indexing metadata
- namespace / tenant boundaries

Recommended partition keys:

```text
/namespace
or
/tenant
```

Goals:

- distribute RU load
- isolate tenant workloads
- reduce hot partitions

Important clarification:

Cosmos is used to help **find the right content and where it lives**, not to become the source-of-truth content platform.

---

## Azure Blob Storage

Stores:

- fetched-content cache
- normalized markdown or transient transforms
- context bundle artifacts
- historical or diagnostic archives

Blob is used primarily as a **performance and artifact layer**.

It is not intended to replace GitHub, Azure DevOps, Confluence, SharePoint, or other authoring/documentation systems.

---

## Azure Service Bus

Separates interactive workloads from background workloads.

Queues:

- index-repo
- invalidate-cache
- automation-jobs
- refresh-standards
- maintenance
- source-refresh

Workers scale based on queue depth.

---

## Azure Managed Redis (Enterprise)

Provides semantic caching.

Cache targets:

- context bundles
- retrieval results
- standards documents
- normalized query results

Benefits:

- faster repeated reads
- reduced Cosmos RU usage
- protection from automation bursts
- fewer repeated source fetches

---

## Azure Container Registry

Container images are stored in **ACR**.

Container Apps pull images using **managed identity**.

---

# 8. Source Connector Model

rMEMbr requires a connector model to retrieve authoritative content from source systems.

Examples:

- GitHub connector
- Azure DevOps connector
- Confluence connector
- SharePoint connector
- future source adapters

Connector responsibilities:

- authenticate to the source system
- fetch authoritative content by location
- normalize content as needed for retrieval and bundle assembly
- expose source metadata back to the indexing/retrieval pipeline
- support governance-aware filtering where required

This connector model is central to the architecture because it preserves source ownership while allowing system-agnostic retrieval.

---

# 9. Cache Design

## Cache Keys

Cache keys must include tenant scope.

Examples:

```text
ctx:{tenant}:{namespace}:{intent_hash}:{version}
repo:{tenant}:{repo}:{branch}:{query_hash}
std:{tenant}:{standards_version}:{topic}
src:{tenant}:{source}:{location_hash}:{version}
```

Rule:

Cached responses **must never bypass authorization checks**.

Authorization must be validated before returning cached results.

---

# 10. Identity Model

## External Access

Authentication:

- Microsoft Entra ID

Authorization options:

- Entra groups
- application roles

---

## Service-to-Service Access

Use **Managed Identity**.

Examples:

- Container Apps → Cosmos DB
- Container Apps → Blob Storage
- Container Apps → Service Bus
- Container Apps → Key Vault
- Container Apps → source connectors where supported by the source/auth pattern

Shared secrets should be avoided where possible.

---

# 11. Observability

All services must send diagnostics to **Log Analytics**.

Application telemetry must use **Application Insights**.

Metrics:

- request latency
- cache hit rate
- Cosmos RU usage
- queue depth
- worker throughput
- indexing latency
- source fetch latency
- source fetch failure rate
- cache effectiveness vs direct source fetches

All services must propagate **correlation IDs**.

---

# 12. Environment Model

Recommended environments:

- dev
- test
- stage
- prod

Each environment is deployed using **Bicep parameter files**.

Infrastructure modules remain identical across environments.

---

# 13. Infrastructure as Code Requirement

All infrastructure must be provisioned using **Bicep**.

Manual resource creation in the Azure portal is prohibited except for emergency recovery.

Resources managed by IaC include:

- VNets
- subnets
- private DNS
- private endpoints
- Container Apps
- Cosmos DB
- Storage accounts
- Redis
- Service Bus
- Key Vault
- managed identities
- role assignments
- diagnostics
- monitoring

---

# 14. Bicep Module Structure

Suggested structure:

```text
infra/
  main.bicep
  main.<env>.bicepparam

  modules/
    networking/
    identity/
    observability/
    data/
    app/
    governance/
```

Modules must align with current enterprise standards for:

- naming
- tagging
- RBAC
- diagnostics
- network segmentation

---

# 15. Delivery Stages

## Stage 0 — Architecture Alignment

Confirm:

- networking model
- identity model
- Bicep module structure
- environment layout
- connector model
- source-of-truth preservation principle

---

## Stage 1 — Foundation Infrastructure

Deploy via Bicep:

- VNet
- subnets
- DNS
- monitoring
- Key Vault
- Cosmos
- Storage
- Redis
- Service Bus
- Container Apps environment

---

## Stage 2 — Core Application Deployment

Deploy services:

- Gateway
- Index
- Standards
- Workers

Integrate with storage and messaging.

---

## Stage 3 — Connector Enablement

Implement and validate:

- source connector framework
- GitHub connector
- Azure DevOps connector
- Confluence connector
- source fetch authorization model
- source normalization logic

---

## Stage 4 — Enterprise Security

Add:

- Entra authentication
- managed identity access
- RBAC enforcement
- audit logging

---

## Stage 5 — Async Processing

Implement:

- Service Bus queues
- worker scaling
- reindex pipelines
- source refresh pipelines

---

## Stage 6 — Semantic Cache

Add:

- Redis caching
- invalidation workers
- cache metrics
- TTL policies
- source-content cache strategy in Blob

---

## Stage 7 — Optimization

Tune:

- Cosmos partitioning
- Redis cache TTL
- source fetch strategy
- scaling rules
- cost optimization

---

# 16. Final Architecture Summary

The recommended platform stack is:

- Azure Container Apps
- Azure Cosmos DB (Vector Search + source location metadata)
- Azure Blob Storage (cache/artifact layer)
- Azure Service Bus
- Azure Managed Redis
- Azure Container Registry
- Microsoft Entra ID
- Azure Key Vault
- Private Endpoints + Private DNS

Embedding generation currently uses **Ollama** through a provider abstraction layer.

Future deployments may optionally support **Azure OpenAI**, but the platform does not depend on any specific AI provider.

This architecture allows rMEMbr to function as a **secure enterprise context delivery platform** that points to, fetches from, and governs content across many systems without forcing users into a single documentation or source-of-truth platform.
