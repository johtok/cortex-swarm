"""Tests for the model multiplier table."""

from cortex_swarm.models.multiplier import (
    COPILOT_MODELS,
    ModelTier,
    get_model,
    is_premium,
    models_by_tier,
)


def test_gpt5_mini_is_free():
    model = get_model("gpt-5-mini")
    assert model.tier == ModelTier.FREE
    assert model.multiplier_paid == 0


def test_sonnet_is_standard():
    model = get_model("claude-sonnet-4.6")
    assert model.tier == ModelTier.STANDARD
    assert model.multiplier_paid == 1


def test_opus_is_premium():
    model = get_model("claude-opus-4.6")
    assert model.tier == ModelTier.PREMIUM
    assert model.multiplier_paid == 3


def test_haiku_is_cheap():
    model = get_model("claude-haiku-4.5")
    assert model.tier == ModelTier.CHEAP
    assert model.multiplier_paid == 0.33


def test_is_premium_helper():
    assert is_premium("claude-opus-4.6") is True
    assert is_premium("claude-opus-4.6-fast") is True
    assert is_premium("claude-sonnet-4.6") is False
    assert is_premium("gpt-5-mini") is False


def test_models_by_tier():
    free_models = models_by_tier(ModelTier.FREE)
    assert len(free_models) >= 3
    assert all(m.multiplier_paid == 0 for m in free_models)

    premium_models = models_by_tier(ModelTier.PREMIUM)
    assert len(premium_models) >= 2
    assert all(m.multiplier_paid >= 3 for m in premium_models)


def test_all_models_have_valid_tiers():
    for model_id, info in COPILOT_MODELS.items():
        assert info.tier in ModelTier, f"{model_id} has invalid tier"
        assert info.multiplier_paid >= 0, f"{model_id} has negative multiplier"
