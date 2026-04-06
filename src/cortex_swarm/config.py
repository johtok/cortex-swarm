"""Configuration loader for cortex-swarm.

Loads from configs/default.yaml, then optionally overrides from
a user-specified config file or environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CouncilConfig:
    members: list[str] = field(default_factory=lambda: [
        "gemini-2.5-pro", "claude-sonnet-4.6", "gpt-5.4", "grok-code-fast-1",
    ])
    chairman: str = "claude-sonnet-4.6"


@dataclass
class SwarmConfig:
    model: str = "gpt-5-mini"
    max_parallel: int = 20
    synthesis_model: str = "claude-sonnet-4.6"


@dataclass
class DagConfig:
    compression_method: str = "key_points"
    compression_level: float = 0.3
    max_retries: int = 1
    cascade_on_failure: bool = True


@dataclass
class RoutingConfig:
    trivial_max_tokens: int = 500
    simple_max_tokens: int = 2000
    moderate_max_tokens: int = 10000
    complex_max_tokens: int = 50000


@dataclass
class SwarmGlobalConfig:
    max_premium_concurrent: int = 2
    default_model: str = "claude-sonnet-4.6"
    roles: dict[str, dict[str, Any]] = field(default_factory=dict)
    council: CouncilConfig = field(default_factory=CouncilConfig)
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    dag: DagConfig = field(default_factory=DagConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)


def _merge_dataclass(target: Any, data: dict) -> None:
    """Merge a dict into a dataclass, updating only present keys."""
    for key, value in data.items():
        if hasattr(target, key):
            setattr(target, key, value)


def load_config(config_path: Path | None = None) -> SwarmGlobalConfig:
    """Load configuration from YAML file(s).

    Resolution order:
    1. Built-in defaults (dataclass defaults)
    2. configs/default.yaml (if exists)
    3. User-specified config_path (if provided)
    """
    config = SwarmGlobalConfig()

    # Load default config
    default_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    if default_path.exists():
        _apply_yaml(config, default_path)

    # Load user override
    if config_path and config_path.exists():
        _apply_yaml(config, config_path)

    _validate_config(config)
    return config


def _validate_config(config: SwarmGlobalConfig) -> None:
    """Validate configuration values are within sane ranges."""
    if config.max_premium_concurrent < 1:
        raise ValueError(f"max_premium_concurrent must be >= 1, got {config.max_premium_concurrent}")
    if config.dag.max_retries < 0:
        raise ValueError(f"dag.max_retries must be >= 0, got {config.dag.max_retries}")
    if not (0.0 <= config.dag.compression_level <= 1.0):
        raise ValueError(f"dag.compression_level must be in [0, 1], got {config.dag.compression_level}")
    if config.swarm.max_parallel < 1:
        raise ValueError(f"swarm.max_parallel must be >= 1, got {config.swarm.max_parallel}")


def _apply_yaml(config: SwarmGlobalConfig, path: Path) -> None:
    """Apply a YAML file's values onto the config."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    if "max_premium_concurrent" in data:
        config.max_premium_concurrent = data["max_premium_concurrent"]
    if "default_model" in data:
        config.default_model = data["default_model"]
    if "roles" in data and isinstance(data["roles"], dict):
        config.roles = data["roles"]

    if "council" in data and isinstance(data["council"], dict):
        _merge_dataclass(config.council, data["council"])
    if "swarm" in data and isinstance(data["swarm"], dict):
        _merge_dataclass(config.swarm, data["swarm"])
    if "dag" in data and isinstance(data["dag"], dict):
        _merge_dataclass(config.dag, data["dag"])
    if "routing" in data and isinstance(data["routing"], dict):
        _merge_dataclass(config.routing, data["routing"])
