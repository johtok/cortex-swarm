"""Base agent protocol and execution types.

All agents implement the Agent protocol. The AgentResult captures
output, cost, and metadata from each execution.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class TaskComplexity(str, Enum):
    """Task complexity levels for routing decisions."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


@dataclass
class AgentResult:
    """Result from a single agent execution."""
    output: str
    model_used: str
    tokens_used: int = 0
    cost_multiplier: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRequest:
    """A task to be executed by an agent."""
    prompt: str
    context: str = ""
    complexity: TaskComplexity = TaskComplexity.MODERATE
    preferred_role: str | None = None
    timeout_seconds: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    """Protocol for all agent implementations."""

    async def execute(self, task: TaskRequest) -> AgentResult:
        """Execute a task and return the result."""
        ...

    @property
    def model_id(self) -> str:
        """The model this agent uses."""
        ...

    @property
    def role_name(self) -> str:
        """The role name of this agent."""
        ...
