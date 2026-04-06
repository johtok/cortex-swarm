"""Tests for DAG execution engine."""

import asyncio
import pytest
from cortex_swarm.dag.types import ActivityType, DagNode, NodeResult
from cortex_swarm.dag.runner import topological_sort, DagRunner
from cortex_swarm.dag.compression import compress_context


def test_topological_sort_linear():
    nodes = [
        DagNode(id="a", activity_type=ActivityType.ANALYSIS, prompt_template="analyze", depends_on=[]),
        DagNode(id="b", activity_type=ActivityType.IMPLEMENTATION, prompt_template="impl", depends_on=["a"]),
        DagNode(id="c", activity_type=ActivityType.REVIEW, prompt_template="review", depends_on=["b"]),
    ]
    result = topological_sort(nodes)
    ids = [n.id for n in result]
    assert ids.index("a") < ids.index("b") < ids.index("c")


def test_topological_sort_cycle_raises():
    nodes = [
        DagNode(id="a", activity_type=ActivityType.ANALYSIS, prompt_template="x", depends_on=["b"]),
        DagNode(id="b", activity_type=ActivityType.ANALYSIS, prompt_template="y", depends_on=["a"]),
    ]
    with pytest.raises(ValueError, match="cycle"):
        topological_sort(nodes)


def test_compress_extractive():
    text = "A" * 1000
    result = compress_context(text, "extractive", 0.5)
    assert len(result) < len(text)
    assert "[... compressed ...]" in result


def test_compress_none():
    text = "hello world"
    assert compress_context(text, "none") == text


def test_compress_key_points():
    text = "# Header\nsome text\n- bullet point\nmore text\ndef function():\n  pass"
    result = compress_context(text, "key_points", 0.3)
    assert "# Header" in result
    assert "- bullet point" in result


@pytest.mark.asyncio
async def test_dag_runner_simple():
    """Test a simple 2-node DAG execution."""
    call_log = []

    async def mock_execute(model_id: str, prompt: str, node_id: str) -> NodeResult:
        call_log.append(node_id)
        return NodeResult(
            node_id=node_id,
            output=f"Output from {node_id}",
            model_used=model_id,
            tokens_used=100,
        )

    runner = DagRunner(execute_fn=mock_execute, max_retries=0)

    nodes = [
        DagNode(id="analyze", activity_type=ActivityType.ANALYSIS, prompt_template="Analyze this"),
        DagNode(id="implement", activity_type=ActivityType.IMPLEMENTATION, prompt_template="Implement this", depends_on=["analyze"]),
    ]

    result = await runner.run(nodes)
    assert result.success
    assert len(result.node_results) == 2
    assert call_log == ["analyze", "implement"]
