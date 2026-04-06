"""Chairman synthesis for council Stage 3.

Builds a comprehensive prompt for the chairman model that includes
all Stage 1 responses and Stage 2 rankings, asking it to synthesize
the best possible answer considering all perspectives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex_swarm.council.session import Stage1Result, Stage2Result


def build_synthesis_prompt(
    question: str,
    stage1: Stage1Result,
    stage2: Stage2Result,
) -> str:
    """Build the chairman synthesis prompt.

    The chairman receives:
    1. The original question
    2. All individual responses (Stage 1)
    3. Aggregate rankings (Stage 2)

    It must produce a final, synthesized answer that is better
    than any individual response.
    """
    # Build responses section
    responses_section = []
    for i, (model_id, response) in enumerate(stage1.responses.items(), 1):
        responses_section.append(f"### Response {i} (from {model_id})\n{response}")

    # Build rankings section
    rankings_section = "### Aggregate Rankings (lower = better)\n"
    if stage2.aggregate:
        for model_id, avg_rank in stage2.aggregate:
            rankings_section += f"- {model_id}: {avg_rank:.2f}\n"
    else:
        rankings_section += "No rankings available.\n"

    # Build evaluations summary
    eval_section = []
    for model_id, evaluation in stage2.evaluations.items():
        # Truncate long evaluations
        truncated = evaluation[:2000] + "..." if len(evaluation) > 2000 else evaluation
        eval_section.append(f"### Evaluation by {model_id}\n{truncated}")

    return f"""\
You are the Chairman of a council of AI models. Your job is to synthesize the best possible answer to a question, considering multiple independent responses and peer evaluations.

## Original Question
{question}

## Individual Responses (Stage 1)
{chr(10).join(responses_section)}

## Peer Review Rankings (Stage 2)
{rankings_section}

## Peer Evaluations
{chr(10).join(eval_section)}

## Your Task
Synthesize a final answer that:
1. Takes the best insights from each response
2. Resolves disagreements using the peer rankings as guidance
3. Is more comprehensive and accurate than any single response
4. Clearly states where the council agreed and where it disagreed

Produce your synthesized answer now.
"""
