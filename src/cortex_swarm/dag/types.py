"""Shared types for DAG execution.

Ported from context-distillation-orchestrator with simplifications.
Activity types, tool policies, and node results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ActivityType(str, Enum):
    """Activity types for DAG nodes, determining model and tool selection."""
    ANALYSIS = "analysis"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    TESTING = "testing"
    FORMATTING = "formatting"
    COMPRESSION = "compression"
    SYNTHESIS = "synthesis"


@dataclass(frozen=True)
class ToolPolicy:
    """Tool allowlist for a DAG node (per-activity confinement)."""
    read: bool = True
    write: bool = False
    edit: bool = False
    bash: bool = False
    glob: bool = True
    grep: bool = True

    def to_allowlist(self) -> list[str]:
        tools = []
        for name in ("read", "write", "edit", "bash", "glob", "grep"):
            if getattr(self, name):
                tools.append(name)
        return tools


# Default tool policies per activity type
ACTIVITY_TOOLS: dict[ActivityType, ToolPolicy] = {
    ActivityType.ANALYSIS: ToolPolicy(read=True, glob=True, grep=True),
    ActivityType.IMPLEMENTATION: ToolPolicy(read=True, write=True, edit=True, bash=True, glob=True, grep=True),
    ActivityType.REVIEW: ToolPolicy(read=True, glob=True, grep=True),
    ActivityType.TESTING: ToolPolicy(read=True, bash=True, glob=True, grep=True),
    ActivityType.FORMATTING: ToolPolicy(read=True, write=True, edit=True),
    ActivityType.COMPRESSION: ToolPolicy(read=True),
    ActivityType.SYNTHESIS: ToolPolicy(read=True, glob=True, grep=True),
}

# Complexity mapping: activity type → default agent role name
ACTIVITY_ROLE: dict[ActivityType, str] = {
    ActivityType.ANALYSIS: "worker",
    ActivityType.IMPLEMENTATION: "worker",
    ActivityType.REVIEW: "worker",
    ActivityType.TESTING: "scout",
    ActivityType.FORMATTING: "drone",
    ActivityType.COMPRESSION: "drone",
    ActivityType.SYNTHESIS: "sage",
}


@dataclass
class DagNode:
    """A node in the task DAG."""
    id: str
    activity_type: ActivityType
    prompt_template: str
    depends_on: list[str] = field(default_factory=list)
    model_override: str | None = None
    timeout_seconds: float = 300.0


@dataclass
class NodeResult:
    """Result from executing a single DAG node."""
    node_id: str
    output: str
    model_used: str
    tokens_used: int = 0
    cost_multiplier: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: str | None = None

    @property
    def failed(self) -> bool:
        return not self.success


@dataclass
class DagResult:
    """Result from executing a complete DAG."""
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    total_tokens: int = 0
    total_duration_ms: int = 0
    total_multiplier_cost: float = 0.0

    @property
    def success(self) -> bool:
        return all(r.success for r in self.node_results.values())

    def add(self, result: NodeResult) -> None:
        self.node_results[result.node_id] = result
        self.total_tokens += result.tokens_used
        self.total_duration_ms += result.duration_ms
        self.total_multiplier_cost += result.cost_multiplier
