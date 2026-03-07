# rMEMbr on Azure: Enterprise Architecture Proposals

Prepared for Jason Wainwright  
Date: March 7, 2026

## 1. What I believe you have today

Based on the architecture brief, the current system is a local-first, five-container deployment with:

- Gateway for HTTP/MCP, policy, bundle assembly, and caching
- Index service for ingestion, chunking, embeddings, and semantic retrieval
- Standards service for versioned standards content
- Postgres with pgvector for storage
- Ollama for embeddings

That is a solid proof-of-concept shape because the service boundaries are already separated. The main enterprise gaps are not the microservice split itself; they are the boundary concerns around authentication, authorization, private networking, operational scaling, secrets management, auditability, and tenant isolation.

## 2. Enterprise goals that should drive the Azure move

From your description, the Azure design needs to support:

- Dozens of human users at first, then hundreds
- Fast automation and AI agents making MCP/API calls at much higher sustained rates than humans
- Clear enterprise authentication and authorization
- Private, supportable networking
- Operational simplicity where possible
- A path to stronger isolation and higher scale later without redesigning the entire product

That means the winning design should:

- Separate synchronous retrieval from asynchronous indexing
- Use Entra-based identities instead of shared secrets where possible
- Put a formal API boundary in front of MCP/HTTP calls
- Avoid coupling the search engine choice to the first hosting choice
- Allow separate scaling for query traffic and indexing traffic

---

# Proposal A — Recommended Default
## Azure Container Apps + Azure API Management + Azure Cosmos DB (Vector) + Service Bus

### Summary

This is the best “move fast without painting yourself into a corner” option.

You keep the existing service-oriented model, move the containers to Azure Container Apps, replace local/Ollama with Azure OpenAI embeddings, put API Management and Entra in front of the Gateway, move the vector store to Azure Cosmos DB for NoSQL vector search, and decouple indexing with Service Bus.

### Azure service mapping

- **Gateway** -> Azure Container Apps
- **Index service** -> Azure Container Apps
- **Standards service** -> Azure Container Apps
- **Background indexing workers** -> Azure Container Apps Jobs or dedicated worker apps
- **Vector store + metadata** -> Azure Cosmos DB for NoSQL with vector search
- **Embedding generation** -> Azure OpenAI
- **Async ingestion orchestration** -> Azure Service Bus
- **Secrets** -> Azure Key Vault
- **AuthN/AuthZ edge** -> Azure API Management + Microsoft Entra ID
- **Observability** -> Azure Monitor + Application Insights + Log Analytics
- **Private access** -> VNet integration + Private Endpoints

### Why this is a strong fit

1. **Closest to your current shape**  
   Your current Gateway / Index / Standards split maps cleanly to Container Apps. That lowers migration risk.

2. **Good scaling model for mixed workloads**  
   Gateway can scale for bursty query traffic while index workers scale independently for ingestion/backfill jobs.

3. **Good enterprise posture without AKS overhead**  
   Container Apps gives you a managed platform with revisions, autoscaling, managed identity, and a secure environment boundary without needing to run Kubernetes yourself.

4. **Cosmos works if you want the database to be the application store**  
   Cosmos DB for NoSQL now supports vector indexing and search, and it lets vectors live beside the application document itself. If your “memory chunk” record is naturally a document with metadata, classification, repo/path/anchor, and embedding together, Cosmos is a sensible fit.

### Recommended logical design

#### Request path

Client / LLM / automation
-> Microsoft Entra token
-> Azure API Management
-> Gateway (Container Apps)
-> Index service / Standards service
-> Cosmos DB / Azure OpenAI / cache

#### Ingestion path

Repo event / manual index request / scheduled refresh
-> API Management
-> Gateway
-> Service Bus queue/topic
-> Index worker
-> Azure OpenAI embeddings
-> Cosmos DB upsert

### Auth and security model

#### Human callers

- Use Microsoft Entra ID for interactive users
- Put APIM in front of the Gateway
- Validate JWTs at APIM
- Pass user claims to the backend only after gateway validation
- Keep Gateway authorization focused on product rules (tool allow/deny, persona/classification, namespace routing)

