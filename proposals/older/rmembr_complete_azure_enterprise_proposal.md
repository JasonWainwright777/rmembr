# rMEMbr Azure Enterprise Proposal
## Private VNet, Semantic Cache, and 100% IaC Delivery in Bicep

## 1. Executive Summary

This proposal describes a full Azure enterprise target architecture for rMEMbr, including the semantic cache expansion path, and a staged delivery plan to get from the current local five-container system to a secure, scalable, maintainable enterprise platform.

The recommended target platform is:

- **Azure Container Apps** for the application runtime
- **Azure Cosmos DB with vector search** for retrieval metadata and embeddings
- **Azure Blob Storage** for cached files, normalized artifacts, and larger content payloads
- **Azure Service Bus** for asynchronous indexing, invalidation, and automation burst handling
- **Azure Managed Redis** for the semantic cache layer
- **Microsoft Entra ID** for user and service authentication
- **Azure Key Vault** for secrets and certificates
- **Private networking everywhere possible**, including private endpoints and private DNS
- **Optional Azure API Management** as the enterprise gateway and policy layer

This proposal also assumes a **hard requirement that all infrastructure be provisioned as code in Bicep**, following the organization's current naming, tagging, layering, environment, RBAC, and networking standards.

---

## 2. Goals

The enterprise solution must:

- run fully inside the organization's private Azure networking model
- support growth from dozens of users to hundreds of users plus heavy automation
- enforce enterprise authentication and authorization
- isolate services and data appropriately
- separate interactive and background workloads
- support maintainable operations and monitoring
- be deployed and managed **100% through IaC**
- use **Bicep** and align with current enterprise patterns and standards

---

## 3. Current-State Summary

The current system runs locally as five containers and already has a service shape that translates well to Azure:

- Gateway
- Index
- Standards
- supporting storage and embeddings functions
- local orchestration and local trust boundaries

That is a strong starting point because it already behaves like a small platform, not a single monolith.

The main enterprise gaps are:

- inbound authentication and authorization
- private networking
- secrets and key handling
- identity for service-to-service communication
- durable object storage
- scalable vector storage
- workload separation for automation
- cache invalidation and burst control
- monitoring, auditability, and repeatable delivery

---

## 4. Recommended Target Architecture

## 4.1 Primary Recommendation

**Target architecture:**

- Azure Container Apps Environment deployed into a private VNet
- Gateway, Index, Standards, and Worker services as separate Container Apps
- Azure Cosmos DB for NoSQL with vector search enabled
- Azure Blob Storage for raw files, normalized documents, and larger cached bundles
- Azure Service Bus for background indexing, refresh, invalidation, and automation workloads
- Azure Managed Redis for semantic cache and hot-path acceleration
- Microsoft Entra ID for user authentication and app/service identity
- Azure Key Vault for secrets, certificates, and signing material
- Private Endpoints and Private DNS for all supported data-plane services
- Optional Azure API Management in front of the Gateway

---

## 4.2 Why This Architecture

This is the best balance of:

- private-network support
- Azure-native operations
- separation of concerns
- scaling flexibility
- lower operational overhead than AKS
- a clear path to support both humans and automation at scale

This proposal intentionally avoids using Azure Functions as the main runtime. Functions can still be useful for side utilities, webhook triggers, or scheduled maintenance, but the core runtime is better served by Container Apps because the platform is service-oriented rather than function-oriented.

---

## 5. Logical Architecture

```text
Clients / LLMs / IDE integrations / Automation
                    |
                    v
        Microsoft Entra ID / Optional APIM
                    |
                    v
              Gateway Service
          (Azure Container App)
                    |
        +-----------+-----------+
        |                       |
        v                       v
 Semantic Cache             Retrieval Path
 (Azure Managed Redis)      (Index / Standards Services)
        |                       |
      cache hit               cache miss
        |                       |
        v                       v
     return                Cosmos Vector Search
                                |
                                v
                           Blob Storage fetch
                                |
                                v
                         Bundle assembly / policy
                                |
                                v
                          cache write-back
                                |
                                v
                              return

Background and invalidation path:
Service Bus -> Worker Container Apps -> Redis invalidation / reindex / maintenance
```

---

## 6. Network Topology

All components should be deployed into a private network model.

## 6.1 Proposed Network Shape

