"""SLO validation: captures latency by cache state and checks against targets.

Skipped if gateway not available. Runs against live services.
Designed for CI nightly or manual validation.
"""

import statistics
import time

import pytest

from tests.mcp.conftest import gateway_reachable, McpTestClient, GATEWAY_URL

try:
    import httpx
except ImportError:
    httpx = None

# SLO thresholds from docs/contracts/slo-targets.md v1.0.0
SEARCH_P50_WARM_MS = 150
SEARCH_P95_WARM_MS = 400
SEARCH_P50_COLD_MS = 500
SEARCH_P95_COLD_MS = 1500
BUNDLE_P50_WARM_MS = 500
BUNDLE_P95_WARM_MS = 1200
BUNDLE_P50_COLD_MS = 2000
BUNDLE_P95_COLD_MS = 4000

# Minimum sample sizes
WARM_SAMPLES = 20
COLD_SAMPLES = 5

skip_no_gateway = pytest.mark.skipif(
    not gateway_reachable(),
    reason="Gateway not reachable (run docker compose up)",
)


def percentile(data: list[float], pct: int) -> float:
    """Calculate percentile from a sorted list."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _timed_post(url: str, payload: dict, timeout: float = 30.0) -> tuple[float, dict]:
    """POST and return (duration_ms, response_json)."""
    start = time.monotonic()
    resp = httpx.post(url, json=payload, timeout=timeout)
    duration_ms = (time.monotonic() - start) * 1000
    return duration_ms, resp.json()


@skip_no_gateway
class TestSloValidation:
    """Latency SLO validation with warm/cold cache split."""

    def _search_payload(self) -> dict:
        return {
            "repo": "rmembr",
            "query": "How does the gateway assemble context bundles?",
            "k": 5,
            "ref": "local",
            "namespace": "default",
        }

    def _bundle_payload(self) -> dict:
        return {
            "repo": "rmembr",
            "task": "Understand gateway architecture",
            "k": 5,
            "ref": "local",
            "namespace": "default",
        }

    def test_search_warm_latency(self):
        """search_repo_memory warm-cache p50 and p95 within SLO."""
        url = f"{GATEWAY_URL}/proxy/index/search_repo_memory"
        payload = self._search_payload()

        # Warm up (discard first call)
        _timed_post(url, payload)

        durations = []
        for _ in range(WARM_SAMPLES):
            ms, _ = _timed_post(url, payload)
            durations.append(ms)

        p50 = percentile(durations, 50)
        p95 = percentile(durations, 95)

        print(f"\nsearch warm p50={p50:.1f}ms p95={p95:.1f}ms (SLO: p50<={SEARCH_P50_WARM_MS}ms p95<={SEARCH_P95_WARM_MS}ms)")
        assert p50 <= SEARCH_P50_WARM_MS, f"search warm p50 {p50:.1f}ms exceeds SLO {SEARCH_P50_WARM_MS}ms"
        assert p95 <= SEARCH_P95_WARM_MS, f"search warm p95 {p95:.1f}ms exceeds SLO {SEARCH_P95_WARM_MS}ms"

    def test_search_cold_latency(self):
        """search_repo_memory cold-start p50 and p95 within SLO."""
        url = f"{GATEWAY_URL}/proxy/index/search_repo_memory"

        durations = []
        for i in range(COLD_SAMPLES):
            payload = {
                **self._search_payload(),
                "query": f"Cold query variation {i} {time.time()}",
            }
            ms, _ = _timed_post(url, payload)
            durations.append(ms)

        p50 = percentile(durations, 50)
        p95 = percentile(durations, 95)

        print(f"\nsearch cold p50={p50:.1f}ms p95={p95:.1f}ms (SLO: p50<={SEARCH_P50_COLD_MS}ms p95<={SEARCH_P95_COLD_MS}ms)")
        assert p50 <= SEARCH_P50_COLD_MS, f"search cold p50 {p50:.1f}ms exceeds SLO {SEARCH_P50_COLD_MS}ms"
        assert p95 <= SEARCH_P95_COLD_MS, f"search cold p95 {p95:.1f}ms exceeds SLO {SEARCH_P95_COLD_MS}ms"

    def test_bundle_warm_latency(self):
        """get_context_bundle warm-cache p50 and p95 within SLO."""
        url = f"{GATEWAY_URL}/tools/get_context_bundle"
        payload = self._bundle_payload()

        # First call populates cache
        _timed_post(url, payload)

        durations = []
        for _ in range(WARM_SAMPLES):
            ms, _ = _timed_post(url, payload)
            durations.append(ms)

        p50 = percentile(durations, 50)
        p95 = percentile(durations, 95)

        print(f"\nbundle warm p50={p50:.1f}ms p95={p95:.1f}ms (SLO: p50<={BUNDLE_P50_WARM_MS}ms p95<={BUNDLE_P95_WARM_MS}ms)")
        assert p50 <= BUNDLE_P50_WARM_MS, f"bundle warm p50 {p50:.1f}ms exceeds SLO {BUNDLE_P50_WARM_MS}ms"
        assert p95 <= BUNDLE_P95_WARM_MS, f"bundle warm p95 {p95:.1f}ms exceeds SLO {BUNDLE_P95_WARM_MS}ms"

    def test_bundle_cold_latency(self):
        """get_context_bundle cold-start p50 and p95 within SLO."""
        url = f"{GATEWAY_URL}/tools/get_context_bundle"

        durations = []
        for i in range(COLD_SAMPLES):
            payload = {
                **self._bundle_payload(),
                "task": f"Cold bundle variation {i} {time.time()}",
            }
            ms, _ = _timed_post(url, payload)
            durations.append(ms)

        p50 = percentile(durations, 50)
        p95 = percentile(durations, 95)

        print(f"\nbundle cold p50={p50:.1f}ms p95={p95:.1f}ms (SLO: p50<={BUNDLE_P50_COLD_MS}ms p95<={BUNDLE_P95_COLD_MS}ms)")
        assert p50 <= BUNDLE_P50_COLD_MS, f"bundle cold p50 {p50:.1f}ms exceeds SLO {BUNDLE_P50_COLD_MS}ms"
        assert p95 <= BUNDLE_P95_COLD_MS, f"bundle cold p95 {p95:.1f}ms exceeds SLO {BUNDLE_P95_COLD_MS}ms"
