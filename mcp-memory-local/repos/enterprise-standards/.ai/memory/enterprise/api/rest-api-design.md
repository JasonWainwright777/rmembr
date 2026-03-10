---
title: REST API Design Standard
domain: api
standard_id: enterprise/api/rest-api-design
version: v1
classification: internal
---

# REST API Design Standard

## Overview

All HTTP APIs must follow these conventions for consistency, discoverability, and client compatibility across the organization.

## URL Structure

- Use lowercase, hyphen-separated path segments: `/api/v1/user-profiles`
- Use plural nouns for resource collections: `/orders`, not `/order`
- Version APIs in the URL path: `/api/v1/`, `/api/v2/`
- Nest sub-resources only one level deep: `/orders/{id}/items` (not deeper)

## HTTP Methods

| Method | Usage | Idempotent |
|--------|-------|------------|
| GET | Retrieve a resource or collection | Yes |
| POST | Create a new resource | No |
| PUT | Full replacement of a resource | Yes |
| PATCH | Partial update of a resource | No |
| DELETE | Remove a resource | Yes |

## Status Codes

- `200 OK` — successful GET, PUT, PATCH
- `201 Created` — successful POST (include `Location` header)
- `204 No Content` — successful DELETE
- `400 Bad Request` — validation or malformed input
- `401 Unauthorized` — missing or invalid authentication
- `403 Forbidden` — authenticated but not authorized
- `404 Not Found` — resource does not exist
- `409 Conflict` — state conflict (e.g., duplicate creation)
- `429 Too Many Requests` — rate limit exceeded (include `Retry-After`)
- `500 Internal Server Error` — unhandled server failure

## Error Responses

Use RFC 7807 Problem Details format:

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation Failed",
  "status": 400,
  "detail": "The 'email' field is not a valid email address.",
  "instance": "/api/v1/users/123"
}
```

## Pagination

- Use cursor-based pagination for large collections
- Return `next_cursor` and `has_more` in the response body
- Accept `cursor` and `limit` as query parameters
- Default page size: 20, maximum: 100

## Filtering & Sorting

- Filter via query parameters: `?status=active&region=us-east`
- Sort via `sort` parameter: `?sort=created_at:desc`
- Document all supported filter and sort fields in the API contract

## Authentication & Authorization

- Use OAuth 2.0 / OpenID Connect with Bearer tokens
- Pass tokens in the `Authorization: Bearer <token>` header
- Never accept tokens in query parameters
- Validate scopes and claims for every endpoint

## Rate Limiting

- Apply rate limits to all public and partner-facing APIs
- Return `429` with `Retry-After` header when exceeded
- Include rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
