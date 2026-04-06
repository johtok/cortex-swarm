# Architecture Guide

## Overview

cortex-swarm is a **multi-agent orchestrator** that coordinates AI model calls with intelligent routing, budget-aware concurrency control, and multi-model consensus. It is designed for the GitHub Copilot ecosystem and respects Copilot's Model Multiplier pricing.

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI / API                               │
│                    (cli.py — Click entry)                        │
├────────┬──────────┬─────────────┬───────────┬───────────────────┤
│ Router │  Council │ Drone Swarm │    DAG    │   Agent Pool      │
│        │ (3-stage)│ (fan-out)   │  Engine   │ (concurrency)     │
├────────┴──────────┴─────────────┴───────────┴───────────────────┤
│                     Model Registry                              │
│              (roles, fallback chains, overrides)                 │
├─────────────────────────────────────────────────────────────────┤
│                    Multiplier Table                              │
│              (24 models, tier classification)                    │
├─────────────────────────────────────────────────────────────────┤
│                   LLM Backends (Adapters)                       │
│         Copilot CLI  ·  OpenAI-compat API  ·  Mock              │
└─────────────────────────────────────────────────────────────────┘
```

## Core Design Principles

### 1. Sonnet-first, Premium-gated

Every decision defaults to **Claude Sonnet 4.6** (multiplier=1). Premium models (Opus 4.6, multiplier=3+) are reserved for critical tasks and hard-capped at **2 concurrent** via `asyncio.Semaphore`. GPT-5 mini (multiplier=0) is unlimited and free.

### 2. Stateless Agents

Agents are not persistent entities — they are **stateless function calls** parameterized by a model ID, system prompt, and task. There is no shared memory or conversation history between agent invocations. This keeps the system simple and predictable.

### 3. Backend-agnostic

All LLM calls go through a `query_fn(model_id, prompt) → str` callback. The orchestration logic never talks to an API directly. This means you can swap backends (Copilot CLI, OpenAI API, mock) without changing any orchestration code.

---

## Module Map

### `models/` — Model Intelligence

| File | Purpose |
|------|---------|
| `multiplier.py` | Complete Copilot multiplier table (24 models). `ModelInfo` dataclass with tier classification. `is_premium()` helper. |
| `registry.py` | `AgentRole` enum (Oracle/Worker/Sage/Scout/Drone). `RoleConfig` with primary model + fallback chain. `ModelRegistry` with override support and `resolve_model()` fallback logic. |

**Key type:** `ModelTier` — FREE (×0), CHEAP (≤×0.33), STANDARD (×1), PREMIUM (≥×3)

### `agents/` — Execution Layer

| File | Purpose |
|------|---------|
| `base.py` | `Agent` protocol, `TaskRequest`, `AgentResult`, `TaskComplexity` enum. All agents implement the `Agent` protocol. |
| `pool.py` | `AgentPool` with `asyncio.Semaphore(2)` for premium models. Tracks `PoolStats` (active/queued/completed/failed per tier). |
| `router.py` | `TaskRouter` classifies complexity by token estimate, maps to role, supports cascade escalation (drone→scout→worker→sage→oracle). |
| `swarm.py` | `DroneSwarm` — fan-out N tasks to GPT-5 mini, merge with Sonnet synthesis. Semaphore-bounded parallelism. |
| `roles.py` | Human-readable role descriptions and `list_all_roles()` helper. |

### `council/` — Multi-Model Consensus

| File | Purpose |
|------|---------|
| `session.py` | `Council` class — 3-stage orchestration. `CouncilMember`, `Stage1Result`, `Stage2Result`, `CouncilResult`. |
| `ranking.py` | `parse_ranking()` extracts "FINAL RANKING:" from text. `aggregate_rankings()` computes average rank scores. Case-normalized labels. |
| `synthesis.py` | `build_synthesis_prompt()` — constructs the chairman's synthesis prompt from all stages. |

**Council members:** Gemini 2.5 Pro, Sonnet 4.6, GPT-5.4, Grok Code Fast 1
**Chairman:** Sonnet 4.6

**3-stage process:**
1. **Independent opinions** — all 4 models answer in parallel
2. **Anonymized peer review** — each model ranks the others' responses blind (labels: Response A/B/C/D)
3. **Chairman synthesis** — Sonnet combines insights weighted by peer rankings

### `dag/` — Task Graph Execution

| File | Purpose |
|------|---------|
| `types.py` | `ActivityType` enum, `ToolPolicy` (per-node tool confinement), `DagNode`, `NodeResult`, `DagResult`. `ACTIVITY_ROLE` maps activity types to default roles. |
| `runner.py` | `DagRunner` — topological sort (Kahn's), context compression between nodes, cascade escalation on failure, dependency-aware skip on upstream failure. |
| `compression.py` | `compress_context()` — extractive (first+last), key_points (headers/bullets/code), summary (smart truncation). |

**Dependency semantics:** If node A fails, all nodes that depend on A are automatically skipped with an error message. They are never executed with missing context.

### `adapters/` — LLM Backends

| File | Purpose |
|------|---------|
| `copilot.py` | `CopilotCLIBackend` (subprocess), `OpenAICompatBackend` (httpx), `MockBackend` (testing). All implement `LLMBackend` protocol: `async query(model_id, prompt) → str`. |

### `config.py` — Configuration

Layered config: dataclass defaults → `default_config.yaml` (shipped in package) → user YAML override.

Validated on load: `max_premium_concurrent ≥ 1`, `max_retries ≥ 0`, `compression_level ∈ [0,1]`, `max_parallel ≥ 1`.

---

## Data Flow Examples

### Single Task Execution

```
User prompt
  → TaskRouter.route() — classify complexity, pick role
  → ModelRegistry.get_model_for_role() — resolve model ID
  → AgentPool.execute() — semaphore gate if premium
  → query_fn(model_id, prompt) — actual LLM call
  → AgentResult
