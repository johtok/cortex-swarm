"""Tests for the premium concurrency pool."""

import asyncio
import pytest
from cortex_swarm.agents.pool import AgentPool


@pytest.mark.asyncio
async def test_pool_allows_unlimited_free():
    """Free-tier agents should run without limits."""
    pool = AgentPool(max_premium=2)
    results = []

    async def task():
        results.append(True)
        return True

    # Run 10 free agents concurrently
    await asyncio.gather(*[
        pool.execute("gpt-5-mini", task) for _ in range(10)
    ])

    assert len(results) == 10
    assert pool.stats.total_completed == 10


@pytest.mark.asyncio
async def test_pool_limits_premium_to_2():
    """Premium agents should be gated by the semaphore."""
    pool = AgentPool(max_premium=2)
    active_count = []
    max_active = 0

    async def premium_task():
        nonlocal max_active
        active = pool.stats.active_premium
        active_count.append(active)
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        return True

    # Run 5 premium agents — at most 2 should be active at once
    await asyncio.gather(*[
        pool.execute("claude-opus-4.6", premium_task) for _ in range(5)
    ])

    assert pool.stats.total_completed == 5
    assert max_active <= 2


@pytest.mark.asyncio
async def test_pool_tracks_stats():
    """Pool should track active and completed counts."""
    pool = AgentPool(max_premium=2)

    async def ok_task():
        return True

    async def fail_task():
        raise ValueError("boom")

    await pool.execute("claude-sonnet-4.6", ok_task)
    assert pool.stats.total_completed == 1

    with pytest.raises(ValueError):
        await pool.execute("claude-sonnet-4.6", fail_task)
    assert pool.stats.total_failed == 1
