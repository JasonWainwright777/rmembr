# Operational Runbook -- Context Gateway

## How to use this runbook

Each scenario follows: **Symptoms** -> **Diagnosis** -> **Recovery** -> **Escalation**.

Check the relevant dashboard panels in Grafana (`localhost:3000`) and the `/metrics` endpoint for real-time data. All log output is structured JSON — use `docker compose logs gateway | jq` for readable output.

---

## Scenario 1: Embedding service unavailable

**Symptoms:**
- `search_repo_memory` returns 503 or times out
- Logs show `"embedding_service_unavailable"` or Ollama connection errors
- `mcp_dependency_health{dependency="ollama"} == 0` in `/metrics`
- `DependencyDown` alert firing for `ollama`

**Diagnosis:**
1. Check Ollama health: `curl -s http://localhost:11434/api/version`
2. Check container status: `docker compose ps ollama`
3. Check Ollama logs: `docker compose logs ollama --tail=50`
4. Verify model is pulled: `docker compose exec ollama ollama list`

**Recovery:**
1. Restart Ollama: `docker compose restart ollama`
2. Wait for health check to pass (~10s)
3. Verify model is available: `docker compose exec ollama ollama list`
4. If model missing: `docker compose exec ollama ollama pull nomic-embed-text`
5. Test: `curl -s http://localhost:8080/health | jq`

**Escalation:**
- If Ollama container crashes repeatedly, check host GPU/memory resources
- If model loads but embedding calls fail, check Ollama version compatibility
- Consider switching to CPU-only mode if GPU driver issues persist

---

## Scenario 2: Database connection pool exhausted

**Symptoms:**
- All endpoints return 503 or hang
- Logs show `"pool exhausted"`, `"connection timeout"`, or `"too many connections"`
- `mcp_dependency_health{dependency="postgres"} == 0`
- `DependencyDown` alert firing for `postgres`

**Diagnosis:**
1. Check active connections: `docker compose exec postgres psql -U memory -c "SELECT count(*) FROM pg_stat_activity"`
2. Check for long-running queries: `docker compose exec postgres psql -U memory -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC LIMIT 5"`
3. Check gateway pool config: verify `max_size` in `server.py`

**Recovery:**
1. Restart the gateway service: `docker compose restart gateway`
2. If persistent, check for connection leaks in recent code changes
3. Increase pool `max_size` in gateway and index services if load warrants it
4. Verify PostgreSQL `max_connections` is sufficient: `docker compose exec postgres psql -U memory -c "SHOW max_connections"`

**Escalation:**
- If connections accumulate despite restarts, look for missing `async with pool.acquire()` patterns or unclosed connections
- Monitor `pg_stat_activity` over time to identify leak patterns

---

## Scenario 3: Auth token mismatch (401 errors)

**Symptoms:**
- Internal service calls fail with 401
- Logs show `"missing X-Internal-Token header"` or `"invalid X-Internal-Token"`
- Gateway `/health` shows `"index": false` and/or `"standards": false`

**Diagnosis:**
1. Verify token consistency: check `INTERNAL_SERVICE_TOKEN` in `.env`
2. Verify all services see the same token: `docker compose exec gateway env | grep INTERNAL_SERVICE_TOKEN`
3. Compare with: `docker compose exec index env | grep INTERNAL_SERVICE_TOKEN`

**Recovery:**
1. Ensure `INTERNAL_SERVICE_TOKEN` is set to the same value in `.env`
2. Restart all services: `docker compose restart`
3. Verify: `curl -s http://localhost:8080/health | jq`

**Escalation:**
- N/A (local configuration issue)

---

## Scenario 4: Bundle cache thrashing (high latency)

**Symptoms:**
- `get_context_bundle` p95 consistently above SLO (>2000ms warm)
- `SearchLatencyP95High` or `BundleLatencyP95High` alert firing
- Metrics show high proportion of `cache_state="miss"` observations
- Logs show frequent "Building bundle" messages with no "Bundle cache hit"

**Diagnosis:**
1. Check cache hit ratio in metrics: `curl -s localhost:8080/metrics | grep mcp_tool_call_duration_seconds`
2. Look at `cache_state` label distribution — are most calls "miss"?
3. Check `BUNDLE_CACHE_TTL_SECONDS` value
4. Check if repo content is changing rapidly (triggering reindexes that invalidate cache)

**Recovery:**
1. Increase `BUNDLE_CACHE_TTL_SECONDS` (default 300s → 600s or 3600s)
2. If cache size is the issue, check bundle_cache table row count
3. Investigate whether frequent reindexing is invalidating caches
4. Consider if query patterns are too varied for caching to be effective

**Escalation:**
- If latency is high even with cache hits, investigate downstream service performance (Index, Standards)
- Profile gateway request handling to identify bottlenecks

---

## Scenario 5: Policy validation failures

**Symptoms:**
- Tool calls denied unexpectedly
- Audit log shows `"action": "deny"` entries
- Users report "not authorized" errors for tools they should have access to

**Diagnosis:**
1. Check loaded policy: verify `POLICY_FILE` env var points to correct file
2. Review deny reasons in audit log: `docker compose logs gateway | jq 'select(.action == "deny")'`
3. Check policy bundle version and role mappings
4. Verify the requesting role matches policy expectations

**Recovery:**
1. Verify policy bundle file is valid JSON and matches expected schema
2. If policy file is corrupted, revert to last known good version
3. Restart gateway to reload policy: `docker compose restart gateway`
4. If `POLICY_HOT_RELOAD=true`, policy reloads automatically on file change

**Escalation:**
- If policy denials are unexpected, review the `tool_auth` section of the policy bundle
- Check if a recent policy update changed role permissions

---

## Scenario 6: MCP client connection failures

**Symptoms:**
- VS Code or Claude Code cannot discover or invoke MCP tools
- MCP client logs show connection refused or timeout
- No MCP-related log entries in gateway logs

**Diagnosis:**
1. Verify MCP is enabled: `docker compose exec gateway env | grep MCP_ENABLED`
2. Check gateway is running: `curl -s http://localhost:8080/health`
3. Test MCP endpoint directly: `curl -s -X POST http://localhost:8080/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}'`
4. Check client MCP config (`.vscode/mcp.json` or `.mcp.json`)

**Recovery:**
1. Set `MCP_ENABLED=true` in `.env` and restart gateway
2. Verify the MCP endpoint responds (step 3 above)
3. Check client-side configuration matches gateway URL and transport. Prefer `http://localhost:8080/mcp` with HTTP transport; use `/mcp/sse` only for legacy SSE clients.
4. For stdio transport, verify `MCP_STDIO_ENABLED=true`

**Escalation:**
- Check for transport-level issues (firewall, port binding conflicts)
- Verify MCP SDK version compatibility between client and server
- Check gateway startup logs for MCP mount errors
