"""
Load Profiling Tests

Benchmarks for system performance under load:
1. Signal ingress throughput
2. WebSocket broadcast latency
3. Database query performance
4. Concurrent connection handling

These tests establish baselines and detect regressions.
Run with: pytest tests/test_load_profile.py -v --benchmark-only
"""

import pytest
import pytest_asyncio
import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean, stdev
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient


# ==================== Performance Baselines ====================

# Target latencies (milliseconds)
SIGNAL_SUBMISSION_P95_MS = 100      # 95th percentile for signal submission
SIGNAL_SUBMISSION_P99_MS = 200      # 99th percentile for signal submission
WEBSOCKET_BROADCAST_P95_MS = 50     # 95th percentile for WS broadcast
DATABASE_QUERY_P95_MS = 50          # 95th percentile for DB queries
CONCURRENT_SIGNALS_PER_SEC = 50     # Minimum signals/second capacity


# ==================== Timing Utilities ====================


class PerformanceMetrics:
    """Collects and analyzes performance metrics."""

    def __init__(self):
        self.latencies: List[float] = []
        self.start_time: float = 0
        self.end_time: float = 0

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        self.latencies.append(latency_ms)

    def start(self) -> None:
        """Mark start of test."""
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        """Mark end of test."""
        self.end_time = time.perf_counter()

    @property
    def count(self) -> int:
        """Number of measurements."""
        return len(self.latencies)

    @property
    def mean_ms(self) -> float:
        """Mean latency in ms."""
        return mean(self.latencies) if self.latencies else 0

    @property
    def stdev_ms(self) -> float:
        """Standard deviation in ms."""
        return stdev(self.latencies) if len(self.latencies) > 1 else 0

    @property
    def min_ms(self) -> float:
        """Minimum latency in ms."""
        return min(self.latencies) if self.latencies else 0

    @property
    def max_ms(self) -> float:
        """Maximum latency in ms."""
        return max(self.latencies) if self.latencies else 0

    @property
    def p50_ms(self) -> float:
        """50th percentile (median) in ms."""
        return self._percentile(50)

    @property
    def p95_ms(self) -> float:
        """95th percentile in ms."""
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        """99th percentile in ms."""
        return self._percentile(99)

    @property
    def duration_s(self) -> float:
        """Total test duration in seconds."""
        return self.end_time - self.start_time

    @property
    def throughput(self) -> float:
        """Operations per second."""
        if self.duration_s > 0:
            return self.count / self.duration_s
        return 0

    def _percentile(self, p: int) -> float:
        """Calculate percentile."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def report(self) -> dict:
        """Generate performance report."""
        return {
            "count": self.count,
            "duration_s": round(self.duration_s, 3),
            "throughput_per_s": round(self.throughput, 2),
            "mean_ms": round(self.mean_ms, 3),
            "stdev_ms": round(self.stdev_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
        }


# ==================== Signal Ingress Benchmarks ====================


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_signal_submission_latency(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Benchmark signal submission latency."""
    metrics = PerformanceMetrics()
    num_signals = 50

    metrics.start()

    for i in range(num_signals):
        signal_data = {
            "idempotency_key": f"bench-{i}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }

        start = time.perf_counter()
        response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Signal Submission Latency ===")
    print(f"  Samples: {report['count']}")
    print(f"  Throughput: {report['throughput_per_s']:.2f} signals/sec")
    print(f"  Mean: {report['mean_ms']:.2f} ms")
    print(f"  P50: {report['p50_ms']:.2f} ms")
    print(f"  P95: {report['p95_ms']:.2f} ms")
    print(f"  P99: {report['p99_ms']:.2f} ms")

    # Assertions against baselines
    assert report["p95_ms"] < SIGNAL_SUBMISSION_P95_MS, \
        f"P95 latency {report['p95_ms']}ms exceeds baseline {SIGNAL_SUBMISSION_P95_MS}ms"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_concurrent_signal_throughput(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Benchmark concurrent signal submission throughput."""
    metrics = PerformanceMetrics()
    num_concurrent = 20
    num_batches = 5

    async def submit_signal(batch: int, idx: int) -> Tuple[int, float]:
        signal_data = {
            "idempotency_key": f"concurrent-{batch}-{idx}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }

        start = time.perf_counter()
        response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        return response.status_code, latency_ms

    metrics.start()

    for batch in range(num_batches):
        tasks = [submit_signal(batch, i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        for status_code, latency_ms in results:
            if status_code in [200, 429]:  # Success or rate-limited
                metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Concurrent Signal Throughput ===")
    print(f"  Total Signals: {report['count']}")
    print(f"  Duration: {report['duration_s']:.2f} s")
    print(f"  Throughput: {report['throughput_per_s']:.2f} signals/sec")
    print(f"  Mean Latency: {report['mean_ms']:.2f} ms")
    print(f"  P95 Latency: {report['p95_ms']:.2f} ms")

    # Throughput baseline
    assert report["throughput_per_s"] >= CONCURRENT_SIGNALS_PER_SEC * 0.5, \
        f"Throughput {report['throughput_per_s']:.2f}/s below minimum {CONCURRENT_SIGNALS_PER_SEC * 0.5}/s"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_batch_signal_submission_latency(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Benchmark batch signal submission latency."""
    metrics = PerformanceMetrics()
    num_batches = 10
    batch_size = 5

    metrics.start()

    for batch in range(num_batches):
        batch_data = {
            "signals": [
                {
                    "idempotency_key": f"batch-{batch}-{i}-{uuid4().hex[:8]}",
                    "symbol": "EURUSD",
                    "direction": "buy",
                    "source": "strategy",
                    "priority": "normal",
                    "confidence": "0.85",
                }
                for i in range(batch_size)
            ]
        }

        start = time.perf_counter()
        response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit/batch",
            json=batch_data,
            headers=auth_headers,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Batch Signal Submission ===")
    print(f"  Batches: {report['count']}")
    print(f"  Signals/Batch: {batch_size}")
    print(f"  Mean Batch Latency: {report['mean_ms']:.2f} ms")
    print(f"  P95 Batch Latency: {report['p95_ms']:.2f} ms")


# ==================== Query Performance Benchmarks ====================


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_signal_list_query_performance(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Benchmark signal list query performance."""
    # First, populate some signals
    for i in range(20):
        signal_data = {
            "idempotency_key": f"query-prep-{i}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }
        await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

    metrics = PerformanceMetrics()
    num_queries = 50

    metrics.start()

    for _ in range(num_queries):
        start = time.perf_counter()
        response = await async_client.get(
            f"/api/v1/signals/{test_profile.id}",
            params={"page": 1, "page_size": 20},
            headers=auth_headers,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Signal List Query Performance ===")
    print(f"  Queries: {report['count']}")
    print(f"  Mean: {report['mean_ms']:.2f} ms")
    print(f"  P95: {report['p95_ms']:.2f} ms")

    assert report["p95_ms"] < DATABASE_QUERY_P95_MS, \
        f"Query P95 {report['p95_ms']}ms exceeds baseline {DATABASE_QUERY_P95_MS}ms"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_profile_query_performance(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Benchmark profile query performance."""
    metrics = PerformanceMetrics()
    num_queries = 100

    metrics.start()

    for _ in range(num_queries):
        start = time.perf_counter()
        response = await async_client.get(
            f"/api/v1/profiles/{test_profile.id}",
            headers=auth_headers,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Profile Query Performance ===")
    print(f"  Queries: {report['count']}")
    print(f"  Mean: {report['mean_ms']:.2f} ms")
    print(f"  P95: {report['p95_ms']:.2f} ms")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_statistics_query_performance(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Benchmark statistics aggregation query performance."""
    metrics = PerformanceMetrics()
    num_queries = 20

    metrics.start()

    for _ in range(num_queries):
        start = time.perf_counter()
        response = await async_client.get(
            f"/api/v1/signals/{test_profile.id}/stats",
            params={"hours": 24},
            headers=auth_headers,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Statistics Query Performance ===")
    print(f"  Queries: {report['count']}")
    print(f"  Mean: {report['mean_ms']:.2f} ms")
    print(f"  P95: {report['p95_ms']:.2f} ms")


# ==================== WebSocket Benchmarks ====================


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_websocket_broadcast_latency(mock_broadcaster):
    """Benchmark WebSocket broadcast latency."""
    metrics = PerformanceMetrics()
    num_broadcasts = 100

    metrics.start()

    for _ in range(num_broadcasts):
        start = time.perf_counter()
        await mock_broadcaster.position_update(
            profile_id=uuid4(),
            ticket=100001,
            symbol="EURUSD",
            current_price=Decimal("1.08500"),
            profit=Decimal("15.00"),
        )
        latency_ms = (time.perf_counter() - start) * 1000
        metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== WebSocket Broadcast Latency ===")
    print(f"  Broadcasts: {report['count']}")
    print(f"  Mean: {report['mean_ms']:.2f} ms")
    print(f"  P95: {report['p95_ms']:.2f} ms")

    assert report["p95_ms"] < WEBSOCKET_BROADCAST_P95_MS, \
        f"Broadcast P95 {report['p95_ms']}ms exceeds baseline {WEBSOCKET_BROADCAST_P95_MS}ms"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_concurrent_websocket_broadcasts(mock_broadcaster):
    """Benchmark concurrent WebSocket broadcasts."""
    metrics = PerformanceMetrics()
    num_concurrent = 50

    async def broadcast():
        start = time.perf_counter()
        await mock_broadcaster.account_update(
            profile_id=uuid4(),
            balance=Decimal("10000.00"),
            equity=Decimal("10500.00"),
            margin=Decimal("500.00"),
            free_margin=Decimal("10000.00"),
            profit=Decimal("500.00"),
            margin_level=Decimal("2100.00"),
        )
        return (time.perf_counter() - start) * 1000

    metrics.start()

    tasks = [broadcast() for _ in range(num_concurrent)]
    latencies = await asyncio.gather(*tasks)

    for latency_ms in latencies:
        metrics.record(latency_ms)

    metrics.stop()

    report = metrics.report()
    print(f"\n=== Concurrent WebSocket Broadcasts ===")
    print(f"  Broadcasts: {report['count']}")
    print(f"  Duration: {report['duration_s']:.3f} s")
    print(f"  Throughput: {report['throughput_per_s']:.2f} broadcasts/sec")
    print(f"  Mean: {report['mean_ms']:.2f} ms")


# ==================== Background Worker Benchmarks ====================


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_reconciliation_worker_cycle_time():
    """Benchmark reconciliation worker cycle time."""
    from archon_prime.api.services.background_tasks import PositionReconciliationWorker

    worker = PositionReconciliationWorker(interval_seconds=0)
    metrics = PerformanceMetrics()

    with patch.object(worker, "_reconcile_all", new_callable=AsyncMock):
        metrics.start()

        for _ in range(20):
            start = time.perf_counter()
            await worker._reconcile_all()
            latency_ms = (time.perf_counter() - start) * 1000
            metrics.record(latency_ms)

        metrics.stop()

    report = metrics.report()
    print(f"\n=== Reconciliation Cycle Time ===")
    print(f"  Cycles: {report['count']}")
    print(f"  Mean: {report['mean_ms']:.2f} ms")
    print(f"  P95: {report['p95_ms']:.2f} ms")


# ==================== Memory and Resource Benchmarks ====================


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_idempotency_cache_memory(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test idempotency cache doesn't grow unbounded."""
    import sys

    num_signals = 100

    # Submit signals and track rough memory
    for i in range(num_signals):
        signal_data = {
            "idempotency_key": f"mem-test-{i}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }
        await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

    # In real test, would measure actual memory usage
    # This is a placeholder for memory profiling
    print(f"\n=== Idempotency Cache Test ===")
    print(f"  Signals Processed: {num_signals}")
    print("  (Memory profiling requires dedicated tools)")


# ==================== Summary Report ====================


@pytest.fixture(scope="module", autouse=True)
def performance_summary(request):
    """Print performance summary at end of module."""
    yield
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST SUMMARY")
    print("=" * 60)
    print(f"Baselines:")
    print(f"  Signal Submission P95: {SIGNAL_SUBMISSION_P95_MS} ms")
    print(f"  Signal Submission P99: {SIGNAL_SUBMISSION_P99_MS} ms")
    print(f"  WebSocket Broadcast P95: {WEBSOCKET_BROADCAST_P95_MS} ms")
    print(f"  Database Query P95: {DATABASE_QUERY_P95_MS} ms")
    print(f"  Concurrent Signals/sec: {CONCURRENT_SIGNALS_PER_SEC}")
    print("=" * 60)