#### Automation and AI workflows

- Prefer **managed identities** for Azure-native callers
- For non-Azure agents, use Entra app registrations with client credentials and narrowly scoped app roles
- Separate roles such as:
  - `rmembr.reader`
  - `rmembr.bundle_creator`
  - `rmembr.index_writer`
  - `rmembr.admin`

#### Service-to-service

- Replace `X-Internal-Token` over time with managed identity where possible
- If a temporary shared secret is needed during migration, keep it in Key Vault and rotate it on a schedule

#### Data protection

- Private Endpoints for Cosmos, Key Vault, and any storage accounts
- Disable public network access where feasible
- Keep Container Apps in a private environment where practical
- Log authz decisions and bundle explanations for auditability

### Data model recommendation for Cosmos

Use one main container for chunk documents with fields like:

- `id`
- `namespace`
- `repo`
- `path`
- `anchor`
- `ref`
- `classification`
- `persona_visibility`
- `content`
- `content_hash`
- `embedding`
- `updated_at`
- `standards_version`
- `metadata`

And separate containers for:

- bundle cache / bundle explanation records
- indexing job state
- policy bundles or policy snapshots if you want runtime policy version tracking

### Partitioning guidance

A naive partition on `namespace` alone may become too hot if automation pounds a single tenant. Consider a partition strategy closer to:

- `/tenantRepoKey` where value is something like `namespace|repo`

That preserves isolation and spreads traffic better than a single tenant-only partition in many cases.

### Pros

- Fastest enterprise-friendly path from your current design
- Managed platform with less ops than AKS
- Clean fit for document-style chunk storage
- Easy to add async scaling for automation-heavy indexing
- Strong Azure-native security posture

### Cons / watch-outs

- Cosmos is a good application database, but it is not automatically the best pure retrieval engine
- Relevance tuning and hybrid retrieval controls may feel less search-native than Azure AI Search
- RU and partition design need deliberate planning once automation traffic grows
- You will need disciplined modeling for cache, metadata, and query patterns to avoid expensive fan-out

### Best use case for Proposal A

Choose this if you want the most balanced answer across speed, maintainability, and Azure-native enterprise readiness.

---

# Proposal B — Retrieval-First Architecture
## Azure Container Apps + Azure AI Search + Blob/Storage + optional Cosmos/Postgres metadata

### Summary

This is the best option if you believe retrieval quality, hybrid search, indexing pipelines, and search operations will become the product’s center of gravity.

Instead of using Cosmos as the vector engine, use Azure AI Search as the retrieval layer and keep metadata/state elsewhere.

### Azure service mapping

- **Gateway / Index / Standards** -> Azure Container Apps
- **Search and vector retrieval** -> Azure AI Search
- **Raw memory pack content / snapshots / large artifacts** -> Blob Storage or ADLS
- **Operational metadata / cache / policy / jobs** -> Cosmos DB or PostgreSQL
- **Embeddings** -> Azure OpenAI
- **Async orchestration** -> Service Bus
- **Auth/security/observability** -> same as Proposal A

### Why this is compelling

Azure AI Search is more search-native than Cosmos. It supports vector search and can work with external vectorization or integrated chunking/vectorization pipelines. If your future roadmap includes hybrid ranking, search tuning, semantic ranking patterns, or multiple retrieval strategies, AI Search is usually the more natural home for the retrieval problem.

### Where it differs from Proposal A

- Search engine becomes specialized instead of embedded inside your operational database
- You likely keep authoritative metadata elsewhere
- Your chunk documents may exist in storage/metadata DB and be projected into a search index

### Pros

- Best retrieval-oriented platform of the options here
- Strong future path for hybrid search and richer retrieval tuning
- Cleaner separation between operational state and search index
- Easier to evolve toward sophisticated RAG/search patterns later

### Cons

- Slightly more moving parts than Proposal A
- More architecture work to keep search index and source-of-truth metadata synchronized
- May feel heavier than needed if your retrieval stays simple and curated

