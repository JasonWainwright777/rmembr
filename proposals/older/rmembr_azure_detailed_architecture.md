# rMEMbr Azure Enterprise Architecture -- Detailed Design

## Purpose

This document expands the previous architecture recommendation and
includes:

-   Azure architecture diagram
-   Network topology design
-   Cosmos DB data model proposal
-   Scaling considerations
-   Migration plan from local containers to Azure

The goal is to move the current **five-container local MCP
architecture** into a secure, scalable Azure enterprise deployment.

------------------------------------------------------------------------

# High-Level Architecture

                    +---------------------------+
                    |       Client Systems      |
                    |  LLMs / Dev Tools / CI   |
                    +-------------+-------------+
                                  |
                                  |
                            Entra ID Auth
                                  |
                                  v
                     +---------------------------+
                     |   Azure API Management    |
                     |  (optional enterprise)    |
                     +-------------+-------------+
                                   |
                                   v
                    +-----------------------------+
                    |        Gateway Service      |
                    |     Azure Container App     |
                    +--------------+--------------+
                                   |
                                   |
                 +-----------------+------------------+
                 |                                    |
                 v                                    v
       +---------------------+             +---------------------+
       |     Index Service   |             |   Standards Service |
       |  Azure Container    |             |  Azure Container    |
       |       App           |             |       App           |
       +----------+----------+             +----------+----------+
                  |                                   |
                  |                                   |
                  v                                   v
         +------------------+              +------------------+
         |   Cosmos DB      |              |   Blob Storage   |
         |  Vector Search   |              |  File Cache      |
         +------------------+              +------------------+
                  |
                  |
                  v
          +------------------+
          |  Azure Service   |
          |      Bus         |
          | Async Processing |
          +------------------+

------------------------------------------------------------------------

# Azure Network Topology

All components should live inside a **private VNet**.

    Azure VNet
    │
    ├── Subnet: container-apps
    │      ├ Gateway Service
    │      ├ Index Service
    │      └ Standards Service
    │
    ├── Subnet: private-endpoints
    │      ├ Cosmos DB Private Endpoint
    │      ├ Blob Storage Private Endpoint
    │      ├ Key Vault Private Endpoint
    │      └ OpenAI Private Endpoint
    │
    ├── Subnet: integration
    │      └ Service Bus
    │
    └── Private DNS Zones
           ├ privatelink.documents.azure.com
           ├ privatelink.blob.core.windows.net
           └ privatelink.vaultcore.azure.net

Public access should be disabled wherever possible.

------------------------------------------------------------------------

# Container Apps Layout

Recommended services:

  Service     Purpose
  ----------- ----------------------------------------------
  Gateway     MCP endpoint, auth validation, orchestration
  Index       embedding generation + indexing
  Standards   policy/standards retrieval
  Workers     async indexing tasks

Container Apps benefits:

-   autoscaling
-   managed identity support
-   VNet integration
-   revision-based deployments

------------------------------------------------------------------------

# Cosmos DB Data Model

Recommended containers.

## chunks

Stores text fragments used for retrieval.

Example document:

    {
      "id": "chunk_123",
      "repo": "repo-name",
      "path": "docs/file.md",
      "chunk_index": 3,
      "embedding": [0.123, 0.999, ...],
      "blob_uri": "https://storage/...",
      "namespace": "teamA"
    }

Partition key recommendation:

    /namespace

Alternative:

    /repo

------------------------------------------------------------------------

## repositories

Stores repo metadata.

    {
      "id": "repo1",
      "namespace": "teamA",
      "lastIndexed": "2026-01-01",
      "branch": "main"
    }

------------------------------------------------------------------------

## namespaces

Tenant or organization separation.

    {
      "id": "namespaceA",
      "owner": "teamA",
      "retentionPolicy": "30d"
    }

------------------------------------------------------------------------

# Blob Storage Layout

Recommended container structure.

    storage-account
    │
    ├ source-cache
    │   └ raw repo files
    │
    ├ normalized-docs
    │   └ markdown chunks
    │
    ├ context-bundles
    │   └ prebuilt context packages
    │
    └ archives
        └ historical snapshots

Blob storage stores large content while Cosmos stores metadata.

------------------------------------------------------------------------

# Service Bus Queues

Recommended queues.

  Queue               Purpose
  ------------------- ----------------------------
  index_repo          reindex a repository
  refresh_namespace   rebuild namespace cache
  automation_jobs     bulk automation workflows
  maintenance         cleanup / compaction tasks

Worker containers can scale based on queue depth.

------------------------------------------------------------------------

# Authentication Model

## External Access

Client → Gateway

Authentication:

-   Microsoft Entra ID
-   OAuth tokens
-   group-based authorization

------------------------------------------------------------------------

## Internal Access

Service-to-service communication should use **Managed Identity**.

Example:

Gateway → Cosmos DB\
Index → Blob Storage\
Workers → Service Bus

No shared internal secrets required.

------------------------------------------------------------------------

# Observability

Recommended stack.

-   Application Insights
-   Log Analytics
-   Azure Monitor
-   Distributed tracing

Metrics to track:

-   vector search latency
-   queue backlog
-   indexing duration
-   cache hit ratio

------------------------------------------------------------------------

# Scaling Model

## Phase 1

-   dozens of users
-   low indexing load

Container Apps minimum replicas: 1--2

------------------------------------------------------------------------

## Phase 2

-   hundreds of users
-   heavy automation

Scale characteristics:

-   Gateway scales by HTTP load
-   workers scale by queue depth
-   Cosmos scales by RU consumption

------------------------------------------------------------------------

# Migration Plan

## Phase 1 -- Lift and Shift

Goal:

Run existing containers in Azure.

Steps:

1.  Build container images
2.  Deploy Container Apps environment
3.  Connect to Blob + Cosmos
4.  Disable public network access

------------------------------------------------------------------------

## Phase 2 -- Enterprise Security

Add:

-   Entra ID authentication
-   managed identities
-   private endpoints
-   Key Vault integration

------------------------------------------------------------------------

## Phase 3 -- Automation and Scaling

Add:

-   Service Bus queues
-   worker containers
-   auto scaling rules

------------------------------------------------------------------------

## Phase 4 -- Optimization

Possible improvements:

-   Azure AI Search hybrid retrieval
-   distributed cache layer
-   multi-region failover

------------------------------------------------------------------------

# Future Enhancements

Potential future upgrades.

-   global deployments
-   regional index replication
-   tenant isolation per Cosmos account
-   AI-powered relevance ranking
-   MCP federation across teams

------------------------------------------------------------------------

# Summary

Recommended Azure stack.

-   Azure Container Apps
-   Azure Cosmos DB (Vector Search)
-   Azure Blob Storage
-   Azure Service Bus
-   Microsoft Entra ID
-   Azure Key Vault
-   Private Endpoints
-   Optional Azure API Management

This architecture supports:

-   private enterprise networking
-   scalable AI context retrieval
-   hundreds of users
-   heavy automation workloads
