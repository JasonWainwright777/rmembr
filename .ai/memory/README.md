---
title: rmembr Memory Pack
---

# rmembr: AI-Indexed Notes

This directory is intended to be indexed by the “targeted memory” system implemented in this repo.

## Start Here

- [instructions.md](instructions.md): what this repo is, what’s “source of truth”, and how to run it
- [repo-layout.md](repo-layout.md): where code and docs live

## System Reference

- [system-architecture.md](system-architecture.md): components and request/data flows
- [api-and-tools.md](api-and-tools.md): Gateway/Index/Standards tool contracts (HTTP)
- [data-model.md](data-model.md): Postgres tables + key constraints
- [configuration.md](configuration.md): env vars and runtime config hotspots
- [security.md](security.md): internal auth, persona/classification filtering, input validation
- [operations-troubleshooting.md](operations-troubleshooting.md): runbooks and common failures

## Authoring Memory Packs

- [memory-pack-authoring.md](memory-pack-authoring.md): how to write `/.ai/memory/**` content so it chunks and retrieves well