```text
Hub / Shared Services VNet (if applicable)
    |
    +-- peering / routed connectivity
    |
Spoke VNet: rmembr
    |
    +-- subnet: container-apps-env
    |      - Gateway Container App
    |      - Index Container App
    |      - Standards Container App
    |      - Worker Container App / jobs
    |
    +-- subnet: private-endpoints
    |      - Cosmos DB private endpoint
    |      - Blob Storage private endpoint
    |      - Key Vault private endpoint
    |      - Redis private endpoint
    |      - Service Bus private endpoint
    |      - Azure OpenAI private endpoint if used
    |
    +-- subnet: integration or reserved subnet(s)
    |      - future expansion
    |
    +-- private DNS zones
           - privatelink.documents.azure.com
           - privatelink.blob.core.windows.net
           - privatelink.vaultcore.azure.net
           - privatelink.redis.cache.windows.net
           - privatelink.servicebus.windows.net
           - any required OpenAI or APIM zones
```

## 6.2 Networking Principles

- No public access to data-plane services unless a documented exception exists
- Use private endpoints where supported
- Disable public network access where supported
- Use private DNS and managed resolution
- Restrict ingress to approved internal paths only
- Use NSGs and route controls according to current enterprise standards
- Prefer managed egress and approved outbound controls

---

## 7. Azure Service Design

## 7.1 Azure Container Apps

Container Apps will host the main services:

- **Gateway**
  - handles MCP/API access
  - validates user identity
  - orchestrates retrieval and policy checks
  - uses cache first on eligible paths

- **Index**
  - handles chunking, embedding orchestration, vector writes, and indexing workflows

- **Standards**
  - serves standards, policy, and classification-related retrieval

- **Workers**
  - process queues
  - perform bulk reindex
  - handle semantic cache invalidation
  - run maintenance and compaction tasks

### Why Container Apps
- easier operations than AKS
- supports service decomposition
- supports managed identities
- supports revisions and controlled rollout
- supports event-driven scaling
- works well with private networking patterns

---

## 7.2 Cosmos DB with Vector Search

Cosmos DB will store durable retrieval data and vectorized metadata.

### Recommended use
- chunk metadata
- embeddings
- repository metadata
- namespace/tenant metadata
- retrieval-oriented metadata
- freshness/version markers
- pointers to content in Blob

### Do not use Cosmos for
- large raw file storage
- large assembled bundle payloads
- archive snapshots

---

## 7.3 Blob Storage

Blob Storage will store larger content objects.

### Recommended use
- raw file cache
- normalized markdown files
- content snapshots
- larger context bundles
- import/export payloads
- archive and diagnostic artifacts

This keeps object storage cheap and scalable while Cosmos remains focused on queryable retrieval data.

---

## 7.4 Service Bus

Service Bus is required to separate interactive traffic from background operations.

### Recommended queues/topics
- `index-repo`
- `reindex-namespace`
- `invalidate-cache`
- `refresh-standards`
- `automation-jobs`
- `maintenance-jobs`

### Why this matters
Human requests and automation traffic should not compete directly. Service Bus creates durable buffering, retry behavior, and a clean scale boundary between interactive and background work.

---

## 7.5 Azure Managed Redis

Redis is the semantic cache layer.

### What Redis should cache
- final context bundles
- ranked retrieval result sets
- standards/policy fragments
- normalized query metadata for common request shapes

### Why add Redis
Once the platform sees repeated reads from agents, users, and automation, Redis protects Cosmos and Blob from repeated hot-path queries and improves latency significantly.

---

## 7.6 Microsoft Entra ID

Use Entra ID for:

- user authentication
- application authentication
- app role assignments
- group-based authorization
- service principal / workload identity integration where needed

---

## 7.7 Key Vault

Key Vault will store:

- service secrets
- certificates
- signing keys
- external API secrets if any remain
- configuration values that must not live in app settings

Access should be through managed identity.

---

## 7.8 Optional API Management

Add API Management if the enterprise wants:

- rate limits
- quotas
- enterprise API lifecycle controls
- central policy enforcement
- controlled exposure to internal consumers
- future productization of the platform

APIM is not strictly required for v1 but is recommended if multiple internal teams or tools will consume the system.

---

## 8. Data Design

## 8.1 Cosmos Containers

### chunks
Stores the indexed fragments and retrieval metadata.

Example conceptual fields:
- id
- tenant
- namespace
- repo
- branch
- path
- chunkIndex
- embedding
- blobUri
- checksum
- indexedAt
- contentVersion
- securityScope

