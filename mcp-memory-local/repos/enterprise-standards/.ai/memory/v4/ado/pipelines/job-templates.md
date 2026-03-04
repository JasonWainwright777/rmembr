---
title: ADO Pipeline Job Templates v4
domain: ado
standard_id: enterprise/ado/pipelines/job-templates
version: v4
classification: internal
---

# Azure DevOps Pipeline Job Templates (v4)

## Overview

All CI/CD pipelines must use the approved job templates from the shared templates repository. Version 4 introduces mandatory SBOM generation and supply chain attestation.

## Changes from v3

- **Mandatory SBOM**: All build templates now generate a Software Bill of Materials (SBOM) as a pipeline artifact
- **Attestation**: Deploy templates require a signed attestation from the build stage
- **New template**: `build/sbom-generate.yml` for standalone SBOM generation
- **Deprecated**: `deploy/app-service-deploy.yml` — replaced by `deploy/app-service-deploy-v2.yml` with attestation support

## Approved Templates

### Build Templates
- `build/dotnet-build.yml` — .NET application builds (now includes SBOM)
- `build/node-build.yml` — Node.js application builds (now includes SBOM)
- `build/docker-build.yml` — Container image builds (now includes SBOM)
- `build/sbom-generate.yml` — Standalone SBOM generation (NEW)

### Test Templates
- `test/unit-tests.yml` — Unit test execution
- `test/integration-tests.yml` — Integration test execution
- `test/security-scan.yml` — SAST/DAST scanning
- `test/sbom-verify.yml` — SBOM verification (NEW)

### Deploy Templates
- `deploy/aks-deploy.yml` — AKS deployment (requires attestation)
- `deploy/app-service-deploy-v2.yml` — Azure App Service deployment with attestation (NEW)

## Usage (v4)

```yaml
stages:
  - stage: Build
    jobs:
      - template: build/dotnet-build.yml@templates
        parameters:
          project: src/MyApp/MyApp.csproj
          configuration: Release
          generateSbom: true

  - stage: Verify
    jobs:
      - template: test/sbom-verify.yml@templates

  - stage: Deploy
    jobs:
      - template: deploy/aks-deploy.yml@templates
        parameters:
          attestation: $(Build.ArtifactStagingDirectory)/attestation.json
```

## Migration from v3

1. Add `generateSbom: true` to all build templates
2. Add `test/sbom-verify.yml` stage before deploy
3. Replace `deploy/app-service-deploy.yml` with `deploy/app-service-deploy-v2.yml`
4. Pass attestation artifact to deploy templates
