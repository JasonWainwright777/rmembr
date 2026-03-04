---
title: Secrets Management Standard
domain: security
standard_id: enterprise/security/secrets-management
version: v1
classification: confidential
---

# Secrets Management

## Overview

All secrets, credentials, and sensitive configuration must be stored in Azure Key Vault and accessed via managed identities. Hardcoded secrets in code or configuration files are prohibited.

## Requirements

### Storage
- Use Azure Key Vault for all secrets
- Use managed identities for authentication
- Never store secrets in environment variables, config files, or code

### Access Patterns
- Use Key Vault references in App Service / AKS configurations
- Use the Azure SDK's DefaultAzureCredential for programmatic access
- Rotate secrets on a defined schedule (90 days minimum)

### CI/CD
- Use Azure DevOps service connections with workload identity federation
- Never store secrets as pipeline variables (use Key Vault task instead)
