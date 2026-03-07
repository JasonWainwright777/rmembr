# Suggested Next Steps for rMEMbr Azure Enterprise Design

Prepared for Jason Wainwright  
Date: March 7, 2026

## 1. Decisions to make next

1. Confirm whether the first production milestone is:
   - fastest secure enterprise deployment
   - best retrieval quality
   - lowest refactor
   - strongest tenant isolation

2. Decide whether tenants are:
   - internal teams only
   - internal teams plus automation identities
   - future external or partner tenants

3. Decide whether indexing is:
   - event-driven from repo changes
   - scheduled batch refresh
   - both

4. Decide whether standards/policy content is:
   - mostly static
   - frequently changed
   - centrally governed by one team
   - delegated per tenant/team

## 2. Technical spikes I would run

### Spike A — Cosmos suitability test

Measure:
- top-k query latency under parallel load
- RU cost under human traffic vs automation traffic
- partition hot-spot behavior
- cache hit rates for context bundles

### Spike B — AI Search comparison test

Measure against the same corpus:
- relevance quality
- latency
- operational complexity
- ease of hybrid filtering and ranking

### Spike C — Auth and policy test

Validate:
- human interactive auth via Entra
- app-to-app auth via managed identity/client credentials
- role-based tool restrictions
- classification filtering and audit output

### Spike D — Scaling test

Validate separately:
- query path saturation
- indexing backlog drain rate
- retry behavior for embedding failures
- effect of automation bursts on interactive latency

## 3. Initial nonfunctional requirements to define

You will get better architecture decisions if these are written down early:

- p50 and p95 latency targets for `search_repo_memory`
- p50 and p95 latency targets for `get_context_bundle`
- maximum tolerated indexing lag
- retention period for cached bundles and explanation records
- target recovery objectives
- audit retention expectations
- tenant isolation requirements

## 4. Security work items

- define app roles and scopes
- define managed identity usage by service
- define private networking requirements
- define secret rotation policy for anything still secret-based
- define logging and audit requirements for policy denials and bundle assembly

## 5. Migration sequence I would use

1. Containerize and deploy current services into a non-prod Container Apps environment
2. Add APIM and Entra in front of the Gateway
3. Add Key Vault and remove local secret handling
4. Replace local embeddings with Azure OpenAI
5. Introduce Service Bus and async indexing workers
6. Migrate vector store to Cosmos in a shadow or dual-write mode
7. Run load and relevance comparisons
8. Decide whether to keep Cosmos or pivot retrieval to AI Search

## 6. Output I would produce next for you

The next useful design package would probably be:

- a target Azure architecture diagram
- a phase-by-phase migration plan
- a security model draft
- an identity and role matrix
- a service-by-service Azure resource bill of materials
- a decision matrix with weighted scoring

## Sources

- Uploaded architecture brief provided by user
- Azure Architecture Center: Choose an Azure Service for Vector Search — https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/vector-search
- Azure Cosmos DB vector search — https://learn.microsoft.com/en-us/azure/cosmos-db/vector-search
- Azure AI Search vector search overview — https://learn.microsoft.com/en-us/azure/search/vector-search-overview
- Azure API Management with OAuth 2.0 / Entra ID — https://learn.microsoft.com/en-us/azure/api-management/api-management-howto-protect-backend-with-aad