### Best use case for Proposal B

Choose this if you think “search quality and retrieval flexibility” matters more than “single database simplicity.”

---

# Proposal C — Minimal Change Path
## Azure Container Apps + Azure Database for PostgreSQL Flexible Server (pgvector)

### Summary

This is the lowest-change migration from your current implementation.

You largely preserve the existing pgvector mental model and move hosting and surrounding enterprise controls into Azure.

### Azure service mapping

- **Gateway / Index / Standards** -> Azure Container Apps
- **Vector + metadata store** -> Azure Database for PostgreSQL Flexible Server with pgvector
- **Embeddings** -> Azure OpenAI
- **Auth/security/observability** -> APIM, Entra, Key Vault, Azure Monitor
- **Async indexing** -> Service Bus + worker apps/jobs

### Why this is attractive

- Lowest rewrite risk in the data layer
- Easiest way to preserve existing ranking/query behavior early
- Existing developer knowledge around Postgres continues to apply

### Pros

- Minimum application refactor
- Familiar SQL and pgvector behavior
- Good if you want to get enterprise hosting online first, then revisit the vector engine later

### Cons

- You inherit more direct database tuning responsibility as scale grows
- Very high concurrency and mixed workload scaling may require more tuning than a more specialized managed search path
- Multi-tenant and workload-isolation strategies may need more engineering discipline over time

### Best use case for Proposal C

Choose this if the first objective is “productionize what we have” rather than “re-platform for the next phase.”

---

# Proposal D — Highest Control / Highest Complexity
## AKS + specialized data services

### Summary

This is the option for maximum control, maximum extensibility, and maximum platform overhead.

Run the services on AKS, keep APIM/Entra/Key Vault/Service Bus, and choose either Cosmos, AI Search, or PostgreSQL behind it.

### Why you might do it

- Need sidecars, custom networking, custom operators, or very specific runtime controls
- Have a platform team already operating AKS well
- Expect enough scale and tenancy complexity that the platform control is worth the cost

### Why I would not start here

For your current stage, this adds operational burden without solving the core product questions. You already have enough design work to do around auth, policy, tenancy, indexing, and retrieval quality. AKS is likely early unless you already know you need it.

### Best use case for Proposal D

Choose this only if your organization already standardizes heavily on AKS or you know Container Apps will not satisfy your runtime/networking requirements.

---

# 3. My recommendation

## Recommended path: Proposal A now, with Proposal B as the likely future evolution if retrieval needs dominate

That means:

### Phase 1

Build the enterprise version on:

- Azure Container Apps
- API Management
- Microsoft Entra ID
- Azure OpenAI
- Azure Cosmos DB vector search
- Service Bus
- Key Vault
- Azure Monitor

### Why

- It gets you out of localhost and into enterprise controls quickly
- It keeps your current service boundaries intact
- It is easier to scale and operate than AKS
- It gives you a strong Azure-native story for security and managed identity
- It gives you a decent vector store that keeps vectors with application documents

### Phase 2 checkpoint

After real usage data, revisit whether the retrieval tier should remain Cosmos or move to Azure AI Search.

That decision should be based on:

- observed latency under automation load
- relevance quality and ranking flexibility
- operational cost profile
- ease of supporting hybrid retrieval
- index management ergonomics

In other words: **I would not argue that Cosmos is wrong. I would argue that Cosmos is the best first enterprise Azure move if you want balanced simplicity, while AI Search is the stronger second-step option if retrieval sophistication becomes the core differentiator.**

---

# 4. Enterprise concerns you should formalize now

## Authentication

I would formalize two caller modes from day one:

1. **Interactive user mode**
   - Entra user tokens
   - group/app-role based authorization
   - user identity propagated for audit logs

2. **Automation/agent mode**
   - managed identity when Azure-hosted
   - client credentials when external
   - app roles with least privilege
   - rate limits and quotas separated from human traffic

## Authorization

Do not rely only on your current persona/classification model. Keep it, but add:

- app roles for tool access
- namespace/tenant scoping rules
- optional policy version stamping on bundle outputs
- strong denial defaults

