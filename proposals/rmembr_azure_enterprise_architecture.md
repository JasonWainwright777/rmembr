# rMEMbr Azure Enterprise Architecture Recommendation

## Overview

This document summarizes a recommended Azure architecture for deploying
the rMEMbr MCP system in an enterprise environment. The goal is to
preserve the current microservice design while adding enterprise
requirements such as:

-   Private networking
-   Enterprise authentication
-   Secure service-to-service communication
-   Scalable storage and vector search
-   Automation-friendly architecture
-   Observability and operational controls

The current local architecture consists of containerized services
including Gateway, Index, and Standards components along with storage
and embeddings services. This maps well to a cloud-native microservice
architecture.

------------------------------------------------------------------------

# Core Azure Architecture Recommendation

**Primary Stack**

-   Azure Container Apps
-   Azure Cosmos DB (Vector Search)
-   Azure Blob Storage
-   Azure Service Bus
-   Microsoft Entra ID
-   Azure Key Vault
-   Private Endpoints + Private DNS
-   Optional Azure API Management

This architecture provides a balance between scalability, operational
simplicity, and enterprise security requirements.

------------------------------------------------------------------------

# Compute Layer

## Azure Container Apps

Container Apps should host the main services:

-   Gateway Service
-   Index Service
-   Standards Service

Reasons for choosing Container Apps:

-   Native VNet integration
-   Private ingress support
-   Autoscaling
-   Managed identities
-   Simpler operational model than AKS
-   Supports both HTTP and queue-driven workloads

Container Apps environments can be deployed directly into private VNets.

------------------------------------------------------------------------

# Data Storage

## Azure Cosmos DB (Vector Search)

Cosmos DB will store:

-   Vector embeddings
-   Chunk metadata
-   Repository metadata
-   Namespace / tenant boundaries
-   Retrieval metadata

Advantages:

-   Native vector search support
-   Horizontally scalable
-   Low latency
-   Partitioning for tenant isolation

Cosmos DB should store **metadata and vectors**, not large file
payloads.

------------------------------------------------------------------------

## Azure Blob Storage

Blob Storage should store:

-   Raw source documents
-   Normalized markdown artifacts
-   Cached file bundles
-   Debug exports
-   Archive snapshots

This keeps Cosmos optimized for queryable metadata while Blob stores
large objects cheaply.

------------------------------------------------------------------------

# Messaging and Automation

## Azure Service Bus

Service Bus should manage asynchronous workloads:

-   Indexing jobs
-   Reindex operations
-   Automation-triggered tasks
-   Bulk refresh operations

This separates automation traffic from interactive MCP queries.

Benefits:

-   Durable queueing
-   Backpressure control
-   Event-driven scaling
-   Isolation of indexing workloads

------------------------------------------------------------------------

# Authentication and Security

## Microsoft Entra ID

External clients authenticate using Entra ID.

Flow:

Client → Gateway → Internal Services

-   Gateway validates JWT tokens
-   Role-based access using groups or app roles
-   Supports enterprise SSO and auditing

------------------------------------------------------------------------

## Managed Identities

Service-to-service authentication should use Managed Identity instead of
shared secrets.

Examples:

-   Gateway accessing Cosmos DB
-   Index service accessing Blob storage
-   Services accessing Key Vault

------------------------------------------------------------------------

## Azure Key Vault

Key Vault stores:

-   Secrets
-   Certificates
-   Signing keys
-   External API credentials

All services should access secrets through managed identity.

------------------------------------------------------------------------

# Networking Architecture

## Private VNet Architecture

All services should be deployed within a private VNet environment.

Key principles:

-   No public access to databases
-   Private endpoints for PaaS services
-   Private DNS zones for service resolution

Components with Private Endpoints:

-   Cosmos DB
-   Blob Storage
-   Key Vault
-   Azure OpenAI (if used)
-   Container Apps Environment

------------------------------------------------------------------------

# Optional Gateway Layer

## Azure API Management

API Management can be added in front of the Gateway service to provide:

-   Rate limiting
-   Request throttling
-   Policy enforcement
-   Logging
-   Centralized API management

This is optional but recommended for large enterprise environments.

------------------------------------------------------------------------

# Workload Separation

The system should separate two traffic patterns.

## Interactive Traffic

Used by human users and LLM tools.

Flow:

Client → Gateway → Index → Cosmos → Blob

Characteristics:

-   Low latency
-   Smaller request volume
-   Immediate responses

------------------------------------------------------------------------

## Automation Traffic

Used by CI/CD, AI workflows, and system automation.

Flow:

Automation → Service Bus → Worker Containers

Characteristics:

-   Burst traffic
-   Heavy indexing operations
-   Background processing

This separation protects user-facing latency.

------------------------------------------------------------------------

# Scaling Model

Initial stage:

-   Dozens of users
-   Moderate automation
-   Minimal indexing bursts

Growth stage:

-   Hundreds of users
-   Heavy automation pipelines
-   Continuous indexing

Container Apps scaling allows:

-   HTTP-based scaling
-   Queue-triggered scaling
-   Event-driven scaling

------------------------------------------------------------------------

# Why Not Azure Functions as Primary Platform

Azure Functions can integrate with VNets, but they are not ideal as the
main runtime because:

-   The MCP architecture is service-based rather than event-based
-   Always-warm service behavior is preferable
-   Service-to-service communication is easier with containers

Functions can still be used for:

-   Webhook triggers
-   Scheduled maintenance jobs
-   Lightweight event handlers

------------------------------------------------------------------------

# Alternative Platform Options

## Option 1 --- Container Apps (Recommended)

Pros:

-   Simplest operations
-   Native scaling
-   Full VNet support
-   Managed identity integration

Cons:

-   Slightly less control than AKS

------------------------------------------------------------------------

## Option 2 --- AKS

Pros:

-   Maximum control
-   Advanced networking
-   Sidecar capabilities

Cons:

-   Operational overhead
-   Kubernetes management complexity

Use AKS only if deep platform control is required.

------------------------------------------------------------------------

# Final Recommendation

Recommended stack:

Azure Container Apps\
Azure Cosmos DB (Vector Search)\
Azure Blob Storage\
Azure Service Bus\
Microsoft Entra ID\
Azure Key Vault\
Private Endpoints + Private DNS\
Optional Azure API Management

This architecture provides:

-   Enterprise security
-   Scalable vector retrieval
-   Private network isolation
-   Clean separation of workloads
-   Room to scale from dozens to hundreds of users and heavy automation
    workloads.
