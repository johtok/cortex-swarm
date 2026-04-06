#!/usr/bin/env python3
"""cortex-swarm end-to-end demo.

Exercises every major subsystem with a mock LLM backend so no real
API calls are made. Run with:

    python examples/demo.py
"""

from __future__ import annotations

import asyncio
import textwrap

# ──────────────────────────────────────────────────────────────────
# 1. Model Multiplier Table
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.models.multiplier import (
    COPILOT_MODELS,
    ModelTier,
    get_model,
    is_premium,
    models_by_tier,
)


def demo_multiplier() -> None:
    print("=" * 60)
    print("1. MODEL MULTIPLIER TABLE")
    print("=" * 60)

    for model_id in ["gpt-5-mini", "claude-haiku-4.5", "claude-sonnet-4.6",
                      "gpt-5.4", "claude-opus-4.6", "claude-opus-4.6-fast"]:
        m = get_model(model_id)
        print(f"  {m.id:<30} tier={m.tier.value:<10} ×{m.multiplier_paid}")

    print(f"\n  Free-tier models:    {len(models_by_tier(ModelTier.FREE))}")
    print(f"  Cheap-tier models:   {len(models_by_tier(ModelTier.CHEAP))}")
    print(f"  Standard-tier models: {len(models_by_tier(ModelTier.STANDARD))}")
    print(f"  Premium-tier models:  {len(models_by_tier(ModelTier.PREMIUM))}")
    print(f"  Total models:         {len(COPILOT_MODELS)}")
    print(f"\n  Is claude-opus-4.6 premium? {is_premium('claude-opus-4.6')}")
    print(f"  Is gpt-5-mini premium?      {is_premium('gpt-5-mini')}")
    print()


# ──────────────────────────────────────────────────────────────────
# 2. Model Registry & Roles
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.models.registry import AgentRole, ModelRegistry


def demo_registry() -> None:
    print("=" * 60)
    print("2. MODEL REGISTRY & ROLE ASSIGNMENTS")
    print("=" * 60)

    registry = ModelRegistry()
    for role in AgentRole:
        config = registry.get_role(role)
        chain = registry.get_fallback_chain(role)
        print(f"  {role.value:<8} → {config.primary_model:<25} "
              f"fallback: {' → '.join(config.fallback_chain)}")

    # Test fallback resolution with exclusions
    resolved = registry.resolve_model(AgentRole.WORKER, exclude={"claude-sonnet-4.6"})
    print(f"\n  Worker with sonnet excluded resolves to: {resolved}")
    print()


# ──────────────────────────────────────────────────────────────────
# 3. Task Routing
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.agents.base import TaskRequest, TaskComplexity
from cortex_swarm.agents.router import TaskRouter
from cortex_swarm.config import load_config


def demo_routing() -> None:
    print("=" * 60)
    print("3. TASK ROUTING")
    print("=" * 60)

    cfg = load_config()
    registry = ModelRegistry(cfg.roles)
    router = TaskRouter(registry, cfg.routing)

    tasks = [
        TaskRequest(prompt="Fix typo"),
        TaskRequest(prompt="Explain what this function does: " + "x" * 5000),
        TaskRequest(prompt="Refactor auth module " + "y" * 30000),
        TaskRequest(prompt="Analyze entire codebase " + "z" * 200000),
        TaskRequest(prompt="Do it this way", preferred_role="oracle"),
    ]

    for task in tasks:
        decision = router.route(task)
        print(f"  [{decision.complexity.value:<8}] → {decision.role.value:<8} "
              f"({decision.model_id}) — {decision.reason[:60]}")

    # Test escalation
    esc = router.escalate(AgentRole.SCOUT)
    print(f"\n  Escalation from scout → {esc.role.value} ({esc.model_id})")
    print()


# ──────────────────────────────────────────────────────────────────
# 4. Premium Pool (concurrency limiter)
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.agents.pool import AgentPool


