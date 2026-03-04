---
title: ADO Pipeline Job Templates v3
domain: ado
standard_id: enterprise/ado/pipelines/job-templates-v3
version: v3
classification: internal
---

# Azure DevOps Pipeline Job Templates v3

## Overview

All CI/CD pipelines must use the approved job templates from the shared templates repository. Direct `script:` tasks for build/test/deploy steps are not permitted in production pipelines.

## Approved Templates

### Build Templates
- `build/dotnet-build.yml` — .NET application builds
- `build/node-build.yml` — Node.js application builds
- `build/docker-build.yml` — Container image builds

### Test Templates
- `test/unit-tests.yml` — Unit test execution
- `test/integration-tests.yml` — Integration test execution
- `test/security-scan.yml` — SAST/DAST scanning

### Deploy Templates
- `deploy/aks-deploy.yml` — AKS deployment
- `deploy/app-service-deploy.yml` — Azure App Service deployment

## Usage

```yaml
stages:
  - stage: Build
    jobs:
      - template: build/dotnet-build.yml@templates
        parameters:
          project: src/MyApp/MyApp.csproj
          configuration: Release

  - stage: Test
    jobs:
      - template: test/unit-tests.yml@templates
        parameters:
          project: tests/MyApp.Tests/MyApp.Tests.csproj
```

## Migration from v2

- Replace `build-step` with `build/<type>-build.yml`
- Add explicit `configuration` parameter (no longer defaults to Debug)
- Security scanning is now mandatory — add `test/security-scan.yml` stage
