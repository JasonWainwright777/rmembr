# rMEMbr Azure Enterprise Proposal (Engineering Review Edition)
## Private VNet Architecture, Semantic Cache, and 100% IaC using Bicep

---

# 0. One-Page Architecture Summary

## Platform Intent

rMEMbr is a **context and instruction delivery platform**, not an AI inference platform.

It is responsible for:

- retrieving context
- retrieving standards and policy
- retrieving repository memory
- assembling context bundles
- enforcing identity and authorization
- delivering scoped context to downstream tools, automation, and AI systems

Reasoning and inference remain outside the core platform boundary.

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
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                            +-----------------------------+
                                                            | Azure Blob Storage          |
                                                            | files / normalized docs /   |
                                                            | bundle artifacts / archive  |
                                                            +---------------+-------------+
                                                                            |
                                                                            v
                                                            +-----------------------------+
                                                            | bundle assembly / writeback |
                                                            | cache write                 |
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
        | 3. normalize request + build cache key
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
              | 4. perform retrieval logic
              v
         Cosmos Vector Search
              |
              | 5. fetch matching metadata / chunk refs
              v
         Blob Storage
              |
              | 6. fetch large content / artifacts if needed
              v
         Bundle Assembly
              |
              | 7. write eligible result to cache
              v
         Redis Semantic Cache
              |
              | 8. return final scoped bundle
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

without coupling the platform to a specific AI provider.

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

# 5. Networking Model

All platform resources must operate in **private-network mode**.

Requirements:

- public access disabled where supported
- all PaaS services accessed via **Private Endpoints**
- Container Apps deployed into a **private VNet environment**
- DNS resolution through **Private DNS Zones**
- outbound internet access restricted to approved endpoints

---

# 6. Azure Service Responsibilities

## Azure Container Apps

Runtime for:

- Gateway Service
- Index Service
- Standards Service
- Worker Services

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
- repository indexing metadata
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

---

## Azure Blob Storage

Stores:

- raw repository files
- normalized markdown
- context bundle artifacts
- historical archives

Blob is used for **large objects**, while Cosmos stores **queryable metadata**.

---

## Azure Service Bus

Separates interactive workloads from background workloads.

Queues:

- index-repo
- invalidate-cache
- automation-jobs
- refresh-standards
- maintenance

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

---

## Azure Container Registry

Container images are stored in **ACR**.

Container Apps pull images using **managed identity**.

---

# 7. Cache Design

## Cache Keys

Cache keys must include tenant scope.

Examples:

```text
ctx:{tenant}:{namespace}:{intent_hash}:{version}
repo:{tenant}:{repo}:{branch}:{query_hash}
std:{tenant}:{standards_version}:{topic}
```

Rule:

Cached responses **must never bypass authorization checks**.

Authorization must be validated before returning cached results.

---

# 8. Identity Model

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

Shared secrets should be avoided where possible.

---

# 9. Observability

All services must send diagnostics to **Log Analytics**.

Application telemetry must use **Application Insights**.

Metrics:

- request latency
- cache hit rate
- Cosmos RU usage
- queue depth
- worker throughput
- indexing latency

All services must propagate **correlation IDs**.

---

# 10. Environment Model

Recommended environments:

- dev
- test
- stage
- prod

Each environment is deployed using **Bicep parameter files**.

Infrastructure modules remain identical across environments.

---

# 11. Infrastructure as Code Requirement

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

# 12. Bicep Module Structure

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

# 13. Delivery Stages

## Stage 0 — Architecture Alignment

Confirm:

- networking model
- identity model
- Bicep module structure
- environment layout

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

## Stage 3 — Enterprise Security

Add:

- Entra authentication
- managed identity access
- RBAC enforcement
- audit logging

---

## Stage 4 — Async Processing

Implement:

- Service Bus queues
- worker scaling
- reindex pipelines

---

## Stage 5 — Semantic Cache

Add:

- Redis caching
- invalidation workers
- cache metrics
- TTL policies

---

## Stage 6 — Optimization

Tune:

- Cosmos partitioning
- Redis cache TTL
- scaling rules
- cost optimization

---

# 14. Final Architecture Summary

The recommended platform stack is:

- Azure Container Apps
- Azure Cosmos DB (Vector Search)
- Azure Blob Storage
- Azure Service Bus
- Azure Managed Redis
- Azure Container Registry
- Microsoft Entra ID
- Azure Key Vault
- Private Endpoints + Private DNS

Embedding generation currently uses **Ollama** through a provider abstraction layer.

Future deployments may optionally support **Azure OpenAI**, but the platform does not depend on any specific AI provider.

This architecture allows rMEMbr to function as a **secure enterprise context delivery platform** supporting developer tools, automation workflows, and AI agents at scale.