**Suggested partition key:** `/namespace` or `/tenant`

### repositories
Stores repo-level indexing metadata.

### namespaces
Stores tenant/team boundaries and retention settings.

### standards
Stores standards and policy metadata if those are managed in Cosmos rather than only Blob.

### retrievalAudit (optional)
Stores lightweight audit records and performance metadata if desired.

---

## 8.2 Blob Containers

Suggested storage containers:

- `source-cache`
- `normalized-docs`
- `context-bundles`
- `archives`
- `diagnostics`

---

## 8.3 Cache Key Design

Use tenant-aware, scope-aware, version-aware cache keys.

Examples:
- `ctx:{tenant}:{namespace}:{intent_hash}:{version}`
- `repo:{tenant}:{repo}:{branch}:{query_hash}`
- `std:{tenant}:{standards_version}:{topic}`
- `retr:{tenant}:{namespace}:{query_hash}:{embedding_version}`

### Rules
- never cache across tenant boundaries
- include version or content epoch markers
- never allow cache keys to bypass authorization boundaries

---

## 9. Security and Identity Model

## 9.1 Authentication

### External user and tool access
- authenticate via Entra ID
- validate JWT tokens at the gateway and optionally at APIM
- authorize via app roles, groups, or scoped claims

### Service-to-service access
- use managed identities
- remove shared internal tokens over time
- use RBAC on target resources

---

## 9.2 Authorization

Authorization should be enforced on:

- tenant
- namespace
- repository scope
- policy/standards scope
- admin or operational actions

Important principle:
**A cached result must never be returned without an authorization check for the caller’s current scope.**

---

## 9.3 Secrets and Certificates

- all secrets stored in Key Vault
- no secrets hardcoded in Bicep or application code
- use Key Vault references or managed identity retrieval patterns
- certificates managed through approved enterprise process

---

## 9.4 Auditability

Track at minimum:
- user/tool identity
- operation type
- namespace/repo scope
- cache hit/miss state
- allow/deny result
- request timing
- queue submission and worker actions

---

## 10. Observability

Use:

- Azure Monitor
- Log Analytics
- Application Insights
- diagnostic settings on all major resources

### Required metrics
- gateway request latency
- Redis cache hit/miss rate
- Cosmos RU consumption
- Blob read rate
- queue backlog depth
- worker processing latency
- failed invalidation count
- indexing duration
- auth failures
- denied access attempts

### Required traces
- end-to-end request tracing across gateway, retrieval, cache, and queue workers
- correlation IDs propagated through all services

---

## 11. Scaling Strategy

## 11.1 User Growth Path

### Stage A
- dozens of users
- moderate request volume
- light automation

### Stage B
- hundreds of users
- repeated questions
- increasing standards lookups
- scheduled and ad hoc automation

### Stage C
- high-frequency AI workflows
- CI/CD or agent-driven context retrieval
- continuous indexing and invalidation activity

---

## 11.2 Scale Controls

### Gateway
Scale on HTTP concurrency and latency indicators

### Workers
Scale on Service Bus queue depth

### Redis
Scale on memory footprint, hit rate, throughput, and connection count

### Cosmos
Scale on RU demand and partitioning strategy

### Blob
Scale naturally, but monitor hot partitions and repeated reads

---

## 12. Why This Should Be 100% IaC in Bicep

The organization has a requirement to follow current patterns and standards. This platform should therefore be built and maintained completely through **Bicep**, not portal-first deployment.

## 12.1 Benefits
- repeatable deployments
- environment consistency
- standards enforcement
- easier review and governance
- reduced configuration drift
- auditable change history
- better alignment with current enterprise delivery patterns

## 12.2 Scope of IaC
The Bicep solution should provision and configure, at minimum:

- resource groups or target scopes according to current landing-zone standards
- VNets, subnets, NSGs, route tables if applicable
- private DNS zones and links
- Container Apps environment
- Container Apps services and jobs
- Container registries or image references
- Cosmos DB account/database/containers
- Storage account and blob containers
- Service Bus namespace and queues/topics
- Redis instance
- Key Vault
- managed identities
- role assignments
- diagnostic settings
- Application Insights / Log Analytics
- API Management if included
- private endpoints
- network restrictions and public access settings
- locks and policy-aligned tags where required

---

## 13. Proposed Bicep Delivery Pattern

This should follow current enterprise IaC structure and standards rather than inventing a parallel pattern.

