# MCP Client UAT Checklist

## Prerequisites

- [ ] Docker compose services running (`docker compose up -d`)
- [ ] Ollama model pulled (`docker compose exec ollama ollama pull nomic-embed-text`)
- [ ] At least one repo indexed (`python scripts/mcp-cli.py index-repo <repo>`)
- [ ] `MCP_ENABLED=true` in `.env` or `docker-compose.yml`
- [ ] Gateway logs show `MCP Streamable HTTP transport ready at /mcp`
- [ ] Gateway logs also show `MCP SSE transport ready at /mcp/sse` for legacy compatibility

## VS Code (primary target: 1.102+)

- [ ] `.vscode/mcp.json` present in workspace root
- [ ] VS Code discovers rmembr MCP server in MCP panel
- [ ] Tool list shows 9 tools
- [ ] `search_repo_memory` returns results for an indexed repo
- [ ] `get_context_bundle` returns bundle with markdown
- [ ] `explain_context_bundle` works with a returned `bundle_id`
- [ ] `validate_pack` returns valid/invalid status
- [ ] `list_standards` returns standards list
- [ ] `get_standard` returns standard content
- [ ] Error on invalid input shows clean error (no internal URLs/tokens/paths)
- [ ] `index_repo` returns authorization error for default (reader) role

## Claude Code (secondary client)

- [ ] `.mcp.json` present in project root
- [ ] Claude Code discovers rmembr MCP server
- [ ] Tool list shows 9 tools
- [ ] `search_repo_memory` returns results
- [ ] `get_context_bundle` returns bundle

## Automated Smoke Tests

- [ ] `python -m pytest tests/mcp/test_mcp_smoke.py -v` passes all tests

## Fresh Setup Validation

- [ ] A developer followed `docs/integration/vscode-mcp.md` from scratch
- [ ] Setup completed with zero undocumented steps
- [ ] Tool invocation succeeded without additional guidance

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Tester | | | Pass / Fail |
| Reviewer | | | Pass / Fail |
