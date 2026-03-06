---
title: rmembr Memory Pack
---

# rmembr: AI-Indexed Notes

This directory is intended to be indexed by the “targeted memory” system implemented in this repo.

## Start Here

- [instructions.md](instructions.md): what this repo is, what’s “source of truth”, and how to run it
- [repo-layout.md](repo-layout.md): where code and docs live

## System Reference

- [system-architecture.md](system-architecture.md): components, ranking pipeline, MCP server, observability, and request/data flows
- [api-and-tools.md](api-and-tools.md): Gateway/Index/Standards tool contracts (HTTP)
- [contract-spec.md](contract-spec.md): canonical tool schema and compatibility rules
- [data-model.md](data-model.md): Postgres tables + key constraints
- [configuration.md](configuration.md): env vars, policy, ranking, MCP, and runtime config
- [security.md](security.md): internal auth, policy-based persona filtering, input validation
- [policy-and-authz.md](policy-and-authz.md): role-based tool access, budget policy, and deny behavior
- [providers.md](providers.md): filesystem and GitHub provider behavior and cache semantics
- [mcp-client-integration.md](mcp-client-integration.md): transport/client setup decisions for VS Code, Claude, and Codex
- [slo-observability.md](slo-observability.md): SLO targets, metrics, dashboards, and alert rules
- [test-contracts-and-quality-gates.md](test-contracts-and-quality-gates.md): what must pass for schema, transport, and latency
- [operations-troubleshooting.md](operations-troubleshooting.md): runbooks and common failures
- [operations-runbook-condensed.md](operations-runbook-condensed.md): incident response quick reference

## Authoring Memory Packs

- [memory-pack-authoring.md](memory-pack-authoring.md): how to write `/.ai/memory/**` content so it chunks and retrieves well
