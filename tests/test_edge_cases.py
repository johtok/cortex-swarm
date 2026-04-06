"""Tests for edge cases found during code review."""

import asyncio
import pytest

from cortex_swarm.agents.pool import AgentPool
from cortex_swarm.agents.swarm import DroneSwarm, SwarmTask
from cortex_swarm.config import load_config, SwarmGlobalConfig, DagConfig, SwarmConfig
from cortex_swarm.council.ranking import parse_ranking, aggregate_rankings, _normalize_label
from cortex_swarm.dag.types import ActivityType, DagNode, NodeResult
from cortex_swarm.dag.runner import topological_sort, DagRunner
from cortex_swarm.models.registry import ModelRegistry, AgentRole
from cortex_swarm.agents.router import TaskRouter, classify_complexity
from cortex_swarm.agents.base import TaskRequest, TaskComplexity


# ── Pool edge cases ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pool_premium_failure_stats_consistent():
    """After a premium task fails, stats should be consistent (no negative counters)."""
    pool = AgentPool(max_premium=2)

    async def failing_task():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await pool.execute("claude-opus-4.6", failing_task)

    assert pool.stats.total_failed == 1
    assert pool.stats.active_premium == 0
    assert pool.stats.queued_premium == 0


@pytest.mark.asyncio
async def test_pool_multiple_premium_failures():
    """Multiple premium failures shouldn't corrupt queue counter."""
    pool = AgentPool(max_premium=2)

    async def failing_task():
        raise ValueError("fail")

    for _ in range(5):
        with pytest.raises(ValueError):
            await pool.execute("claude-opus-4.6", failing_task)

    assert pool.stats.total_failed == 5
    assert pool.stats.active_premium == 0
    assert pool.stats.queued_premium == 0


@pytest.mark.asyncio
async def test_pool_unknown_model():
    """Unknown models should be treated as standard tier, not crash."""
    pool = AgentPool(max_premium=2)

    async def task():
        return "ok"

    result = await pool.execute("totally-fake-model", task)
    assert result == "ok"
    assert pool.stats.total_completed == 1


@pytest.mark.asyncio
async def test_pool_mixed_success_failure():
    """Pool tracks both successful and failed tasks correctly."""
    pool = AgentPool(max_premium=2)
    call_count = 0

    async def sometimes_fail():
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise RuntimeError("even fail")
        return "ok"

    results = []
    for _ in range(4):
        try:
            r = await pool.execute("gpt-5-mini", sometimes_fail)
            results.append(r)
        except RuntimeError:
            pass

    assert pool.stats.total_completed == 2
    assert pool.stats.total_failed == 2


# ── Config validation ────────────────────────────────────────────

def test_config_defaults_valid():
    """Default config should pass validation."""
    cfg = load_config()
    assert cfg.max_premium_concurrent == 2
    assert cfg.default_model == "claude-sonnet-4.6"


def test_config_invalid_max_retries():
    """Negative max_retries should raise ValueError."""
    cfg = SwarmGlobalConfig(dag=DagConfig(max_retries=-1))
    from cortex_swarm.config import _validate_config
    with pytest.raises(ValueError, match="max_retries"):
        _validate_config(cfg)


def test_config_invalid_compression_level():
    """Out-of-range compression_level should raise ValueError."""
    cfg = SwarmGlobalConfig(dag=DagConfig(compression_level=1.5))
    from cortex_swarm.config import _validate_config
    with pytest.raises(ValueError, match="compression_level"):
        _validate_config(cfg)


def test_config_invalid_max_parallel():
    """Zero max_parallel should raise ValueError."""
    cfg = SwarmGlobalConfig(swarm=SwarmConfig(max_parallel=0))
    from cortex_swarm.config import _validate_config
    with pytest.raises(ValueError, match="max_parallel"):
        _validate_config(cfg)


# ── Ranking normalization ────────────────────────────────────────