```

### Council Session

```
Question
  → Stage 1: gather([query(gemini, q), query(sonnet, q), query(gpt54, q), query(grok, q)])
  → Stage 2: anonymize responses → gather([query(m, review_prompt) for m in members])
  → parse_ranking() each review → aggregate_rankings()
  → Stage 3: build_synthesis_prompt() → query(chairman, synthesis_prompt)
  → CouncilResult
```

### DAG Execution

```
Node definitions with depends_on edges
  → topological_sort() — Kahn's algorithm, validates no cycles or missing deps
  → For each node in order:
      → Check upstream failures → skip if any dependency failed
      → Gather upstream outputs → compress_context()
      → Inject compressed context into prompt template
      → _execute_with_retry() — try primary model, escalate on failure
      → Store output for downstream nodes
  → DagResult
```

---

## Concurrency Model

```
                    ┌───────────────────┐
                    │   AgentPool       │
                    │                   │
  Premium tasks ──► │  Semaphore(2) ────┼──► max 2 concurrent Opus calls
                    │                   │
  Standard tasks ─► │  (no gate) ───────┼──► unlimited Sonnet/GPT-5.4
                    │                   │
  Free tasks ─────► │  (no gate) ───────┼──► unlimited GPT-5 mini
                    └───────────────────┘
```

All premium model calls **must** go through `AgentPool.execute()`. The semaphore ensures at most 2 premium agents run simultaneously, regardless of how many are queued. Stats are tracked per-tier with an `asyncio.Lock` to prevent races.

---

## Cascade Escalation

When a task fails, the router can automatically retry with a more capable model:

```
gpt-5-mini → claude-haiku-4.5 → claude-sonnet-4.6 → gpt-5.4 → claude-opus-4.6
  (free)        (cheap)            (standard)         (standard)    (premium)
```

Escalation is opt-in (`cascade_on_failure: true` in config) and respects the premium concurrency limit.

---

## Extending cortex-swarm

### Adding a new model

1. Add entry to `COPILOT_MODELS` dict in `multiplier.py`
2. Tier is auto-derived from `multiplier_paid` value

### Adding a new role

1. Add to `AgentRole` enum in `registry.py`
2. Add `RoleConfig` to `DEFAULT_ROLES` with model + fallback chain
3. Add description to `ROLE_DESCRIPTIONS` in `roles.py`
4. Add complexity mapping in `COMPLEXITY_ROLE_MAP` in `router.py`
5. Add escalation path entry in `ESCALATION_PATH`

### Adding a new backend

Implement the `LLMBackend` protocol:

```python
class MyBackend:
    async def query(self, model_id: str, prompt: str) -> str:
        # Your implementation here
        ...
```

Pass `backend.query` as the `query_fn` to Council, DroneSwarm, or DagRunner.
