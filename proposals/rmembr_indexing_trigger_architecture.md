
# rMEMbr Indexing Trigger Architecture
## Event-Driven Indexing with Pipelines, Connectors, and Azure Service Bus

---

# 1. Purpose

This document defines the **indexing trigger architecture** for rMEMbr in the Azure enterprise deployment.

The goal is to provide a **scalable, event-driven mechanism** for updating the vector index when source content changes, while preserving the federated retrieval model.

Key design goals:

- Avoid constant scanning of repositories and documentation systems
- Preserve systems of record (GitHub, Azure DevOps, Confluence, etc.)
- Ensure indexing logic exists in a **centralized worker system**
- Support **multiple change detection mechanisms**
- Provide **enterprise-grade reliability and scalability**
- Maintain **source-agnostic indexing workflows**

---

# 2. Core Principle

Indexing should be **event-driven**, not scan-driven.

Whenever possible, source systems should **publish a change event** that triggers indexing.

All indexing requests must be routed through **Azure Service Bus**, which acts as the centralized asynchronous trigger mechanism.

This architecture ensures that:

- indexing workloads do not block user requests
- indexing is consistent across all source types
- retries and failures are handled reliably
- indexing workloads scale independently of the API layer

---

# 3. Architecture Overview

```
Source Change Detected
        |
        v
Event Producer
(ADO Pipeline / Webhook / Poller / Admin)
        |
        v
Azure Service Bus
(reindex queue)
        |
        v
Index Worker Services
(Container Apps)
        |
        v
Connector Layer
(GitHub / ADO / Confluence / etc.)
        |
        v
Content Retrieval
        |
        v
Chunking + Embeddings
        |
        v
Cosmos DB Vector Index Update
        |
        v
Cache Invalidation
(Redis / Blob)
```

This ensures that all indexing is processed through a **single centralized indexing pipeline**.

---

# 4. Repository-Based Indexing (Pipeline Trigger Model)

For repository-hosted content (GitHub, Azure DevOps repos), indexing should be triggered by **CI/CD pipelines or repository webhooks**.

Example rule:

```
Any file change in `.ai/**` triggers a reindex event.
```

Recommended subpaths:

```
.ai/memory/**
.ai/standards/**
.ai/policies/**
```

Example workflow:

```
Developer commits change to .ai/memory/design.md
        |
        v
Pipeline detects path change
        |
        v
Pipeline publishes reindex event to Service Bus
        |
        v
Index worker retrieves updated file
        |
        v
Embeddings generated
        |
        v
Cosmos metadata updated
        |
        v
Cache invalidation triggered
```

The pipeline should **not perform indexing itself**.

The pipeline is only responsible for **publishing the reindex event**.

---

# 5. Non-Repository Sources

Some systems do not provide clean pipeline or webhook triggers.

Examples include:

- Confluence
- SharePoint
- Azure DevOps Wikis
- legacy documentation systems

These systems require **connector-based change detection**.

Possible approaches include:

### Option 1 — Webhook-Based

If supported by the system:

```
System webhook → publish reindex event
```

### Option 2 — Polling Connector

A connector periodically checks for updates:

```
Poll source for changes since last checkpoint
        |
        v
Publish reindex events
```

### Option 3 — Scheduled Refresh

Used when change detection is unreliable.

```
Scheduled job publishes refresh events
```

Even in these scenarios, indexing must still be triggered via **Service Bus**.

---

# 6. Event Contract

All change detection mechanisms must publish a **standardized indexing event**.

Example message:

```json
{
  "eventType": "reindex.requested",
  "sourceType": "azure-devops-repo",
  "sourceId": "project/repo",
  "location": ".ai/memory/design.md",
  "scope": "file",
  "tenant": "enterprise",
  "namespace": "platform-team",
  "changeType": "modified",
  "version": "commit-sha",
  "requestedBy": "pipeline"
}
```

Example Confluence event:

```json
{
  "eventType": "reindex.requested",
  "sourceType": "confluence",
  "sourceId": "architecture-space",
  "location": "page/12345",
  "scope": "document",
  "tenant": "enterprise",
  "namespace": "architecture",
  "changeType": "modified",
  "version": "page-version",
  "requestedBy": "poller"
}
```

Example full refresh:

```json
{
  "eventType": "reindex.requested",
  "sourceType": "azure-devops-repo",
  "sourceId": "project/repo",
  "scope": "repository",
  "tenant": "enterprise",
  "namespace": "platform-team",
  "changeType": "refresh",
  "requestedBy": "scheduled-job"
}
```

---

# 7. Worker Responsibilities

Index worker services consume messages from the **Service Bus reindex queue**.

Workers perform the following tasks:

1. Parse event message
2. Select appropriate source connector
3. Retrieve authoritative content
4. Normalize content format
5. Chunk documents for indexing
6. Generate embeddings
7. Update Cosmos vector metadata
8. Invalidate relevant cache entries
9. Optionally refresh blob cache

Workers run as **Azure Container Apps** and scale automatically based on queue depth.

---

# 8. Benefits of the Event-Driven Model

## Reduced System Load

Continuous repository scanning is eliminated.

## Faster Index Updates

Changes are processed immediately after detection.

## Scalable Indexing

Workers scale independently of the API layer.

## Unified Processing Model

All sources feed into the same indexing workflow.

## Enterprise Reliability

Azure Service Bus provides:

- message durability
- retries
- dead-letter queues
- backpressure handling

---

# 9. Why Azure Service Bus

Azure Service Bus provides enterprise messaging features required for this architecture.

Capabilities include:

- durable message delivery
- retry policies
- dead-letter queues
- FIFO ordering
- pub/sub topics
- horizontal worker scaling
- message sessions for advanced workflows

These features make it suitable for large-scale indexing workloads.

---

# 10. Future Scaling Considerations

As rMEMbr adoption grows, indexing workloads may increase due to:

- large repository sets
- documentation growth
- AI-driven automation workflows
- mass reindex events during schema updates

The event-driven architecture ensures the platform can handle:

- thousands of indexing events
- burst workloads
- asynchronous reprocessing jobs

without impacting the user-facing API performance.

---

# 11. Summary

The rMEMbr indexing architecture follows a **federated, event-driven model**.

Key principles:

- Source systems remain the **systems of record**
- Pipelines and connectors detect content changes
- All indexing requests are published to **Azure Service Bus**
- Centralized worker services perform indexing
- Cosmos DB stores vectors and source metadata
- Redis and Blob provide performance caching layers

This architecture ensures indexing is:

- scalable
- reliable
- consistent
- source-agnostic