def test_normalize_label():
    assert _normalize_label("Response A") == "Response A"
    assert _normalize_label("response a") == "Response A"
    assert _normalize_label("RESPONSE B") == "Response B"
    assert _normalize_label("  Response C  ") == "Response C"


def test_parse_ranking_mixed_case():
    """Rankings with mixed case should normalize to consistent labels."""
    text = """
FINAL RANKING:
1. response c
2. RESPONSE A
3. Response B
"""
    result = parse_ranking(text)
    assert result == ["Response C", "Response A", "Response B"]


def test_aggregate_case_insensitive():
    """Aggregation should handle normalized labels correctly."""
    rankings = {
        "m1": ["Response A", "Response B"],
        "m2": ["Response B", "Response A"],
    }
    label_to_model = {
        "Response A": "model-a",
        "Response B": "model-b",
    }
    result = aggregate_rankings(rankings, label_to_model)
    assert len(result) == 2
    # Both should have avg rank 1.5
    assert all(abs(r[1] - 1.5) < 0.01 for r in result)


# ── DAG edge cases ───────────────────────────────────────────────

def test_topological_sort_unknown_dependency():
    """Unknown dependency should raise ValueError."""
    nodes = [
        DagNode(id="a", activity_type=ActivityType.ANALYSIS,
                prompt_template="x", depends_on=["nonexistent"]),
    ]
    with pytest.raises(ValueError, match="unknown node"):
        topological_sort(nodes)


def test_topological_sort_diamond():
    """Diamond dependency graph should be valid."""
    #   A
    #  / \
    # B   C
    #  \ /
    #   D
    nodes = [
        DagNode(id="a", activity_type=ActivityType.ANALYSIS, prompt_template="a"),
        DagNode(id="b", activity_type=ActivityType.ANALYSIS, prompt_template="b", depends_on=["a"]),
        DagNode(id="c", activity_type=ActivityType.ANALYSIS, prompt_template="c", depends_on=["a"]),
        DagNode(id="d", activity_type=ActivityType.SYNTHESIS, prompt_template="d", depends_on=["b", "c"]),
    ]
    result = topological_sort(nodes)
    ids = [n.id for n in result]
    assert ids.index("a") < ids.index("b")
    assert ids.index("a") < ids.index("c")
    assert ids.index("b") < ids.index("d")
    assert ids.index("c") < ids.index("d")


@pytest.mark.asyncio
async def test_dag_cascade_escalation():
    """Failed node should retry with escalated model."""
    models_used = []

    async def failing_then_ok(model_id: str, prompt: str, node_id: str) -> NodeResult:
        models_used.append(model_id)
        if len(models_used) == 1:
            return NodeResult(node_id=node_id, output="", model_used=model_id, success=False, error="fail")
        return NodeResult(node_id=node_id, output="ok", model_used=model_id, tokens_used=10)

    runner = DagRunner(
        execute_fn=failing_then_ok,
        max_retries=1,
        cascade_on_failure=True,
    )
    nodes = [DagNode(id="n1", activity_type=ActivityType.ANALYSIS, prompt_template="test")]
    result = await runner.run(nodes)

    assert result.success
    # First attempt: default model, second: escalated
    assert len(models_used) == 2
    assert models_used[0] == "claude-sonnet-4.6"  # default for ANALYSIS
    assert models_used[1] != models_used[0]  # escalated


@pytest.mark.asyncio
async def test_dag_upstream_failure_skips_downstream():
    """When an upstream node fails, downstream nodes should be skipped."""
    call_log = []

    async def mock_execute(model_id: str, prompt: str, node_id: str) -> NodeResult:
        call_log.append(node_id)
        if node_id == "analyze":
            return NodeResult(node_id=node_id, output="", model_used=model_id,
                              success=False, error="analysis failed")
        return NodeResult(node_id=node_id, output="ok", model_used=model_id, tokens_used=10)

    runner = DagRunner(execute_fn=mock_execute, max_retries=0)
    nodes = [
        DagNode(id="analyze", activity_type=ActivityType.ANALYSIS, prompt_template="analyze"),
        DagNode(id="implement", activity_type=ActivityType.IMPLEMENTATION,
                prompt_template="implement", depends_on=["analyze"]),
    ]
    result = await runner.run(nodes)

    assert not result.success
    assert call_log == ["analyze"]  # implement should NOT have been called
    assert result.node_results["implement"].error is not None
    assert "Skipped" in result.node_results["implement"].error


