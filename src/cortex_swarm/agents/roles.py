"""Named agent roles with system prompts and capabilities.

Each role maps to a specific model and task profile.
Roles are the user-facing names for the agent archetypes.
"""

from __future__ import annotations

from cortex_swarm.models.registry import AgentRole, DEFAULT_ROLES, RoleConfig


# Extended system prompts per role
ROLE_DESCRIPTIONS: dict[AgentRole, str] = {
    AgentRole.ORACLE: (
        "The Oracle handles the most critical and complex tasks: "
        "architecture decisions, complex debugging, security reviews, "
        "and any task where getting it wrong has severe consequences. "
        "Uses Claude Opus 4.6 (premium, multiplier=3). Max 2 concurrent."
    ),
    AgentRole.WORKER: (
        "The Worker is the default workhorse — used for most tasks. "
        "Implementation, code review, analysis, refactoring, testing. "
        "Uses Claude Sonnet 4.6 (standard, multiplier=1). "
        "Should be used the MOST. When in doubt, use Worker."
    ),
    AgentRole.SAGE: (
        "The Sage handles long-context tasks: large codebase analysis, "
        "cross-file understanding, documentation synthesis, and tasks "
        "requiring extensive context windows. "
        "Uses GPT-5.4 (standard, multiplier=1)."
    ),
    AgentRole.SCOUT: (
        "The Scout handles simple, low-intelligence tasks: file search, "
        "formatting, simple lookups, grep patterns, boilerplate generation. "
        "Uses Claude Haiku 4.5 (cheap, multiplier=0.33)."
    ),
    AgentRole.DRONE: (
        "The Drone handles bulk small tasks in parallel swarms. "
        "Classification, linting, summarization, simple extraction. "
        "Uses GPT-5 mini (FREE, multiplier=0). Unlimited concurrency!"
    ),
}


def get_role_info(role: AgentRole) -> dict:
    """Get complete role information including model and description."""
    config = DEFAULT_ROLES[role]
    return {
        "role": role.value,
        "model": config.primary_model,
        "fallback_chain": config.fallback_chain,
        "temperature": config.temperature,
        "tier": config.model_info.tier.value,
        "multiplier": config.model_info.multiplier_paid,
        "description": ROLE_DESCRIPTIONS.get(role, ""),
        "system_prompt": config.system_prompt_prefix,
    }


def list_all_roles() -> list[dict]:
    """List all available roles with their configurations."""
    return [get_role_info(role) for role in AgentRole]
