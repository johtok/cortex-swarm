"""Copilot Model Multiplier table.

Maps every supported model to its multiplier cost for paid and free plans.
Multiplier 0 = free, 0.33 = cheap, 1 = standard, 3+ = premium.
Source: GitHub Copilot pricing documentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    """Cost tier derived from multiplier value."""
    FREE = "free"           # multiplier = 0
    CHEAP = "cheap"         # multiplier <= 0.33
    STANDARD = "standard"   # multiplier = 1
    PREMIUM = "premium"     # multiplier >= 3


@dataclass(frozen=True)
class ModelInfo:
    """Model metadata including multiplier costs."""
    id: str
    multiplier_paid: float
    multiplier_free: float | None  # None = not available on free plan
    max_context_tokens: int = 200_000  # reasonable default
    supports_tools: bool = True

    @property
    def tier(self) -> ModelTier:
        if self.multiplier_paid == 0:
            return ModelTier.FREE
        elif self.multiplier_paid <= 0.33:
            return ModelTier.CHEAP
        elif self.multiplier_paid >= 3:
            return ModelTier.PREMIUM
        return ModelTier.STANDARD


# Complete Copilot Multiplier table
COPILOT_MODELS: dict[str, ModelInfo] = {
    # --- FREE tier (multiplier = 0) ---
    "gpt-4.1": ModelInfo("gpt-4.1", 0, 1),
    "gpt-4o": ModelInfo("gpt-4o", 0, 1),
    "gpt-5-mini": ModelInfo("gpt-5-mini", 0, 1),

    # --- CHEAP tier (multiplier <= 0.33) ---
    "claude-haiku-4.5": ModelInfo("claude-haiku-4.5", 0.33, 1),
    "gemini-3-flash": ModelInfo("gemini-3-flash", 0.33, None),
    "gpt-5.1-codex-mini": ModelInfo("gpt-5.1-codex-mini", 0.33, None),
    "gpt-5.4-mini": ModelInfo("gpt-5.4-mini", 0.33, None),
    "grok-code-fast-1": ModelInfo("grok-code-fast-1", 0.25, 1),

    # --- STANDARD tier (multiplier = 1) ---
    "claude-sonnet-4": ModelInfo("claude-sonnet-4", 1, None),
    "claude-sonnet-4.5": ModelInfo("claude-sonnet-4.5", 1, None),
    "claude-sonnet-4.6": ModelInfo("claude-sonnet-4.6", 1, None),
    "gemini-2.5-pro": ModelInfo("gemini-2.5-pro", 1, None),
    "gemini-3-pro": ModelInfo("gemini-3-pro", 1, None),
    "gemini-3.1-pro": ModelInfo("gemini-3.1-pro", 1, None),
    "gpt-5.1": ModelInfo("gpt-5.1", 1, None),
    "gpt-5.1-codex": ModelInfo("gpt-5.1-codex", 1, None),
    "gpt-5.1-codex-max": ModelInfo("gpt-5.1-codex-max", 1, None),
    "gpt-5.2": ModelInfo("gpt-5.2", 1, None),
    "gpt-5.2-codex": ModelInfo("gpt-5.2-codex", 1, None),
    "gpt-5.3-codex": ModelInfo("gpt-5.3-codex", 1, None),
    "gpt-5.4": ModelInfo("gpt-5.4", 1, None, max_context_tokens=1_000_000),

    # --- PREMIUM tier (multiplier >= 3) ---
    "claude-opus-4.5": ModelInfo("claude-opus-4.5", 3, None),
    "claude-opus-4.6": ModelInfo("claude-opus-4.6", 3, None),
    "claude-opus-4.6-fast": ModelInfo("claude-opus-4.6-fast", 30, None),
}


def get_model(model_id: str) -> ModelInfo:
    """Look up a model by ID. Raises KeyError if not found."""
    return COPILOT_MODELS[model_id]


def models_by_tier(tier: ModelTier) -> list[ModelInfo]:
    """Return all models in a given tier, sorted by multiplier."""
    return sorted(
        [m for m in COPILOT_MODELS.values() if m.tier == tier],
        key=lambda m: m.multiplier_paid,
    )


def is_premium(model_id: str) -> bool:
    """Check if a model is premium tier (multiplier >= 3)."""
    return COPILOT_MODELS.get(model_id, ModelInfo(model_id, 1, None)).tier == ModelTier.PREMIUM