@pytest.mark.asyncio
async def test_dag_retry_catches_exceptions():
    """execute_fn raising an exception should be retried, not crash the DAG."""
    attempt_count = 0

    async def flaky_execute(model_id: str, prompt: str, node_id: str) -> NodeResult:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise ConnectionError("network timeout")
        return NodeResult(node_id=node_id, output="ok", model_used=model_id, tokens_used=10)

    runner = DagRunner(execute_fn=flaky_execute, max_retries=1, cascade_on_failure=True)
    nodes = [DagNode(id="n1", activity_type=ActivityType.ANALYSIS, prompt_template="test")]
    result = await runner.run(nodes)

    assert result.success
    assert attempt_count == 2  # first attempt failed, second succeeded


@pytest.mark.asyncio
async def test_dag_empty():
    """Empty DAG should succeed with no results."""
    async def noop(m, p, n):
        raise AssertionError("should not be called")

    runner = DagRunner(execute_fn=noop)
    result = await runner.run([])
    assert result.success
    assert len(result.node_results) == 0


# ── Router edge cases ────────────────────────────────────────────

def test_router_explicit_complexity():
    """Explicit complexity should be respected, not overridden by token heuristic."""
    cfg = load_config()
    registry = ModelRegistry(cfg.roles)
    router = TaskRouter(registry, cfg.routing)

    task = TaskRequest(prompt="short", complexity=TaskComplexity.CRITICAL)
    decision = router.route(task)
    assert decision.role == AgentRole.ORACLE


def test_router_escalation_chain():
    """Escalation should go drone→scout→worker→sage→oracle."""
    cfg = load_config()
    registry = ModelRegistry(cfg.roles)
    router = TaskRouter(registry, cfg.routing)

    path = []
    role = AgentRole.DRONE
    for _ in range(5):
        esc = router.escalate(role)
        path.append(esc.role)
        role = esc.role

    assert path == [
        AgentRole.SCOUT, AgentRole.WORKER, AgentRole.SAGE,
        AgentRole.ORACLE, AgentRole.ORACLE,  # stays at top
    ]


# ── Registry edge cases ─────────────────────────────────────────

def test_registry_override():
    """Role overrides should change primary model."""
    registry = ModelRegistry(role_overrides={
        "worker": {"model": "gpt-5.2"},
    })
    assert registry.get_model_for_role(AgentRole.WORKER) == "gpt-5.2"
    # Other roles unaffected
    assert registry.get_model_for_role(AgentRole.ORACLE) == "claude-opus-4.6"


def test_registry_unknown_role_override_ignored():
    """Unknown role names in overrides should be silently ignored."""
    registry = ModelRegistry(role_overrides={
        "nonexistent_role": {"model": "something"},
    })
    # Should not crash, existing roles unchanged
    assert registry.get_model_for_role(AgentRole.WORKER) == "claude-sonnet-4.6"


# ── Swarm edge cases ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_swarm_synthesis_failure_preserves_results():
    """If synthesis fails, drone results should still be returned."""
    async def mock_query(model_id: str, prompt: str) -> str:
        if model_id == "claude-sonnet-4.6":
            raise RuntimeError("synthesis backend down")
        return f"Result from {model_id}"

    swarm = DroneSwarm(query_fn=mock_query, max_parallel=5)
    tasks = [SwarmTask(id=f"t{i}", prompt=f"task {i}") for i in range(3)]

    result = await swarm.execute(tasks)
    assert result.successful == 3
    assert result.failed == 0
    assert "[Synthesis failed" in result.synthesis
