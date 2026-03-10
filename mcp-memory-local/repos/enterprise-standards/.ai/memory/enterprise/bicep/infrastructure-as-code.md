---
title: Bicep Infrastructure as Code Standards
domain: bicep
standard_id: enterprise/bicep/infrastructure-as-code
version: v1
classification: internal
---

# Bicep Infrastructure as Code Standards

## Overview

All Azure infrastructure must be defined in Bicep templates. ARM JSON templates, portal-created resources, and ad-hoc CLI deployments are not permitted for production environments.

## File Structure

```
infra/
  main.bicep              # Entry point — orchestrates modules
  main.bicepparam         # Parameter file per environment
  modules/
    networking.bicep
    compute.bicep
    storage.bicep
    monitoring.bicep
```

- Use a single `main.bicep` entry point that composes modules
- One module per resource group or logical domain
- Use `.bicepparam` files (not JSON parameter files) for environment-specific values

## Naming Conventions

- Resources: `{workload}-{environment}-{region}-{resource-type}` (e.g., `myapp-prod-eus2-kv`)
- Modules: lowercase, hyphen-separated, matching the resource domain
- Parameters: camelCase
- Variables: camelCase
- Outputs: camelCase, prefixed with the resource type (e.g., `storageAccountId`)

## Module Standards

### Parameters
- All modules must accept `location`, `environment`, and `tags` as parameters
- Use `@allowed()` decorator for constrained values
- Use `@secure()` decorator for secrets — never pass secrets as plain parameters
- Provide sensible defaults where appropriate

### Example Module
```bicep
@description('The Azure region for resources.')
param location string = resourceGroup().location

@description('Environment name.')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Resource tags.')
param tags object = {}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'Standard_GRS' : 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
  }
}

output storageAccountId string = storageAccount.id
```

## Security Requirements

- Enable HTTPS-only on all applicable resources
- Set minimum TLS version to 1.2
- Disable public access by default — use Private Endpoints for production
- Use managed identities instead of connection strings or keys
- Never output secrets — use Key Vault references

## Deployment

- Deploy via Azure DevOps pipelines using the approved `deploy/bicep-deploy.yml` template
- Use `what-if` validation in PR pipelines before merging
- Production deployments require approval gates
- Tag all resources with `environment`, `owner`, `costCenter`, and `managedBy`

## State & Drift

- Bicep is declarative — re-running a deployment should be idempotent
- Use deployment stacks or periodic `what-if` runs to detect drift
- Do not modify deployed resources manually — all changes must go through Bicep