## Network and exposure

- APIM should be the public front door
- Gateway should be private behind APIM if possible
- Index and Standards should not be public
- Cosmos/Search/Storage/Key Vault should use private connectivity when feasible

## Secrets and keys

- store secrets in Key Vault
- prefer managed identity over secrets whenever possible
- eliminate embedded tokens and static credentials over time

## Scalability

You mentioned a future where AI workflows hit this “at breakneck pace.” Design for that now by splitting:

- interactive bundle/search traffic
- indexing/update traffic
- standards/policy retrieval
- cache/state

That means queues, autoscaling, and workload isolation should be first-class design elements, not later add-ons.

## Multi-tenancy

Your current namespace model is a start, but enterprise use usually pushes you toward one of these:

- **soft multi-tenancy**: namespace in app layer, shared infra
- **pooled tenant model**: shared services, tenant-aware partitions and quotas
- **harder isolation for regulated tenants**: separate database/account/index per tenant or per trust boundary

I would start with pooled multi-tenancy plus strong per-tenant routing, quotas, and audit. Then decide later whether any tenant needs isolated infrastructure.

---

# 5. A practical target architecture I would put in front of leadership

## Production baseline

- **Azure API Management** as public API facade
- **Azure Container Apps Environment** hosting:
  - gateway-app
  - index-app
  - standards-app
  - index-worker
- **Azure Service Bus** for ingestion and reindex queues
- **Azure OpenAI** for embeddings
- **Azure Cosmos DB for NoSQL with vector search** for chunk + embedding storage
- **Azure Key Vault** for secrets/certs if needed
- **Azure Monitor / App Insights / Log Analytics** for telemetry
- **Private networking** for data services
- **Microsoft Entra ID** for human and app authentication

## Optional near-term additions

- Redis cache if bundle caching becomes hot-path critical
- Front Door if global routing or WAF requirements emerge
- separate worker apps for heavy backfills vs incremental indexing
- a policy admin service/UI later if policy lifecycle becomes operationally important

---

# 6. Decision matrix

| Option | Best For | Biggest Advantage | Biggest Risk |
|---|---|---|---|
| Proposal A: ACA + Cosmos | balanced enterprise move | fastest Azure-native production path | retrieval may later outgrow database-centric search |
| Proposal B: ACA + AI Search | retrieval-first product roadmap | strongest search-native capabilities | more moving parts and sync logic |
| Proposal C: ACA + PostgreSQL pgvector | minimal refactor | preserves existing behavior and team knowledge | more tuning burden at scale |
| Proposal D: AKS | maximum control | deepest platform flexibility | highest ops burden |

---

# 7. My blunt recommendation

If I were presenting this as an architecture proposal, I would say:

> Move the existing services to Azure Container Apps, put API Management and Entra in front of them, replace local embeddings with Azure OpenAI, add Service Bus for decoupled indexing, and use Cosmos DB vector search as the first enterprise-grade vector store. Keep the data contract and service boundaries stable so that the retrieval layer can later move to Azure AI Search if real-world search quality or scale proves that specialized search is the better long-term choice.

That gives you a practical enterprise path without committing too early to the most complex option.

---

# Sources

- Uploaded architecture brief provided by user
- Azure Architecture Center: Choose an Azure Service for Vector Search — https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/vector-search
- Azure Cosmos DB vector search — https://learn.microsoft.com/en-us/azure/cosmos-db/vector-search
- Azure AI Search vector search overview — https://learn.microsoft.com/en-us/azure/search/vector-search-overview
- Azure Container Apps managed identity — https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
- Azure Container Apps authentication — https://learn.microsoft.com/en-us/azure/container-apps/authentication
- Azure API Management with OAuth 2.0 / Entra ID — https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-protect-backend-with-aad
- Azure Database for PostgreSQL pgvector — https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector
- Azure Private Endpoint overview — https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview
- Azure Key Vault overview — https://learn.microsoft.com/en-us/azure/key-vault/general/overview
- Azure Service Bus managed identity — https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity
