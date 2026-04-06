"""Model registry with role-based assignment and fallback chains.

Each agent role has a primary model and a fallback chain. The router
uses this to select the right model for each task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from cortex_swarm.models.multiplier import ModelInfo, ModelTier, COPILOT_MODELS, get_model


class AgentRole(str, Enum):
    """Named agent roles with designated models."""
    ORACLE = "oracle"       # Hardest tasks — Opus 4.6
    WORKER = "worker"       # Default workhorse — Sonnet 4.6
    SAGE = "sage"           # Long context — GPT-5.4
    SCOUT = "scout"         # Simple tasks — Haiku 4.5
    DRONE = "drone"         # Bulk free tasks — GPT-5 mini


@dataclass(frozen=True)
class RoleConfig:
    """Configuration for an agent role."""
    role: AgentRole
    primary_model: str
    fallback_chain: list[str] = field(default_factory=list)
    system_prompt_prefix: str = ""
    temperature: float = 0.1

    @property
    def model_info(self) -> ModelInfo:
        return get_model(self.primary_model)


# Default role configurations — bias heavily toward Sonnet 4.6
DEFAULT_ROLES: dict[AgentRole, RoleConfig] = {
    AgentRole.ORACLE: RoleConfig(
        role=AgentRole.ORACLE,
        primary_model="claude-opus-4.6",
        fallback_chain=["gpt-5.4", "gemini-3.1-pro", "claude-sonnet-4.6"],
        system_prompt_prefix="You are an expert architect and debugger. Handle only the most critical, complex tasks.",
        temperature=0.1,
    ),
    AgentRole.WORKER: RoleConfig(
        role=AgentRole.WORKER,
        primary_model="claude-sonnet-4.6",
        fallback_chain=["gpt-5.2", "claude-sonnet-4.5", "gpt-5.1"],
        system_prompt_prefix="You are a skilled software engineer. Implement, review, and analyze code efficiently.",
        temperature=0.1,
    ),
    AgentRole.SAGE: RoleConfig(
        role=AgentRole.SAGE,
        primary_model="gpt-5.4",
        fallback_chain=["gemini-2.5-pro", "claude-sonnet-4.6", "gpt-5.2"],
        system_prompt_prefix="You are a deep analyst with extensive context handling. Analyze large codebases and synthesize documentation.",
        temperature=0.1,
    ),
    AgentRole.SCOUT: RoleConfig(
        role=AgentRole.SCOUT,
        primary_model="claude-haiku-4.5",
        fallback_chain=["gpt-5.4-mini", "gpt-5-mini"],
        system_prompt_prefix="You are a fast, efficient assistant. Handle simple lookups, formatting, and file searches.",
        temperature=0.0,
    ),
    AgentRole.DRONE: RoleConfig(
        role=AgentRole.DRONE,
        primary_model="gpt-5-mini",
        fallback_chain=["gpt-4.1", "gpt-4o"],
        system_prompt_prefix="You are a lightweight worker. Complete small, well-defined tasks quickly.",
        temperature=0.0,
    ),
}


class ModelRegistry:
    """Central registry for model lookups and role resolution."""

    def __init__(self, role_overrides: dict[str, dict] | None = None):
        self._roles = dict(DEFAULT_ROLES)
        if role_overrides:
            self._apply_overrides(role_overrides)

    def get_role(self, role: AgentRole) -> RoleConfig:
        return self._roles[role]

    def get_model_for_role(self, role: AgentRole) -> str:
        return self._roles[role].primary_model

    def get_fallback_chain(self, role: AgentRole) -> list[str]:
        """Return [primary] + fallback_chain for a role."""
        config = self._roles[role]
        return [config.primary_model] + list(config.fallback_chain)

    def resolve_model(self, role: AgentRole, exclude: set[str] | None = None) -> str:
        """Resolve the best available model for a role, skipping excluded models."""
        chain = self.get_fallback_chain(role)
        excluded = exclude or set()
        for model_id in chain:
            if model_id not in excluded:
                return model_id
        return chain[0]  # last resort: primary even if excluded

    def _apply_overrides(self, overrides: dict[str, dict]) -> None:
        for role_name, override in overrides.items():
            try:
                role = AgentRole(role_name)
            except ValueError:
                continue
            base = self._roles[role]
            self._roles[role] = RoleConfig(
                role=role,
                primary_model=override.get("model", base.primary_model),
                fallback_chain=override.get("fallback_chain", list(base.fallback_chain)),
                system_prompt_prefix=override.get("system_prompt", base.system_prompt_prefix),
                temperature=override.get("temperature", base.temperature),
            )
