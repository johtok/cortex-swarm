"""Agent pool with premium concurrency control.

The pool enforces that at most N premium-tier agents (multiplier >= 3)
run concurrently. Standard, cheap, and free agents are unlimited.
GPT-5 mini (multiplier=0) can run as many as you want.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from cortex_swarm.models.multiplier import is_premium, get_model, ModelTier

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Live pool statistics."""
    active_premium: int = 0
    active_standard: int = 0
    active_cheap: int = 0
    active_free: int = 0
    queued_premium: int = 0
    total_completed: int = 0
    total_failed: int = 0


class AgentPool:
    """Manages agent concurrency with premium tier limits.

    Premium agents (Opus 4.6, etc.) are gated by a semaphore.
    All other tiers run without concurrency restrictions.
    """

    def __init__(self, max_premium: int = 2):
        self._premium_semaphore = asyncio.Semaphore(max_premium)
        self._max_premium = max_premium
        self._stats = PoolStats()
        self._lock = asyncio.Lock()

    @property
    def stats(self) -> PoolStats:
        return self._stats

    async def execute(
        self,
        model_id: str,
        task_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Execute a task function with appropriate concurrency control.

        Premium models are gated by the semaphore. Others run freely.

        Args:
            model_id: The model being used (to determine tier).
            task_fn: Async callable that performs the actual work.

        Returns:
            Whatever task_fn returns.
        """
        if is_premium(model_id):
            return await self._run_premium(model_id, task_fn)
        else:
            return await self._run_standard(model_id, task_fn)

    async def _run_premium(
        self,
        model_id: str,
        task_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Run a premium task, waiting for semaphore if needed."""
        acquired = False
        async with self._lock:
            self._stats.queued_premium += 1

        logger.info(
            "Premium agent %s queued (active=%d/%d, queued=%d)",
            model_id, self._stats.active_premium, self._max_premium,
            self._stats.queued_premium,
        )

        try:
            async with self._premium_semaphore:
                async with self._lock:
                    self._stats.queued_premium -= 1
                    self._stats.active_premium += 1
                    acquired = True

                logger.info(
                    "Premium agent %s started (active=%d/%d)",
                    model_id, self._stats.active_premium, self._max_premium,
                )

                try:
                    result = await task_fn()
                    async with self._lock:
                        self._stats.total_completed += 1
                    return result
                except BaseException:
                    async with self._lock:
                        self._stats.total_failed += 1
                    raise
                finally:
                    async with self._lock:
                        self._stats.active_premium -= 1
        except BaseException:
            if not acquired:
                async with self._lock:
                    self._stats.queued_premium -= 1
            raise

    async def _run_standard(
        self,
        model_id: str,
        task_fn: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Run a non-premium task without concurrency limits."""
        try:
            model_info = get_model(model_id)
            tier = model_info.tier
        except KeyError:
            tier = ModelTier.STANDARD

        async with self._lock:
            if tier == ModelTier.FREE:
                self._stats.active_free += 1
            elif tier == ModelTier.CHEAP:
                self._stats.active_cheap += 1
            else:
                self._stats.active_standard += 1

        try:
            result = await task_fn()
            async with self._lock:
                self._stats.total_completed += 1
            return result
        except Exception:
            async with self._lock:
                self._stats.total_failed += 1
            raise
        finally:
            async with self._lock:
                if tier == ModelTier.FREE:
                    self._stats.active_free -= 1
                elif tier == ModelTier.CHEAP:
                    self._stats.active_cheap -= 1
                else:
                    self._stats.active_standard -= 1
