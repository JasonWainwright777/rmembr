---
title: Docker Container Standards
domain: docker
standard_id: enterprise/docker/container-standards
version: v1
classification: internal
---

# Docker Container Standards

## Overview

All containerized applications must follow these standards to ensure security, consistency, and operational readiness across environments.

## Base Images

- Use only approved base images from the internal container registry
- Approved bases: `mcr.microsoft.com/dotnet/aspnet`, `mcr.microsoft.com/dotnet/sdk`, `node:lts-alpine`, `python:3.12-slim`
- Never use `latest` tags in Dockerfiles — always pin to a specific version
- Rebuild images weekly to pick up OS-level security patches

## Dockerfile Requirements

### Multi-Stage Builds
- All production images must use multi-stage builds to minimize image size
- Build dependencies must not be present in the final stage

### Example Structure
```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app .
USER app
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### Security
- Never run containers as root — use `USER` directive
- Do not embed secrets in images — use environment variables or mounted secrets
- Include a `.dockerignore` to exclude sensitive files, build artifacts, and `.git/`
- Scan all images with Trivy or equivalent before pushing to registry

### Health Checks
- All services must define a `HEALTHCHECK` in the Dockerfile or a `healthcheck` in docker-compose
- Health endpoints must respond within 3 seconds
- Use `curl` or a lightweight binary for health probes — do not install unnecessary tools

## Docker Compose Conventions

- Use `depends_on` with `condition: service_healthy` for startup ordering
- Externalize all configuration via environment variables with sensible defaults
- Use named volumes for persistent data — never bind-mount host paths in production
- Use bridge networks for service isolation
- Optional services should use `profiles` to avoid starting by default

## Image Tagging

- Tag images with the git SHA and semantic version: `myapp:1.2.3` and `myapp:abc1234`
- Never push untagged images to shared registries
- Use immutable tags in production deployments
