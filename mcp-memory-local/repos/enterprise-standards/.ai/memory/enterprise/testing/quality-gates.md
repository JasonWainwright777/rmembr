---
title: Testing and Quality Gates Standard
domain: testing
standard_id: enterprise/testing/quality-gates
version: v1
classification: internal
---

# Testing and Quality Gates Standard

## Overview

All production code must pass defined quality gates before merging. Untested code is not deployable.

## Test Pyramid

- **Unit tests** — fast, isolated, no external dependencies. Target: 80%+ code coverage on business logic.
- **Integration tests** — validate service boundaries, database queries, API contracts. Run against real dependencies (use testcontainers or docker-compose).
- **End-to-end tests** — validate critical user journeys. Keep the suite small and stable.

## Required Quality Gates

### PR Merge Gates
- All unit tests pass
- Code coverage does not decrease (or meets minimum threshold)
- No new critical/high SAST findings
- Linting passes with zero errors
- At least one approving review

### Pre-Deploy Gates
- All integration tests pass
- Container image scan shows no critical vulnerabilities
- `what-if` or dry-run deployment succeeds (for infrastructure changes)

## Code Coverage

- Measure coverage with the language-appropriate tool (e.g., `dotnet test --collect:"XPlat Code Coverage"`, `pytest --cov`, `jest --coverage`)
- Enforce minimum thresholds in CI — do not rely on manual review
- Coverage thresholds:
  - Business logic / domain: 80%
  - API controllers / handlers: 70%
  - Infrastructure / glue code: 50%

## Test Naming

Use descriptive names that describe the scenario and expected outcome:

```
// Good
OrderService_PlaceOrder_WithInvalidEmail_ReturnsValidationError

// Bad
Test1
TestPlaceOrder
```

## Test Data

- Use factories or builders for test data — never hardcode magic values
- Isolate tests — each test creates and cleans up its own data
- Never depend on shared mutable state between tests
- Use deterministic data — avoid random values unless testing randomness

## Static Analysis

- Run SAST on every PR (e.g., SonarQube, CodeQL, Semgrep)
- Treat critical and high findings as blocking
- Medium findings must be triaged within the sprint
- Suppress false positives with inline comments and documented rationale
