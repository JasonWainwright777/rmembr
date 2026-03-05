"""Prometheus metrics for gateway observability.

Exports: tool_call_latency, tool_call_total, tool_call_errors,
         dependency_health, dependency_health_last_probe,
         update_dependency_health, metrics_app (ASGI app for /metrics).

Gracefully degrades when prometheus_client is not installed.
"""

import time

try:
    from prometheus_client import Histogram, Counter, Gauge, make_asgi_app

    tool_call_latency = Histogram(
        "mcp_tool_call_duration_seconds",
        "MCP tool call latency in seconds",
        labelnames=["tool", "cache_state"],
        buckets=[0.05, 0.1, 0.15, 0.3, 0.5, 0.6, 1.0, 1.2, 1.5, 2.0, 4.0, 10.0],
    )

    tool_call_total = Counter(
        "mcp_tool_call_total",
        "Total MCP tool calls",
        labelnames=["tool", "status"],
    )

    tool_call_errors = Counter(
        "mcp_tool_call_errors_total",
        "Total MCP tool call errors",
        labelnames=["tool"],
    )

    dependency_health = Gauge(
        "mcp_dependency_health",
        "Dependency health status (1=healthy, 0=degraded)",
        labelnames=["dependency"],
    )

    dependency_health_last_probe = Gauge(
        "mcp_dependency_health_last_probe_timestamp",
        "Unix epoch timestamp of last health probe per dependency",
        labelnames=["dependency"],
    )

    metrics_app = make_asgi_app()
    METRICS_AVAILABLE = True

except ImportError:
    tool_call_latency = None
    tool_call_total = None
    tool_call_errors = None
    dependency_health = None
    dependency_health_last_probe = None
    metrics_app = None
    METRICS_AVAILABLE = False


def observe_latency(tool: str, duration_seconds: float, cache_state: str = "miss") -> None:
    """Record a tool call latency observation."""
    if tool_call_latency is not None:
        tool_call_latency.labels(tool=tool, cache_state=cache_state).observe(duration_seconds)


def count_call(tool: str, status: str = "success") -> None:
    """Increment the tool call counter."""
    if tool_call_total is not None:
        tool_call_total.labels(tool=tool, status=status).inc()


def count_error(tool: str) -> None:
    """Increment the tool call error counter."""
    if tool_call_errors is not None:
        tool_call_errors.labels(tool=tool).inc()


async def update_dependency_health(
    check_index, check_standards, check_postgres, check_ollama
) -> None:
    """Probe each dependency and update gauge values.

    Called by gateway background task every 30 seconds.
    Each checker is an async callable returning bool (True=healthy).
    """
    if dependency_health is None:
        return

    checks = {
        "index": check_index,
        "standards": check_standards,
        "postgres": check_postgres,
        "ollama": check_ollama,
    }

    for name, checker in checks.items():
        try:
            healthy = await checker()
        except Exception:
            healthy = False
        dependency_health.labels(dependency=name).set(1 if healthy else 0)
        dependency_health_last_probe.labels(dependency=name).set(time.time())
