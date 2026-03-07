# Recommendation Memo: rMEMbr Enterprise Move to Azure

Prepared for Jason Wainwright  
Date: March 7, 2026

## Executive recommendation

My recommendation is to move rMEMbr into Azure using **Azure Container Apps + Azure API Management + Microsoft Entra ID + Azure OpenAI + Azure Cosmos DB vector search + Service Bus**, while deliberately keeping the retrieval contract abstract enough that Azure AI Search can replace the vector tier later if search sophistication becomes the main product differentiator.

## Why this is the right first move

- It preserves the current service split, so the application does not need a deep rewrite just to become enterprise-ready.
- It adds the enterprise controls that are missing today: authentication, authorization, private networking, secrets management, observability, and scalable background processing.
- It scales well for the mixed demand profile you described: a smaller number of human users plus a potentially much larger volume of automation and AI-driven calls.
- It avoids the operational overhead of AKS until there is a proven need for that level of runtime control.

## Why I am not recommending AI Search first

Azure AI Search is likely the stronger long-term retrieval platform if search quality, hybrid ranking, and retrieval tuning become central. But for the first enterprise move, Cosmos is a simpler fit because it can hold the chunk document and its embedding together in one operational store. That is attractive while you are still proving scale patterns, tenancy patterns, and product behavior.

## Why I am not recommending PostgreSQL first

PostgreSQL with pgvector is still a valid option and is the least disruptive technically. I am not ranking it first because your question is not just “how do I host this,” it is “how do I make this enterprise-scale and support automation at pace.” For that broader question, the Azure-native path built around managed identity, APIM, queues, and a document/vector store gives you a cleaner enterprise story.

## Target production shape

- APIM is the public API boundary
- Entra ID issues tokens for humans and apps
- Gateway runs in Container Apps and remains the main MCP/API entry point
- Indexing runs asynchronously through Service Bus and dedicated workers
- Cosmos stores chunk records, embeddings, and related metadata
- Azure OpenAI generates embeddings
- Key Vault stores anything that cannot yet be replaced by managed identity
- Azure Monitor / App Insights provide traces, metrics, and audit support

## Key design principles to lock now

1. **Separate read-path from write-path scaling**  
   Query traffic and indexing traffic should never compete for the same resources.

2. **Use identity, not shared secrets**  
   Managed identities and Entra app roles should replace ad hoc internal tokens over time.

3. **Make tenant and policy decisions visible**  
   Every bundle should be explainable by policy version, classification rule, and caller identity.

4. **Keep the retrieval interface stable**  
   The application should depend on a retrieval abstraction, not on Cosmos-specific logic everywhere.

5. **Design for automation explicitly**  
   Automation needs quotas, queueing, retry policies, and separate scaling controls.

## Suggested rollout

### Step 1
Lift the existing services into Container Apps with APIM, Entra, Key Vault, and Azure Monitor.

### Step 2
Replace local embeddings with Azure OpenAI.

### Step 3
Move indexing to an asynchronous queue-based flow using Service Bus.

### Step 4
Implement Cosmos vector storage and run side-by-side tests against the current pgvector behavior.

### Step 5
Load test human traffic and automation traffic separately.

### Step 6
Decide whether retrieval stays on Cosmos or moves to AI Search based on observed behavior, not preference alone.

## Closing view

This approach gives you a realistic enterprise landing zone now and preserves optionality later. That is the part I like most about it: it solves the urgent enterprise concerns without forcing you to decide, too early, what the forever retrieval engine must be.

## Sources

- Uploaded architecture brief provided by user
- Azure Architecture Center: Choose an Azure Service for Vector Search — https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/vector-search
- Azure Cosmos DB vector search — https://learn.microsoft.com/en-us/azure/cosmos-db/vector-search
- Azure AI Search vector search overview — https://learn.microsoft.com/en-us/azure/search/vector-search-overview
