---
title: Sample Repo B Instructions
priority: must-follow
---

# Repo B Data Pipeline Instructions

## Project Structure

- `pipelines/` — Azure Data Factory pipeline definitions (ARM/Bicep)
- `notebooks/` — Databricks notebooks (Python)
- `infra/` — Terraform infrastructure code
- `tests/` — Unit and integration tests

## Data Quality Rules

All pipelines must:
1. Validate schema at ingestion
2. Log row counts at each transformation step
3. Write to a dead-letter queue on validation failure

## Terraform Modules

Infrastructure modules are version-pinned per enterprise standard. See `enterprise/terraform/module-versioning`.

## Running Locally

1. Install Python 3.11+
2. Create virtualenv: `python -m venv .venv`
3. Install deps: `pip install -r requirements.txt`
4. Run tests: `pytest tests/`