## 13.1 Recommended Bicep Structure

```text
infra/
  main.bicep
  main.<env>.bicepparam

  modules/
    networking/
      vnet.bicep
      subnets.bicep
      privateDns.bicep
      privateEndpoints.bicep

    identity/
      managedIdentity.bicep
      roleAssignments.bicep

    observability/
      logAnalytics.bicep
      appInsights.bicep
      diagnosticSettings.bicep

    data/
      cosmosAccount.bicep
      cosmosSqlDatabase.bicep
      cosmosContainer.bicep
      storageAccount.bicep
      serviceBus.bicep
      redis.bicep
      keyVault.bicep

    app/
      containerAppsEnvironment.bicep
      containerAppService.bicep
      containerAppJob.bicep
      apiManagement.bicep

    governance/
      tags.bicep
      locks.bicep
      policy-aligned configuration modules
```

---

## 13.2 Parameterization Standards

Use current organizational standards for:

- environment naming
- location values
- cost center / application tags
- domain or business-unit tags
- SKU selection
- public access toggles
- retention settings
- log routing settings

### Recommended parameter approach
- keep environment-specific values in `.bicepparam` files
- keep business logic out of pipeline scripts where possible
- use modular outputs and clear dependencies
- keep naming generation centralized and consistent with current patterns

---

## 13.3 Current Standards Alignment

This implementation should explicitly align with current standards for:

- naming conventions
- tagging conventions
- environment scoping
- network segmentation
- RBAC assignment model
- private endpoint usage
- diagnostics defaults
- resource locks
- approved Azure regions
- deployment pipelines
- promotion path across environments

If any current standard is missing or incomplete for a required Azure service, the proposal is to **extend the standard**, not bypass it.

---

## 14. Proposed Repository Pattern

A dedicated infrastructure repo or approved platform folder structure should contain:

- Bicep modules
- environment parameter files
- CI/CD pipeline definitions
- validation scripts
- documentation
- architecture decision records
- deployment runbooks

Suggested top-level structure:

```text
rmembr-platform/
  infra/
  docs/
  pipelines/
  scripts/
  README.md
```

If the organization already has an established repo pattern for Bicep platforms, this proposal should use that exact pattern.

---

## 15. Delivery Stages

## Stage 0 – Architecture and Standards Alignment

### Objective
Confirm design decisions and align with enterprise standards before buildout.

### Activities
- finalize target architecture
- validate required Azure services are approved
- confirm naming, tags, RBAC, and network standards
- document exceptions if needed
- define environment topology
- define Bicep module boundaries
- define auth and tenant model

### Deliverables
- approved architecture decision record
- approved Bicep module plan
- approved networking model
- approved identity model

---

## Stage 1 – Foundation IaC

### Objective
Stand up the private enterprise platform foundation in Azure using Bicep.

### Scope
- resource groups or approved scopes
- VNet, subnets, NSGs, route controls
- private DNS zones
- Log Analytics and App Insights
- Key Vault
- managed identities
- Container Apps environment
- Storage account
- Cosmos DB
- Service Bus
- Redis
- private endpoints
- diagnostic settings

### Deliverables
- deployable Bicep foundation
- environment parameter files
- pipeline validation and deployment flow
- baseline observability

### Exit criteria
- all foundation resources deploy by pipeline only
- no manual portal creation required
- all data-plane services private only

---

## Stage 2 – Core Application Deployment

### Objective
Deploy the current services into Azure Container Apps with enterprise wiring.

### Scope
- Gateway Container App
- Index Container App
- Standards Container App
- Worker Container App / jobs
- managed identity wiring
- Key Vault integration
- Storage/Cosmos/Service Bus connectivity
- private ingress and internal service routing
- base health probes and diagnostics

### Deliverables
- containerized Azure deployment of current service model
- configuration model for environment promotion
- app-to-platform integration

### Exit criteria
- core retrieval works in Azure private network
- interactive path works end-to-end
- background path can enqueue and process jobs

---

## Stage 3 – Security Hardening and Enterprise Auth

### Objective
Move from application-local trust to enterprise identity and policy controls.

### Scope
- Entra ID authentication
- app roles or group-based authorization
- managed identity-only service access where feasible
- role assignments for data-plane access
- secret removal from code and app settings
- audit and deny-path logging
- optional APIM if selected

### Deliverables
- documented access model
- documented RBAC assignments
- secure configuration baseline
- validated auth flows

