"""GPT-5 mini drone swarm for bulk parallel tasks.

Fan-out pattern: split work into N small tasks, run unlimited
GPT-5 mini agents in parallel (multiplier=0, FREE!), then merge
results with a Sonnet 4.6 synthesis pass.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class SwarmTask:
    """A single sub-task for the swarm."""
    id: str
    prompt: str
    context: str = ""


@dataclass
class SwarmResult:
    """Result from a single swarm drone."""
    task_id: str
    output: str
    success: bool = True
    error: str | None = None


@dataclass
class SwarmBatchResult:
    """Aggregated result from the entire swarm batch."""
    results: list[SwarmResult] = field(default_factory=list)
    synthesis: str = ""
    total_tasks: int = 0
    successful: int = 0
    failed: int = 0


SYNTHESIS_PROMPT = """\
You are synthesizing results from {count} parallel sub-tasks.
Combine these results into a coherent, comprehensive summary.

## Sub-task Results
{results_block}

## Your Task
1. Merge all successful results into a single coherent output.
2. Note any failures or inconsistencies.
3. Produce a final, unified result.
"""


class DroneSwarm:
    """Orchestrates a swarm of GPT-5 mini drones for bulk work."""

    def __init__(
        self,
        query_fn: Callable[[str, str], Awaitable[str]],
        drone_model: str = "gpt-5-mini",
        synthesis_model: str = "claude-sonnet-4.6",
        max_parallel: int = 20,
    ):
        self._query = query_fn
        self._drone_model = drone_model
        self._synthesis_model = synthesis_model
        self._semaphore = asyncio.Semaphore(max_parallel)

    async def execute(
        self,
        tasks: list[SwarmTask],
        synthesize: bool = True,
    ) -> SwarmBatchResult:
        """Fan out tasks to drones and optionally synthesize results."""
        logger.info("Swarm dispatching %d tasks to %s", len(tasks), self._drone_model)

        drone_tasks = [self._run_drone(task) for task in tasks]
        results = await asyncio.gather(*drone_tasks, return_exceptions=True)

        batch = SwarmBatchResult(total_tasks=len(tasks))

        for task, result in zip(tasks, results):
            if isinstance(result, BaseException):
                batch.results.append(SwarmResult(
                    task_id=task.id, output="", success=False, error=str(result),
                ))
                batch.failed += 1
            else:
                batch.results.append(result)
                if result.success:
                    batch.successful += 1
                else:
                    batch.failed += 1

        if synthesize and batch.successful > 0:
            batch.synthesis = await self._synthesize(batch)

        logger.info(
            "Swarm complete: %d/%d successful", batch.successful, batch.total_tasks,
        )
        return batch

    async def _run_drone(self, task: SwarmTask) -> SwarmResult:
        """Run a single drone task with concurrency control."""
        async with self._semaphore:
            prompt = task.prompt
            if task.context:
                prompt = f"Context:\n{task.context}\n\n{prompt}"

            try:
                output = await self._query(self._drone_model, prompt)
                return SwarmResult(task_id=task.id, output=output)
            except Exception as e:
                return SwarmResult(
                    task_id=task.id, output="", success=False, error=str(e),
                )

    async def _synthesize(self, batch: SwarmBatchResult) -> str:
        """Merge drone results using the synthesis model."""
        results_parts = []
        for r in batch.results:
            if r.success:
                results_parts.append(f"### Task {r.task_id}\n{r.output}")
            else:
                results_parts.append(f"### Task {r.task_id} [FAILED]\n{r.error}")

        prompt = SYNTHESIS_PROMPT.format(
            count=batch.total_tasks,
            results_block="\n\n".join(results_parts),
        )

        return await self._query(self._synthesis_model, prompt)