async def demo_pool() -> None:
    print("=" * 60)
    print("4. PREMIUM CONCURRENCY POOL")
    print("=" * 60)

    pool = AgentPool(max_premium=2)
    max_concurrent_premium = 0
    log: list[str] = []

    async def premium_work(task_id: int) -> str:
        nonlocal max_concurrent_premium
        active = pool.stats.active_premium
        max_concurrent_premium = max(max_concurrent_premium, active)
        log.append(f"premium-{task_id} started (active={active})")
        await asyncio.sleep(0.05)
        log.append(f"premium-{task_id} done")
        return f"result-{task_id}"

    async def free_work(task_id: int) -> str:
        log.append(f"free-{task_id} started")
        await asyncio.sleep(0.01)
        log.append(f"free-{task_id} done")
        return f"result-{task_id}"

    # Launch 4 premium + 10 free tasks concurrently
    premium_tasks = [
        pool.execute("claude-opus-4.6", lambda i=i: premium_work(i))
        for i in range(4)
    ]
    free_tasks = [
        pool.execute("gpt-5-mini", lambda i=i: free_work(i))
        for i in range(10)
    ]

    results = await asyncio.gather(*premium_tasks, *free_tasks)
    stats = pool.stats

    print(f"  Max concurrent premium: {max_concurrent_premium} (limit: 2)")
    print(f"  Total completed: {stats.total_completed}")
    print(f"  Premium results: {results[:4]}")
    print(f"  Free results: {len(results[4:])} tasks done")
    assert max_concurrent_premium <= 2, "FAIL: more than 2 premium running!"
    print("  ✅ Premium concurrency properly limited to 2")
    print()


# ──────────────────────────────────────────────────────────────────
# 5. LLM Council (mock backend)
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.council.session import Council, CouncilMember


async def demo_council() -> None:
    print("=" * 60)
    print("5. LLM COUNCIL (mock)")
    print("=" * 60)

    call_count = {"total": 0}

    async def mock_query(model_id: str, prompt: str) -> str:
        call_count["total"] += 1

        # Stage 3: chairman synthesis (check first — it contains "Chairman")
        if "Chairman" in prompt:
            return (
                "The council recommends starting with a modular monolith. "
                "Extract microservices only when clear scaling boundaries emerge. "
                "Agreed: keep it simple first. Disagreed: timing of service extraction."
            )

        # Stage 2: peer review (contains "Evaluate" and response blocks)
        if "Evaluate" in prompt and "Response A" in prompt:
            return textwrap.dedent(f"""\
                Analysis by {model_id}:
                Response A focuses on scaling, Response B on pragmatism,
                Response C on evolutionary architecture, Response D is contrarian.

                FINAL RANKING:
                1. Response C
                2. Response B
                3. Response A
                4. Response D
            """)

        # Stage 1: independent opinions
        opinions = {
            "gemini-2.5-pro": "Use microservices for independent scaling.",
            "claude-sonnet-4.6": "A modular monolith is best for your team size.",
            "gpt-5.4": "Start monolith, extract services as needed.",
            "grok-code-fast-1": "Neither — go serverless functions.",
        }
        return opinions.get(model_id, f"Opinion from {model_id}")

    members = [
        CouncilMember(model_id="gemini-2.5-pro", name="Gemini"),
        CouncilMember(model_id="claude-sonnet-4.6", name="Sonnet"),
        CouncilMember(model_id="gpt-5.4", name="GPT-5.4"),
        CouncilMember(model_id="grok-code-fast-1", name="Grok"),
    ]

    council = Council(members, chairman_model="claude-sonnet-4.6", query_fn=mock_query)
    result = await council.convene("Should we use microservices or a monolith?")

    print(f"  Question: {result.question}")
    print(f"\n  Stage 1 — {len(result.stage1.responses)} opinions collected:")
    for model_id, resp in result.stage1.responses.items():
        print(f"    {model_id}: {resp[:60]}...")

    print(f"\n  Stage 2 — Peer review rankings:")
    if result.stage2.aggregate:
        for model_id, avg_rank in result.stage2.aggregate:
            print(f"    {model_id}: avg rank {avg_rank:.2f}")
    else:
        print("    (no parseable rankings)")

    print(f"\n  Stage 3 — Chairman synthesis:")
    print(f"    {result.synthesis[:120]}...")

    print(f"\n  Total LLM calls: {call_count['total']}")
    print("  ✅ Council completed 3-stage consensus")
    print()


# ──────────────────────────────────────────────────────────────────
# 6. Drone Swarm (mock backend)
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.agents.swarm import DroneSwarm, SwarmTask


async def demo_swarm() -> None:
    print("=" * 60)
    print("6. DRONE SWARM (mock)")
    print("=" * 60)

    call_log: list[tuple[str, str]] = []

    async def mock_query(model_id: str, prompt: str) -> str:
        call_log.append((model_id, prompt[:50]))
        if model_id == "gpt-5-mini":
            return f"Drone result for: {prompt[:40]}"
        return "Synthesis: All files processed successfully."

    swarm = DroneSwarm(query_fn=mock_query, max_parallel=5)

    tasks = [
        SwarmTask(id=f"file-{i}", prompt=f"Summarize file_{i}.py", context=f"# file {i}")
        for i in range(8)
    ]

    result = await swarm.execute(tasks)

    print(f"  Total tasks: {result.total_tasks}")
    print(f"  Successful: {result.successful}")
    print(f"  Failed: {result.failed}")
    print(f"  Sample result: {result.results[0].output[:60]}")
    print(f"  Synthesis: {result.synthesis[:80]}...")
    print(f"  LLM calls: {len(call_log)} (8 drone + 1 synthesis = 9)")
    assert result.successful == 8
    print("  ✅ All 8 drone tasks completed + synthesis")
    print()


