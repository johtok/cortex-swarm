# Frequently Asked Questions

## General

### What is cortex-swarm?

A Python orchestration framework that coordinates multiple AI model calls with intelligent routing, budget-aware concurrency control, and multi-model consensus. It's designed for the GitHub Copilot ecosystem and respects Copilot's Model Multiplier pricing.

### What problem does it solve?

When you have access to many AI models with different costs and capabilities, you need a system that:
- Routes tasks to the right model (don't waste Opus on a typo fix)
- Limits expensive calls (max 2 premium agents at once)
- Enables multi-model consensus for important decisions
- Handles bulk work cheaply (GPT-5 mini swarms for free)
- Executes multi-step workflows with dependency tracking

### What inspired this project?

Three projects:
- **[oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)** — Multi-agent architecture, named roles, background management
- **[karpathy/llm-council](https://github.com/karpathy/llm-council)** — Multi-model consensus with anonymized peer review
- **[context-distillation-orchestrator](https://github.com/johtok/context-distillation-orchestrator)** — DAG execution, tiered model routing, context compression

---

## Models & Pricing

### Why is Sonnet 4.6 the default for everything?

Sonnet 4.6 has a multiplier of 1 (standard cost), excellent quality, and is fast. It's the best balance of cost and capability for the vast majority of tasks. The system is deliberately biased toward Sonnet — when in doubt, use Sonnet.

### What's "free" about GPT-5 mini?

GPT-5 mini has a Copilot multiplier of **0** on paid plans, meaning it costs nothing against your usage quota. This makes it ideal for bulk parallel work (the "drone swarm" pattern). You can run as many concurrent GPT-5 mini calls as you want.

### When should I use Opus 4.6 (premium)?

Only for the most critical tasks: security reviews, architectural decisions, complex debugging where getting it wrong has severe consequences. Opus has a 3× multiplier and is limited to 2 concurrent calls. The router assigns it automatically for "critical" complexity tasks.

### What's the multiplier?

GitHub Copilot uses "multipliers" to track model usage against your plan's quota. A multiplier of 1 means standard cost. Multiplier 0 = free. Multiplier 3 = costs 3× a standard request. See the full table with `cortex-swarm status`.

### Can I use models not in the table?

Yes, but they'll be treated as "standard" tier by default (no premium gating). Add them to `COPILOT_MODELS` in `multiplier.py` for proper tier classification.

---

## Agent Roles

### What are the 5 roles?

| Role | Model | Multiplier | Use For |
|------|-------|------------|---------|
| **Oracle** | Opus 4.6 | 3 (premium) | Critical tasks, architecture, security review |
| **Worker** | Sonnet 4.6 | 1 (standard) | Everything else — the default workhorse |
| **Sage** | GPT-5.4 | 1 (standard) | Large codebase analysis, long context |
| **Scout** | Haiku 4.5 | 0.33 (cheap) | Simple lookups, formatting, boilerplate |
| **Drone** | GPT-5 mini | 0 (free) | Bulk parallel tasks in swarms |

### How does routing work?

The router estimates task complexity from prompt length (tokens ≈ characters/4):
- **≤500 tokens** → Trivial → Drone (GPT-5 mini, free)
- **≤2000 tokens** → Simple → Scout (Haiku, cheap)
- **≤10000 tokens** → Moderate → Worker (Sonnet, standard)
- **≤50000 tokens** → Complex → Sage (GPT-5.4, standard)
- **>50000 tokens** → Critical → Oracle (Opus, premium)

You can override this with `--role oracle` or by setting `task.complexity` directly.

### What happens when a task fails?

Cascade escalation: the system retries with the next tier up.

```
Drone → Scout → Worker → Sage → Oracle
```

If a drone task fails, it's retried with Scout (Haiku). If that fails, Worker (Sonnet). And so on up to Oracle. Escalation is configurable (`cascade_on_failure` in config).

---

## Premium Concurrency

### Why limit to 2 premium agents?

Premium models (Opus 4.6, multiplier ≥ 3) are expensive — each call costs 3-30× a standard call. Running many concurrently would burn through your Copilot quota extremely fast. The limit of 2 ensures you get premium quality when needed without runaway costs.

### What happens when a 3rd premium task is submitted?

It queues. The `asyncio.Semaphore(2)` blocks the 3rd task until one of the first two completes. Standard and free tasks continue running without any gate.

### Can I change the limit?

Yes. In your config YAML:
```yaml
max_premium_concurrent: 3  # or any positive integer
```

### Do standard/free tasks have limits?

No. Sonnet, Haiku, GPT-5 mini, and all other non-premium models run with no concurrency restrictions. The drone swarm uses its own `max_parallel` setting (default 20) to avoid overwhelming the backend, but that's a practical limit, not a budget one.

---

## Council Mode

### When should I use the council?

For high-stakes decisions where you want multiple perspectives:
- Architecture choices ("microservices vs monolith?")
- Code review of security-critical code
- Design decisions with long-term consequences
- Any question where diverse opinions add value

### How does the 3-stage process work?

1. **Stage 1 — Independent opinions:** All 4 council members (Gemini, Sonnet, GPT-5.4, Grok) answer the question independently and in parallel. No model sees another's answer.

2. **Stage 2 — Anonymized peer review:** Each model receives all 4 responses anonymized as "Response A/B/C/D" and must evaluate and rank them. This prevents bias — models can't favor their own response.

3. **Stage 3 — Chairman synthesis:** Sonnet 4.6 (the chairman) receives all responses, all peer evaluations, and the aggregate rankings. It synthesizes a final answer that takes the best insights from each.

### Why those 4 models?

Diversity of training data, architecture, and reasoning patterns:
- **Gemini 2.5 Pro** — Strong structured reasoning, different training data
- **Claude Sonnet 4.6** — Balanced analysis, our default workhorse
- **GPT-5.4** — Broad knowledge, long context
- **Grok Code Fast 1** — Contrarian/different perspective, fast

### Can I change the council members?

Yes, in config:
```yaml
council:
  members:
    - gemini-2.5-pro
    - claude-sonnet-4.6
    - gpt-5.4
    - gpt-5.2  # swap Grok for GPT-5.2
  chairman: claude-sonnet-4.6
```

---

## Drone Swarm

### What's a drone swarm?

A pattern for bulk parallel work: split a large task into many small sub-tasks, fan them all out to GPT-5 mini (free!), then merge the results with a single Sonnet synthesis pass.

Example: "Summarize each of the 50 Python files in this directory" → 50 drone tasks + 1 synthesis = 51 LLM calls, of which 50 are free.

### How many drones can run at once?

Default `max_parallel` is 20 (configurable). This is a practical limit to avoid overwhelming the backend, not a budget limit — GPT-5 mini is free.

### What if synthesis fails?

Drone results are preserved. The `SwarmBatchResult` will contain all individual results, and `synthesis` will contain an error message like `[Synthesis failed: ...]`. You don't lose drone work.

---

## DAG Execution

### What's a DAG?

A Directed Acyclic Graph — a workflow where tasks have dependencies. "Analyze first, then implement based on analysis, then test, then review."

### How does context pass between nodes?

Upstream node outputs are **compressed** before being injected into downstream prompts. Three compression methods:
- **extractive** — Keep first + last portions (most info-dense)
- **key_points** — Extract headers, bullets, code definitions, errors
- **summary** — Smart truncation at paragraph/sentence boundaries

### What if an upstream node fails?

All downstream nodes that depend on it are **skipped** with a clear error message. They are never executed with missing context. This prevents cascading garbage.

### Can nodes run in parallel?

Currently nodes execute sequentially in topological order. Nodes at the same "level" (no dependencies between them) could theoretically run in parallel — this is a future enhancement.

---

## Configuration

### Where does config come from?

Three layers, in priority order:
1. **Dataclass defaults** (hardcoded in `config.py`)
2. **`default_config.yaml`** (shipped inside the package)
3. **User YAML** (passed via `--config path/to/config.yaml`)

Each layer overrides only the keys it specifies.

### What gets validated?

- `max_premium_concurrent` must be ≥ 1
- `dag.max_retries` must be ≥ 0
- `dag.compression_level` must be in [0, 1]
- `swarm.max_parallel` must be ≥ 1

Invalid values raise `ValueError` at config load time.

---

## Development

### How do I run the tests?

```bash
cd cortex-swarm
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

### How do I add a test?

Add to `tests/test_*.py`. Async tests use `@pytest.mark.asyncio`. The project uses `asyncio_mode = "auto"` so you can also just define `async def test_*` without the decorator.

### Do I need real API keys to test?

No. All tests use `MockBackend` or inline mock functions. No real LLM calls are made during testing.

### How do I try the demo?

```bash
pip install -e ".[dev]"
python examples/demo.py
```

This exercises all 8 subsystems (multiplier, registry, routing, pool, council, swarm, DAG, CLI) with mock backends.
