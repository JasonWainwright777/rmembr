---
title: Terraform Module Versioning Standard
domain: terraform
standard_id: enterprise/terraform/module-versioning
version: v3
classification: internal
---

# Terraform Module Versioning

## Overview

All Terraform modules must follow semantic versioning (SemVer) and be pinned to specific versions in consuming configurations.

## Requirements

### Version Format
- Use SemVer: `MAJOR.MINOR.PATCH`
- Tag releases in the module repository
- Document breaking changes in CHANGELOG.md

### Pinning Rules
- Always pin to exact versions in production configurations
- Use version constraints (`~>`) only in development environments
- Never use `ref = "main"` in module sources

### Module Registry
- All shared modules must be published to the internal Terraform module registry
- Module names must follow the pattern: `terraform-<PROVIDER>-<NAME>`
- Each module must include a `versions.tf` file declaring required provider versions

## Examples

### Correct Usage
```hcl
module "network" {
  source  = "app.terraform.io/myorg/network/azurerm"
  version = "3.2.1"
}
```

### Incorrect Usage
```hcl
module "network" {
  source = "git::https://dev.azure.com/myorg/modules/network?ref=main"
}
```
