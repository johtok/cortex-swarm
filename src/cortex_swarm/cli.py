"""cortex-swarm CLI entry point.

Commands:
  run      — Execute a single task with auto-routing
  council  — Run an LLM council for a question
  swarm    — Fan-out a batch of tasks to GPT-5 mini drones
  roles    — List available agent roles
  status   — Show model multiplier table
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from cortex_swarm import __version__
from cortex_swarm.agents.roles import list_all_roles
from cortex_swarm.models.multiplier import COPILOT_MODELS, ModelTier


@click.group()
@click.version_option(version=__version__, prog_name="cortex-swarm")
def main() -> None:
    """cortex-swarm — Multi-agent orchestrator with premium concurrency control."""


@main.command()
@click.argument("prompt")
@click.option("--role", "-r", default=None, help="Force a specific role (oracle/worker/sage/scout/drone)")
@click.option("--model", "-m", default=None, help="Force a specific model ID")
@click.option("--config", "-c", type=click.Path(exists=True), default=None, help="Config file path")
def run(prompt: str, role: str | None, model: str | None, config: str | None) -> None:
    """Execute a single task with auto-routing."""
    from cortex_swarm.agents.base import TaskRequest, TaskComplexity
    from cortex_swarm.agents.pool import AgentPool
    from cortex_swarm.agents.router import TaskRouter
    from cortex_swarm.config import load_config
    from cortex_swarm.models.registry import ModelRegistry

    cfg = load_config(Path(config) if config else None)
    registry = ModelRegistry(cfg.roles)
    router = TaskRouter(registry, cfg.routing)
    pool = AgentPool(max_premium=cfg.max_premium_concurrent)

    task = TaskRequest(prompt=prompt, preferred_role=role)
    decision = router.route(task)

    final_model = model or decision.model_id

    click.echo(f"🧠 Routing: {decision.reason}")
    click.echo(f"📡 Model: {final_model}")
    click.echo(f"⚡ Role: {decision.role.value}")
    click.echo()

    # In a real implementation, this would execute via the adapter
    click.echo("⏳ Execution would happen here via the configured backend.")
    click.echo("   Configure a backend in your config file or use --backend flag.")
    click.echo()
    click.echo(f"📊 Pool stats: max_premium={cfg.max_premium_concurrent}")


@main.command()
@click.argument("question")
@click.option("--config", "-c", type=click.Path(exists=True), default=None, help="Config file path")
def council(question: str, config: str | None) -> None:
    """Run an LLM council for a question."""
    from cortex_swarm.config import load_config

    cfg = load_config(Path(config) if config else None)

    click.echo("🏛️  LLM Council Session")
    click.echo(f"   Members: {', '.join(cfg.council.members)}")
    click.echo(f"   Chairman: {cfg.council.chairman}")
    click.echo()
    click.echo(f"❓ Question: {question}")
    click.echo()
    click.echo("Stage 1: Collecting independent opinions (parallel)...")
    click.echo("Stage 2: Anonymized peer review...")
    click.echo("Stage 3: Chairman synthesis...")
    click.echo()
    click.echo("⏳ Council execution requires a configured backend.")
    click.echo("   Set OPENAI_API_KEY or configure copilot backend in config.")


@main.command()
@click.argument("task_description")
@click.option("--count", "-n", default=5, help="Number of sub-tasks to create")
@click.option("--config", "-c", type=click.Path(exists=True), default=None, help="Config file path")
def swarm(task_description: str, count: int, config: str | None) -> None:
    """Fan-out a task to GPT-5 mini drones."""
    from cortex_swarm.config import load_config

    cfg = load_config(Path(config) if config else None)

    click.echo("🐝 Drone Swarm")
    click.echo(f"   Model: {cfg.swarm.model} (FREE, multiplier=0)")
    click.echo(f"   Max parallel: {cfg.swarm.max_parallel}")
    click.echo(f"   Synthesis by: {cfg.swarm.synthesis_model}")
    click.echo(f"   Sub-tasks: {count}")
    click.echo()
    click.echo(f"📋 Task: {task_description}")
    click.echo()
    click.echo("⏳ Swarm execution requires a configured backend.")


@main.command()
def roles() -> None:
    """List available agent roles and their models."""
    click.echo("🎭 Agent Roles\n")

    for info in list_all_roles():
        tier_emoji = {
            "free": "🟢", "cheap": "🟡", "standard": "🔵", "premium": "🔴",
        }.get(info["tier"], "⚪")

        click.echo(f"  {tier_emoji} {info['role'].upper()}")
        click.echo(f"     Model: {info['model']} (×{info['multiplier']} multiplier)")
        click.echo(f"     Fallback: {' → '.join(info['fallback_chain'])}")
        click.echo(f"     {info['description']}")
        click.echo()


@main.command()
def status() -> None:
    """Show the Copilot model multiplier table."""
    click.echo("📊 Copilot Model Multiplier Table\n")

    for tier in ModelTier:
        tier_emoji = {
            ModelTier.FREE: "🟢", ModelTier.CHEAP: "🟡",
            ModelTier.STANDARD: "🔵", ModelTier.PREMIUM: "🔴",
        }[tier]

        models = [m for m in COPILOT_MODELS.values() if m.tier == tier]
        if not models:
            continue

        click.echo(f"  {tier_emoji} {tier.value.upper()} (multiplier={'0' if tier == ModelTier.FREE else '≤0.33' if tier == ModelTier.CHEAP else '1' if tier == ModelTier.STANDARD else '≥3'})")
        for m in sorted(models, key=lambda x: x.multiplier_paid):
            free_str = f" (free: ×{m.multiplier_free})" if m.multiplier_free is not None else ""
            click.echo(f"     {m.id:<30} ×{m.multiplier_paid}{free_str}")
        click.echo()


if __name__ == "__main__":
    main()
