# rMEMbr Sample Showcase Prompts

Prompts demonstrating what rMEMbr can do as a Federated Context Retrieval System.

## Semantic Search

> "Search rMEMbr for how authentication works in the gateway"

> "Search the repo memory for chunking strategy and anchor stability"

> "What does rMEMbr know about the provider framework?"

## Context Bundles (Core Feature)

> "Get me a context bundle for adding a new MCP tool to the gateway"

> "I'm about to refactor the ranking pipeline — pull a context bundle so I don't break anything"

> "Assemble context for debugging why bundle cache TTL isn't being respected"

## Bundle Explainability

> "Explain how that last bundle was assembled — why were those chunks selected?"

Uses `explain_context_bundle` on a previously returned bundle ID.

## Enterprise Standards

> "List all available enterprise standards"

> "Show me the API versioning standard"

> "Pull the schema for the logging standard so I can validate my service"

## Indexing & Validation

> "Index the rmembr repo — I just updated the memory files"

> "Re-index all repos after pulling new changes"

> "Validate that the rmembr memory pack is indexed and queryable"

## Persona-Filtered Context

> "Get a context bundle for deploying to production, filtered for the agent persona"

> "Pull context as an external consumer — what would a third-party integration see?"

## Real Workflow Scenarios

> "I'm adding GitHub Actions CI to this repo. Pull context so I understand the Docker setup, env vars, and any relevant standards."

> "A new developer is onboarding — what does rMEMbr know about running the stack locally and the architecture?"

> "I need to add a new service to docker-compose. What patterns should I follow based on the existing services?"
