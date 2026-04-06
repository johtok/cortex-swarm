"""DAG execution engine with cascade escalation.

Ported from context-distillation-orchestrator. Executes task DAGs
in topological order with context compression between nodes and
automatic escalation on failure.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from cortex_swarm.dag.compression import compress_context
from cortex_swarm.dag.types import (
    ActivityType,
    ACTIVITY_ROLE,
    DagNode,
    DagResult,
    NodeResult,
)

logger = logging.getLogger(__name__)


def topological_sort(nodes: list[DagNode]) -> list[DagNode]:
    """Sort nodes in dependency order (Kahn's algorithm)."""
    node_map = {n.id: n for n in nodes}
    in_degree = {n.id: 0 for n in nodes}
    adjacency: dict[str, list[str]] = {n.id: [] for n in nodes}

    for node in nodes:
        for dep in node.depends_on:
            if dep not in node_map:
                raise ValueError(f"Node '{node.id}' depends on unknown node '{dep}'")
            adjacency[dep].append(node.id)
            in_degree[node.id] += 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    result = []

    while queue:
        # Process nodes at the same level in parallel (same in-degree)
        nid = queue.pop(0)
        result.append(node_map[nid])
        for neighbor in adjacency[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(nodes):
        raise ValueError("DAG has a cycle — cannot execute")

    return result


class DagRunner:
    """Executes task DAGs with context compression and cascade escalation."""

    def __init__(
        self,
        execute_fn: Callable[[str, str, str], Awaitable[NodeResult]],
        compression_method: str = "key_points",
        compression_level: float = 0.3,
        max_retries: int = 1,
        cascade_on_failure: bool = True,
    ):
        """Initialize the DAG runner.

        Args:
            execute_fn: Async function(model_id, prompt, node_id) → NodeResult.
            compression_method: How to compress context between nodes.
            compression_level: Compression aggressiveness (0-1).
            max_retries: Max retry attempts per node.
            cascade_on_failure: Whether to escalate model tier on retry.
        """
        self._execute = execute_fn
        self._compression_method = compression_method
        self._compression_level = compression_level
        self._max_retries = max_retries
        self._cascade = cascade_on_failure

    async def run(self, nodes: list[DagNode]) -> DagResult:
        """Execute all nodes in topological order."""
        sorted_nodes = topological_sort(nodes)
        dag_result = DagResult()
        node_outputs: dict[str, str] = {}

        failed_nodes: set[str] = set()

        for node in sorted_nodes:
            # Skip nodes whose dependencies failed
            failed_deps = [d for d in node.depends_on if d in failed_nodes]
            if failed_deps:
                skip_result = NodeResult(
                    node_id=node.id,
                    output="",
                    model_used="",
                    success=False,
                    error=f"Skipped: upstream dependency failed ({', '.join(failed_deps)})",
                )
                dag_result.add(skip_result)
                failed_nodes.add(node.id)
                logger.warning("Skipping node %s: dependencies %s failed", node.id, failed_deps)
                continue

            # Gather upstream context
            upstream_parts = []
            for dep_id in node.depends_on:
                if dep_id in node_outputs:
                    compressed = compress_context(
                        node_outputs[dep_id],
                        self._compression_method,
                        self._compression_level,
                    )
                    upstream_parts.append(compressed)

            context = "\n\n---\n\n".join(upstream_parts) if upstream_parts else ""

            # Build prompt with context
            prompt = node.prompt_template
            if context:
                prompt = f"<upstream_context>\n{context}\n</upstream_context>\n\n{prompt}"

            # Execute with retries
            model_id = node.model_override or self._default_model_for(node.activity_type)
            result = await self._execute_with_retry(node, model_id, prompt)

            dag_result.add(result)
            if result.success:
                node_outputs[node.id] = result.output
            else:
                failed_nodes.add(node.id)
                logger.warning("Node %s failed, downstream nodes will be skipped", node.id)

        return dag_result

    async def _execute_with_retry(
        self, node: DagNode, model_id: str, prompt: str
    ) -> NodeResult:
        """Execute a node with retry and optional cascade escalation."""
        escalation_models = self._escalation_chain(model_id)
        result: NodeResult | None = None

        for attempt in range(1 + self._max_retries):
            if self._cascade and attempt > 0:
                idx = min(attempt, len(escalation_models) - 1)
                current_model = escalation_models[idx]
            else:
                current_model = model_id

            try:
                result = await self._execute(current_model, prompt, node.id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                result = NodeResult(
                    node_id=node.id,
                    output="",
                    model_used=current_model,
                    success=False,
                    error=str(exc),
                )

            if result.success:
                return result

            logger.info(
                "Node %s attempt %d/%d failed, model=%s",
                node.id, attempt + 1, 1 + self._max_retries, current_model,
            )

        assert result is not None, "max_retries must be >= 0"
        return result

    @staticmethod
    def _default_model_for(activity_type: ActivityType) -> str:
        """Get default model for an activity type."""
        role = ACTIVITY_ROLE.get(activity_type, "worker")
        # Map role name → default model (same as registry defaults)
        role_models = {
            "oracle": "claude-opus-4.6",
            "worker": "claude-sonnet-4.6",
            "sage": "gpt-5.4",
            "scout": "claude-haiku-4.5",
            "drone": "gpt-5-mini",
        }
        return role_models.get(role, "claude-sonnet-4.6")

    @staticmethod
    def _escalation_chain(model_id: str) -> list[str]:
        """Build an escalation chain for cascade retries."""
        chains: dict[str, list[str]] = {
            "gpt-5-mini": ["claude-haiku-4.5", "claude-sonnet-4.6"],
            "claude-haiku-4.5": ["claude-sonnet-4.6", "gpt-5.4"],
            "claude-sonnet-4.6": ["gpt-5.4", "claude-opus-4.6"],
            "gpt-5.4": ["claude-opus-4.6"],
            "claude-opus-4.6": ["claude-opus-4.6"],
        }
        return [model_id] + chains.get(model_id, ["claude-sonnet-4.6"])
