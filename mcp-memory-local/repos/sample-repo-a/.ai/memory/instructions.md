---
title: Sample Repo A Instructions
priority: must-follow
---

# Repo A Development Instructions

## Architecture

This repo follows a clean architecture pattern:
- `src/Api/` — HTTP API layer (controllers, middleware)
- `src/Domain/` — Business logic and domain entities
- `src/Infrastructure/` — Data access, external services

## Branching Strategy

- `main` — production-ready code
- `develop` — integration branch
- Feature branches: `feature/<ticket-id>-<description>`

## Terraform Modules

All infrastructure is in `infra/`. Modules are pinned to exact versions per enterprise standard. See `enterprise/terraform/module-versioning` for version pinning rules.

## Pipeline Configuration

CI/CD uses the enterprise job templates v3. See `enterprise/ado/pipelines/job-templates-v3` for approved templates.

## Local Development

1. Install .NET 8 SDK
2. Run `dotnet restore`
3. Set connection string in user secrets
4. Run `dotnet run --project src/Api`
