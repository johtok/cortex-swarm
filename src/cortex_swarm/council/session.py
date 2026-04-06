"""LLM Council — 3-stage multi-model consensus.

Inspired by karpathy/llm-council. Queries multiple diverse LLMs,
has them peer-review each other anonymously, then synthesizes a
final answer considering all perspectives.

Council members: Gemini 2.5 Pro, Sonnet 4.6, GPT-5.4, Grok Code Fast 1
Chairman: Sonnet 4.6 (synthesizer)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from cortex_swarm.council.ranking import (
    aggregate_rankings,
    parse_ranking,
    RankingResult,
)
from cortex_swarm.council.synthesis import build_synthesis_prompt

logger = logging.getLogger(__name__)


@dataclass
class CouncilMember:
    """A council member with its model assignment."""
    model_id: str
    name: str  # human-readable label


@dataclass
class Stage1Result:
    """Individual responses from all council members."""
    responses: dict[str, str]  # model_id → response


@dataclass
class Stage2Result:
    """Peer review rankings from all council members."""
    evaluations: dict[str, str]  # model_id → raw evaluation text
    rankings: dict[str, list[str]]  # model_id → ordered list of response labels
    aggregate: list[tuple[str, float]]  # (model_id, avg_rank) sorted best→worst


@dataclass
class CouncilResult:
    """Full council result across all 3 stages."""
    question: str
    stage1: Stage1Result
    stage2: Stage2Result
    synthesis: str
    chairman_model: str


# Anonymous labels for peer review
ANON_LABELS = ["Response A", "Response B", "Response C", "Response D",
               "Response E", "Response F", "Response G", "Response H"]


REVIEW_PROMPT = """\
You are evaluating multiple responses to a question. Each response was written independently by a different AI model. Your identity and theirs are hidden.

## Original Question
{question}

## Responses to Evaluate
{responses_block}

## Your Task
1. Evaluate each response for correctness, completeness, clarity, and insight.
2. Provide a brief assessment of each response.
3. End with a FINAL RANKING section listing responses from best to worst.

Format your ranking EXACTLY like this:
FINAL RANKING:
1. Response X
2. Response Y
3. Response Z
...
"""


class Council:
    """Orchestrates a multi-model council session."""

    def __init__(
        self,
        members: list[CouncilMember],
        chairman_model: str,
        query_fn: Callable[[str, str], Awaitable[str]],
    ):
        """Initialize the council.

        Args:
            members: List of council members with model assignments.
            chairman_model: Model ID for the chairman (synthesis stage).
            query_fn: Async function(model_id, prompt) → response string.
                     The caller provides this to abstract the LLM backend.
        """
        self._members = members
        self._chairman = chairman_model
        self._query = query_fn

    async def convene(self, question: str) -> CouncilResult:
        """Run the full 3-stage council process.

        Stage 1: Independent opinions (parallel)
        Stage 2: Anonymized peer review (parallel)
        Stage 3: Chairman synthesis
        """
        logger.info("Council convened with %d members", len(self._members))

        stage1 = await self._stage1_opinions(question)
        stage2 = await self._stage2_review(question, stage1)
        synthesis = await self._stage3_synthesize(question, stage1, stage2)

        return CouncilResult(
            question=question,
            stage1=stage1,
            stage2=stage2,
            synthesis=synthesis,
            chairman_model=self._chairman,
        )

    async def _stage1_opinions(self, question: str) -> Stage1Result:
        """Stage 1: Query all members independently in parallel."""
        logger.info("Stage 1: Collecting independent opinions")

        tasks = {
            member.model_id: self._query(member.model_id, question)
            for member in self._members
        }

        results = {}
        responses = await asyncio.gather(
            *tasks.values(), return_exceptions=True,
        )

        for (model_id, _), response in zip(tasks.items(), responses):
            if isinstance(response, BaseException):
                logger.error("Stage 1 failed for %s: %s", model_id, response)
                results[model_id] = f"[Error: {response}]"
            else:
                results[model_id] = response

        return Stage1Result(responses=results)

    async def _stage2_review(
        self, question: str, stage1: Stage1Result
    ) -> Stage2Result:
        """Stage 2: Anonymized peer review."""
        logger.info("Stage 2: Anonymized peer review")

        # Build anonymized response block
        model_to_label: dict[str, str] = {}
        label_to_model: dict[str, str] = {}
        responses_block_parts = []

        for i, (model_id, response) in enumerate(stage1.responses.items()):
            label = ANON_LABELS[i] if i < len(ANON_LABELS) else f"Response {i+1}"
            model_to_label[model_id] = label
            label_to_model[label] = model_id
            responses_block_parts.append(f"### {label}\n{response}")

        responses_block = "\n\n".join(responses_block_parts)

        review_prompt = REVIEW_PROMPT.format(
            question=question,
            responses_block=responses_block,
        )

        # Query all members for their rankings (in parallel)
        tasks = {
            member.model_id: self._query(member.model_id, review_prompt)
            for member in self._members
        }

        evaluations: dict[str, str] = {}
        rankings: dict[str, list[str]] = {}

        responses = await asyncio.gather(
            *tasks.values(), return_exceptions=True,
        )

        for (model_id, _), response in zip(tasks.items(), responses):
            if isinstance(response, BaseException):
                logger.error("Stage 2 failed for %s: %s", model_id, response)
                evaluations[model_id] = f"[Error: {response}]"
            else:
                evaluations[model_id] = response
                parsed = parse_ranking(response)
                if parsed:
                    rankings[model_id] = parsed

        # De-anonymize and aggregate
        aggregate = aggregate_rankings(rankings, label_to_model)

        return Stage2Result(
            evaluations=evaluations,
            rankings=rankings,
            aggregate=aggregate,
        )

    async def _stage3_synthesize(
        self,
        question: str,
        stage1: Stage1Result,
        stage2: Stage2Result,
    ) -> str:
        """Stage 3: Chairman synthesizes all inputs."""
        logger.info("Stage 3: Chairman synthesis by %s", self._chairman)

        prompt = build_synthesis_prompt(question, stage1, stage2)
        return await self._query(self._chairman, prompt)
