"""Ranking parser and aggregation for council peer review.

Parses "FINAL RANKING:" sections from model evaluations and
computes aggregate scores (lower = better, like golf).
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


def parse_ranking(evaluation_text: str) -> list[str] | None:
    """Extract ordered ranking from evaluation text.

    Looks for a "FINAL RANKING:" section with numbered items like:
      1. Response A
      2. Response C
      3. Response B

    Returns list of response labels in rank order, or None if not found.
    """
    match = re.search(r"FINAL RANKING:\s*\n((?:\d+\.\s*.+\n?)+)", evaluation_text, re.IGNORECASE)
    if not match:
        return None

    ranking_block = match.group(1)
    items = re.findall(r"\d+\.\s*(Response\s+\w+)", ranking_block, re.IGNORECASE)

    if not items:
        return None

    return [item.strip() for item in items]


RankingResult = list[tuple[str, float]]


def aggregate_rankings(
    rankings: dict[str, list[str]],
    label_to_model: dict[str, str],
) -> RankingResult:
    """Compute aggregate rankings across all reviewers.

    Each model gets an average rank position (1 = best).
    Lower score = better ("street cred" scoring from llm-council).

    Args:
        rankings: {reviewer_model_id: [ordered labels]}
        label_to_model: {label: model_id} for de-anonymization

    Returns:
        List of (model_id, avg_rank) sorted best to worst.
    """
    if not rankings:
        return []

    # Collect rank positions for each label
    label_ranks: dict[str, list[int]] = {}

    for _reviewer, ranked_labels in rankings.items():
        for position, label in enumerate(ranked_labels, start=1):
            normalized = label.strip()
            if normalized not in label_ranks:
                label_ranks[normalized] = []
            label_ranks[normalized].append(position)

    # Compute average rank and de-anonymize
    results: list[tuple[str, float]] = []

    for label, positions in label_ranks.items():
        avg_rank = sum(positions) / len(positions)
        model_id = label_to_model.get(label, label)
        results.append((model_id, avg_rank))

    results.sort(key=lambda x: x[1])
    return results
