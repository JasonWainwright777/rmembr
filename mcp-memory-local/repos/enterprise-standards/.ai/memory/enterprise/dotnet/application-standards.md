---
title: .NET Application Standards
domain: dotnet
standard_id: enterprise/dotnet/application-standards
version: v1
classification: internal
---

# .NET Application Standards

## Overview

All .NET applications must target the current LTS release and follow these conventions for project structure, configuration, logging, and deployment.

## Runtime & SDK

- Target .NET 8 (current LTS) for all new projects
- Migrate existing .NET 6 applications to .NET 8 before end-of-support
- Use the Microsoft-published SDK images for CI builds
- Pin the SDK version in `global.json`

## Project Structure

```
src/
  MyApp/
    MyApp.csproj
    Program.cs
    appsettings.json
tests/
  MyApp.Tests/
    MyApp.Tests.csproj
global.json
Directory.Build.props
```

- Use `Directory.Build.props` for shared properties (TreatWarningsAsErrors, nullable, implicit usings)
- One solution file at the repo root
- Separate `src/` and `tests/` directories

## Configuration

- Use `IConfiguration` with the standard provider chain: `appsettings.json` → `appsettings.{Environment}.json` → environment variables
- Never hardcode connection strings, secrets, or environment-specific values
- Use the Options pattern (`IOptions<T>`) for strongly-typed configuration sections
- Validate configuration at startup with `ValidateOnStart()`

## Dependency Injection

- Register all services in `Program.cs` or via extension methods — no service locator pattern
- Use scoped lifetime for database contexts and per-request services
- Use singleton lifetime for stateless services and HTTP clients
- Register `HttpClient` instances via `IHttpClientFactory`

## Logging

- Use `ILogger<T>` from `Microsoft.Extensions.Logging`
- Use structured logging with message templates — never string interpolation
- Log levels: `Debug` for diagnostics, `Information` for business events, `Warning` for recoverable issues, `Error` for failures, `Critical` for unrecoverable failures
- Include correlation IDs in all log entries

```csharp
// Correct
logger.LogInformation("Order {OrderId} placed by {UserId}", orderId, userId);

// Incorrect
logger.LogInformation($"Order {orderId} placed by {userId}");
```

## Error Handling

- Use middleware for global exception handling — do not catch exceptions in every controller
- Return RFC 7807 Problem Details for API errors
- Never expose stack traces or internal details in production responses
- Use `Result<T>` or similar patterns for business logic errors — reserve exceptions for truly exceptional conditions

## API Conventions

- Use minimal APIs or controller-based APIs consistently within a project — do not mix
- Version APIs using URL path segments: `/api/v1/resource`
- Use `System.Text.Json` for serialization (not Newtonsoft) unless there is a documented compatibility requirement
- Return appropriate HTTP status codes: 200, 201, 204, 400, 404, 409, 500
