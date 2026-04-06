"""Task complexity classifier and model router.

Routes tasks to the appropriate agent role based on complexity.
Defaults to Sonnet 4.6 (Worker) when uncertain — it's the workhorse.
Supports cascade escalation on failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cortex_swarm.agents.base import TaskComplexity, TaskRequest
from cortex_swarm.config import RoutingConfig
from cortex_swarm.models.registry import AgentRole, ModelRegistry

logger = logging.getLogger(__name__)

# Complexity → Role mapping (biased toward Worker/Sonnet 4.6)
COMPLEXITY_ROLE_MAP: dict[TaskComplexity, AgentRole] = {
    TaskComplexity.TRIVIAL: AgentRole.DRONE,     # GPT-5 mini (free)
    TaskComplexity.SIMPLE: AgentRole.SCOUT,      # Haiku 4.5 (cheap)
    TaskComplexity.MODERATE: AgentRole.WORKER,   # Sonnet 4.6 (default)
    TaskComplexity.COMPLEX: AgentRole.SAGE,      # GPT-5.4 (long context)
    TaskComplexity.CRITICAL: AgentRole.ORACLE,   # Opus 4.6 (premium)
}

# Escalation path: try next tier up on failure
ESCALATION_PATH: dict[AgentRole, AgentRole] = {
    AgentRole.DRONE: AgentRole.SCOUT,
    AgentRole.SCOUT: AgentRole.WORKER,
    AgentRole.WORKER: AgentRole.SAGE,
    AgentRole.SAGE: AgentRole.ORACLE,
    AgentRole.ORACLE: AgentRole.ORACLE,  # already at top
}


def classify_complexity(task: TaskRequest, routing_config: RoutingConfig) -> TaskComplexity:
    """Classify task complexity based on prompt length and metadata.

    Uses token count as a rough proxy. Real implementations would
    use a classifier model, but this is a good starting heuristic.
    """
    # If explicitly set, respect it
    if task.complexity != TaskComplexity.MODERATE:
        return task.complexity

    # Estimate tokens (~4 chars per token)
    estimated_tokens = len(task.prompt + task.context) // 4

    if estimated_tokens <= routing_config.trivial_max_tokens:
        return TaskComplexity.TRIVIAL
    elif estimated_tokens <= routing_config.simple_max_tokens:
        return TaskComplexity.SIMPLE
    elif estimated_tokens <= routing_config.moderate_max_tokens:
        return TaskComplexity.MODERATE
    elif estimated_tokens <= routing_config.complex_max_tokens:
        return TaskComplexity.COMPLEX
    else:
        return TaskComplexity.CRITICAL


@dataclass
class RoutingDecision:
    """The result of routing a task."""
    role: AgentRole
    model_id: str
    complexity: TaskComplexity
    reason: str


class TaskRouter:
    """Routes tasks to the appropriate agent role and model."""

    def __init__(self, registry: ModelRegistry, routing_config: RoutingConfig):
        self._registry = registry
        self._config = routing_config

    def route(self, task: TaskRequest) -> RoutingDecision:
        """Route a task to the best agent role and model."""
        # If user specified a preferred role, use it
        if task.preferred_role:
            try:
                role = AgentRole(task.preferred_role)
                return RoutingDecision(
                    role=role,
                    model_id=self._registry.get_model_for_role(role),
                    complexity=task.complexity,
                    reason=f"User-specified role: {role.value}",
                )
            except ValueError:
                logger.warning("Unknown preferred role: %s, falling back to auto-routing", task.preferred_role)

        complexity = classify_complexity(task, self._config)
        role = COMPLEXITY_ROLE_MAP[complexity]
        model_id = self._registry.get_model_for_role(role)

        return RoutingDecision(
            role=role,
            model_id=model_id,
            complexity=complexity,
            reason=f"Auto-routed: {complexity.value} → {role.value} ({model_id})",
        )

    def escalate(self, current_role: AgentRole) -> RoutingDecision:
        """Escalate to the next tier after a failure."""
        next_role = ESCALATION_PATH[current_role]
        model_id = self._registry.get_model_for_role(next_role)
        return RoutingDecision(
            role=next_role,
            model_id=model_id,
            complexity=TaskComplexity.CRITICAL,
            reason=f"Escalated from {current_role.value} → {next_role.value} ({model_id})",
        )