# ──────────────────────────────────────────────────────────────────
# 7. DAG Execution (mock backend)
# ──────────────────────────────────────────────────────────────────
from cortex_swarm.dag.types import ActivityType, DagNode, NodeResult
from cortex_swarm.dag.runner import DagRunner


async def demo_dag() -> None:
    print("=" * 60)
    print("7. DAG EXECUTION (mock)")
    print("=" * 60)

    execution_order: list[str] = []

    async def mock_execute(model_id: str, prompt: str, node_id: str) -> NodeResult:
        execution_order.append(node_id)
        return NodeResult(
            node_id=node_id,
            output=f"Completed {node_id} with {model_id}",
            model_used=model_id,
            tokens_used=150,
            cost_multiplier=get_model(model_id).multiplier_paid if model_id in COPILOT_MODELS else 1.0,
        )

    runner = DagRunner(execute_fn=mock_execute, compression_method="key_points")

    #   analyze ──→ implement ──→ review
    #      └──────→ test ─────────┘
    nodes = [
        DagNode(id="analyze", activity_type=ActivityType.ANALYSIS,
                prompt_template="Analyze the authentication module"),
        DagNode(id="implement", activity_type=ActivityType.IMPLEMENTATION,
                prompt_template="Implement the refactored auth", depends_on=["analyze"]),
        DagNode(id="test", activity_type=ActivityType.TESTING,
                prompt_template="Write tests for auth module", depends_on=["analyze"]),
        DagNode(id="review", activity_type=ActivityType.REVIEW,
                prompt_template="Review implementation and tests",
                depends_on=["implement", "test"]),
    ]

    result = await runner.run(nodes)

    print(f"  Execution order: {' → '.join(execution_order)}")
    print(f"  All succeeded: {result.success}")
    print(f"  Total tokens: {result.total_tokens}")
    print(f"  Total multiplier cost: {result.total_multiplier_cost}")
    print(f"\n  Node details:")
    for node_id, nr in result.node_results.items():
        print(f"    {node_id}: {nr.model_used} (×{nr.cost_multiplier})")

    # Verify dependencies respected
    assert execution_order.index("analyze") < execution_order.index("implement")
    assert execution_order.index("analyze") < execution_order.index("test")
    assert execution_order.index("implement") < execution_order.index("review")
    assert execution_order.index("test") < execution_order.index("review")
    print("  ✅ DAG executed in correct dependency order")
    print()


# ──────────────────────────────────────────────────────────────────
# 8. CLI commands (dry run)
# ──────────────────────────────────────────────────────────────────
from click.testing import CliRunner
from cortex_swarm.cli import main as cli_main


def demo_cli() -> None:
    print("=" * 60)
    print("8. CLI COMMANDS")
    print("=" * 60)

    runner = CliRunner()

    # Test 'roles' command
    result = runner.invoke(cli_main, ["roles"])
    print("  $ cortex-swarm roles")
    for line in result.output.strip().split("\n")[:8]:
        print(f"    {line}")
    print("    ...")
    assert result.exit_code == 0

    # Test 'status' command
    result = runner.invoke(cli_main, ["status"])
    print("\n  $ cortex-swarm status")
    for line in result.output.strip().split("\n")[:6]:
        print(f"    {line}")
    print("    ...")
    assert result.exit_code == 0

    # Test 'run' command
    result = runner.invoke(cli_main, ["run", "Fix the bug in auth.py"])
    print("\n  $ cortex-swarm run 'Fix the bug in auth.py'")
    for line in result.output.strip().split("\n"):
        print(f"    {line}")
    assert result.exit_code == 0

    print("\n  ✅ All CLI commands work")
    print()


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
async def async_main() -> None:
    await demo_pool()
    await demo_council()
    await demo_swarm()
    await demo_dag()


def main() -> None:
    print()
    print("🧠 cortex-swarm — End-to-End Demo")
    print("=" * 60)
    print()

    # Sync demos
    demo_multiplier()
    demo_registry()
    demo_routing()

    # Async demos
    asyncio.run(async_main())

    # CLI demos
    demo_cli()

    print("=" * 60)
    print("✅ ALL DEMOS PASSED — cortex-swarm is working correctly!")
    print("=" * 60)


if __name__ == "__main__":
    main()
