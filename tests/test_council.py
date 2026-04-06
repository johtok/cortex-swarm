"""Tests for the LLM council ranking parser."""

from cortex_swarm.council.ranking import parse_ranking, aggregate_rankings


def test_parse_ranking_basic():
    text = """
Some evaluation text here...

FINAL RANKING:
1. Response A
2. Response C
3. Response B
"""
    result = parse_ranking(text)
    assert result == ["Response A", "Response C", "Response B"]


def test_parse_ranking_missing():
    text = "No ranking section here at all."
    assert parse_ranking(text) is None


def test_parse_ranking_case_insensitive():
    text = """
final ranking:
1. Response B
2. Response A
"""
    result = parse_ranking(text)
    assert result == ["Response B", "Response A"]


def test_aggregate_rankings():
    rankings = {
        "model-1": ["Response A", "Response B", "Response C"],
        "model-2": ["Response B", "Response A", "Response C"],
        "model-3": ["Response A", "Response C", "Response B"],
    }
    label_to_model = {
        "Response A": "gemini-2.5-pro",
        "Response B": "claude-sonnet-4.6",
        "Response C": "gpt-5.4",
    }

    result = aggregate_rankings(rankings, label_to_model)

    # Response A: ranks 1,2,1 → avg 1.33
    # Response B: ranks 2,1,3 → avg 2.0
    # Response C: ranks 3,3,2 → avg 2.67
    assert result[0][0] == "gemini-2.5-pro"  # best
    assert result[-1][0] == "gpt-5.4"  # worst
    assert abs(result[0][1] - 1.333) < 0.01


def test_aggregate_empty():
    assert aggregate_rankings({}, {}) == []