### Exit criteria
- all external access authenticated
- no shared internal secrets required for Azure-native resource access
- audit trail available for core operations

---

## Stage 4 – Async Workload Separation

### Objective
Protect user-facing retrieval and prepare for automation scale.

### Scope
- Service Bus queues/topics finalized
- worker scaling rules
- retry/dead-letter behavior
- reindex pipelines
- maintenance jobs
- refresh jobs

### Deliverables
- queue-driven processing model
- dead-letter handling runbook
- scale settings by workload type

### Exit criteria
- indexing and refresh no longer depend on synchronous user requests
- automation traffic isolated from user latency path

---

## Stage 5 – Semantic Cache Enablement

### Objective
Add the Redis semantic cache layer to improve repeated-read performance.

### Scope
- Redis deployment and private endpoint
- cache lookup/write-back logic
- cache key design
- TTL policy
- event-driven invalidation using Service Bus
- invalidation worker implementation
- cache hit/miss metrics

### Deliverables
- semantic cache capability
- invalidation design and runbooks
- latency dashboards
- protected auth-aware cache flow

### Exit criteria
- repeated-read performance materially improved
- cache invalidation works for repo and standards updates
- no tenant or auth leakage across cached results

---

## Stage 6 – Optimization and Enterprise Readiness

### Objective
Prepare for broader enterprise adoption and sustained scale.

### Scope
- load testing
- cost tuning
- partition strategy tuning
- Redis TTL tuning
- Cosmos RU tuning
- APIM adoption if needed
- DR and backup considerations
- operational runbooks
- support model and SLO definition

### Deliverables
- production readiness review
- support and operations guide
- performance test results
- recommended scale settings
- backlog for phase-two improvements

### Exit criteria
- platform supports projected user and automation growth
- operations team has clear runbooks
- deployment and rollback are repeatable

---

## 16. Pipeline and Deployment Requirements

The delivery pipeline should also follow current enterprise patterns and standards.

## Requirements
- validate Bicep syntax and lints
- validate parameter files
- deploy by environment promotion path
- support what-if / preview where appropriate
- block manual drift
- publish deployment outputs as artifacts
- enforce approvals according to environment criticality

### Suggested stages
- lint
- validate
- what-if / plan
- deploy
- post-deploy smoke checks

If the organization already has a standard Bicep pipeline template, use that template rather than creating a one-off deployment flow.

---

## 17. Risks and Mitigations

## Risk 1 – Cache complexity
A semantic cache adds invalidation complexity.

**Mitigation:** introduce cache after observability and eventing are ready; use version-aware keys plus targeted invalidation.

## Risk 2 – Authorization leakage through cache
If cache keys are not scoped correctly, data could be exposed improperly.

**Mitigation:** include tenant and scope in cache keys and enforce auth before returning cached results.

## Risk 3 – Premature overengineering
Building everything at once may slow delivery.

**Mitigation:** use staged rollout; foundation and core runtime first, then async separation, then semantic cache.

## Risk 4 – Divergence from enterprise standards
A fast-moving project may accidentally bypass current patterns.

**Mitigation:** treat standards alignment as Stage 0 deliverable and codify them in reusable Bicep modules.

## Risk 5 – Operational blind spots
Without strong telemetry, scale issues may be hard to diagnose.

**Mitigation:** make observability part of foundation, not an afterthought.

---

## 18. Decision Summary

## Recommended final target
- Container Apps
- Cosmos DB vector search
- Blob Storage
- Service Bus
- Managed Redis semantic cache
- Entra ID
- Key Vault
- Private Endpoints
- Optional APIM

## Recommended implementation approach
- build everything through **100% IaC**
- use **Bicep**
- follow **current patterns and standards**
- deliver in stages
- add semantic cache after the platform foundation and async model are in place

---

## 19. Final Recommendation

Move forward with a staged Azure enterprise implementation of rMEMbr using:

**Azure Container Apps + Cosmos DB + Blob Storage + Service Bus + Managed Redis + Entra ID + Key Vault + Private Networking**

Build the platform entirely in **Bicep**, and ensure the design conforms to the organization’s existing standards for naming, tagging, environment management, RBAC, diagnostics, networking, and deployment pipelines.

This approach gives the team:

- a secure private Azure deployment model
- scalable retrieval and storage
- clean separation between interactive and automation traffic
- a clear performance expansion path through semantic caching
- repeatable and governed enterprise delivery through IaC
