# cortex-swarm — LLM Agent Instructions

**Generated:** 2026-04-06 | **Branch:** master

## OVERVIEW

Python multi-agent orchestrator with premium concurrency control, LLM council consensus, and drone swarms. Copilot Model Multiplier-aware. ~2k LOC across 18 source files, 43 tests.

## STRUCTURE

```
cortex-swarm/
├── src/cortex_swarm/
│   ├── __init__.py               # Package entry, __version__
│   ├── cli.py                    # Click CLI: run, council, swarm, roles, status
│   ├── config.py                 # YAML config loader with validation
│   ├── default_config.yaml       # Default configuration (shipped in wheel)
│   ├── models/
│   │   ├── multiplier.py         # 24 Copilot models, ModelInfo, ModelTier, is_premium()
│   │   └── registry.py           # AgentRole enum, RoleConfig, ModelRegistry with fallbacks
│   ├── agents/
│   │   ├── base.py               # Agent protocol, TaskRequest, AgentResult, TaskComplexity
│   │   ├── pool.py               # AgentPool with asyncio.Semaphore(2) for premium
│   │   ├── router.py             # TaskRouter: complexity → role → model, cascade escalation
│   │   ├── swarm.py              # DroneSwarm: fan-out GPT-5 mini + Sonnet synthesis
│   │   └── roles.py              # Role descriptions and list_all_roles()
│   ├── council/
│   │   ├── session.py            # 3-stage Council (opinions → peer review → synthesis)
│   │   ├── ranking.py            # FINAL RANKING parser, case normalization, aggregation
│   │   └── synthesis.py          # Chairman synthesis prompt builder
│   ├── dag/
│   │   ├── types.py              # DagNode, NodeResult, DagResult, ActivityType, ToolPolicy
│   │   ├── runner.py             # DagRunner: topo sort, compression, cascade, skip-on-fail
│   │   └── compression.py        # extractive, key_points, summary compression
│   └── adapters/
│       └── copilot.py            # CopilotCLIBackend, OpenAICompatBackend, MockBackend
├── tests/
│   ├── test_multiplier.py        # Model table and tier tests
│   ├── test_pool.py              # Pool concurrency and stats tests
│   ├── test_council.py           # Council ranking, aggregation, session tests
│   ├── test_dag.py               # DAG execution, compression, dependency tests
│   └── test_edge_cases.py        # 22 edge cases from two critic passes
├── examples/
│   └── demo.py                   # 8-section end-to-end demo with mock backends
├── docs/
│   ├── architecture.md           # Architecture guide, module map, data flows
│   └── faq.md                    # FAQ: models, pricing, routing, council, swarm, DAG
├── pyproject.toml                # hatchling build, dependencies, pytest config
├── install.sh                    # One-line installer script
└── .github/workflows/ci.yml     # CI: Python 3.11/3.12/3.13, tests + mypy + ruff
```

## KEY CONCEPTS

### Model Tiers (from multiplier.py)

| Tier | Multiplier | Examples | Concurrency |
|------|-----------|----------|-------------|
| FREE | 0 | gpt-5-mini, gpt-4.1, gpt-4o | Unlimited |
| CHEAP | 0.25–0.33 | claude-haiku-4.5, grok-code-fast-1 | Unlimited |
| STANDARD | 1 | claude-sonnet-4.6, gpt-5.4, gemini-2.5-pro | Unlimited |
| PREMIUM | 3–30 | claude-opus-4.6, claude-opus-4.6-fast | Max 2 concurrent |

### Agent Roles (from registry.py)

| Role | Default Model | Fallback Chain | Use For |
|------|--------------|----------------|---------|
| ORACLE | claude-opus-4.6 | gpt-5.4 → sonnet-4.6 | Critical: security, architecture |
| WORKER | claude-sonnet-4.6 | gpt-5.4 → haiku-4.5 | Default workhorse for everything |
| SAGE | gpt-5.4 | sonnet-4.6 → haiku-4.5 | Long context, large codebase |
| SCOUT | claude-haiku-4.5 | gpt-5-mini | Simple lookups, formatting |
| DRONE | gpt-5-mini | (none) | Bulk parallel, free |

### Cascade Escalation

```
DRONE → SCOUT → WORKER → SAGE → ORACLE
(free)  (cheap)  (std)    (std)   (premium)
```

On task failure, retry with next tier. Clamped to highest available model.

### Council (3-stage, from council/)

1. **Independent opinions** — 4 models answer in parallel (Gemini, Sonnet, GPT-5.4, Grok)
2. **Anonymized peer review** — each model ranks others' responses blind
3. **Chairman synthesis** — Sonnet 4.6 synthesizes from all opinions + rankings

### Premium Gate (from pool.py)

`asyncio.Semaphore(2)` — at most 2 premium (Opus) calls concurrent. Standard and free: unlimited.

## WHERE TO LOOK

| Task | Files | Notes |
|------|-------|-------|
| Add a new model | `models/multiplier.py` | Add to `COPILOT_MODELS` dict, tier auto-derived |
| Add a new agent role | `models/registry.py`, `agents/roles.py`, `agents/router.py` | Enum + RoleConfig + description + routing |
| Change routing heuristics | `agents/router.py` | `COMPLEXITY_ROLE_MAP`, `ESCALATION_PATH`, token thresholds |
| Change premium concurrency | `config.py`, `agents/pool.py` | `max_premium_concurrent` config key |
| Add a new LLM backend | `adapters/copilot.py` | Implement `async query(model_id, prompt) → str` |
| Change council composition | `default_config.yaml`, `council/session.py` | Config `council.members` and `council.chairman` |
| Change drone swarm settings | `default_config.yaml`, `agents/swarm.py` | Config `swarm.model`, `swarm.max_parallel` |
| Add a DAG node type | `dag/types.py` | Add to `ActivityType` enum and `ACTIVITY_ROLE` map |
| Change context compression | `dag/compression.py` | Three methods: extractive, key_points, summary |
| Add CLI command | `cli.py` | Click group, follow existing patterns |
| Add tests | `tests/test_*.py` | Use `@pytest.mark.asyncio`, `MockBackend` for LLM calls |

## CONVENTIONS

- **Runtime**: Python 3.11+, asyncio for concurrency
- **Build**: hatchling with `src/` layout, `pythonpath = ["src"]` in pytest config
- **Dependencies**: click, pyyaml, httpx (runtime); pytest, pytest-asyncio, mypy, ruff (dev)
- **Config format**: YAML with layered defaults → user override
- **All LLM calls** go through `query_fn(model_id: str, prompt: str) → str` callback
- **Agents are stateless**: no memory between invocations, no shared context
- **Tests**: all use `MockBackend` or inline mocks, no real API calls
- **Error handling**: `BaseException` for proper `CancelledError` propagation
- **File naming**: snake_case for all Python files
- **Async mode**: `auto` for pytest-asyncio (just use `async def test_*`)

## ANTI-PATTERNS

- Never import from `adapters.copilot` to bypass `query_fn` — always use the callback
- Never call premium models without going through `AgentPool.execute()` — it gates concurrency
- Never modify `COPILOT_MODELS` at runtime — it's treated as immutable
- Never use `CancelledError` inside a bare `except Exception` — use `BaseException`
- Never execute DAG nodes whose upstream dependencies failed — they get skipped
- Never assume model availability — always provide fallback chains in `RoleConfig`

## COMMANDS

```bash
# Install
pip install -e ".[dev]"

# Run tests
pytest -v

# Type check
mypy src/

# Lint
ruff check src/ tests/

# Run demo
python examples/demo.py

# CLI
cortex-swarm --help
cortex-swarm run "your task here"
cortex-swarm council "high-stakes question"
cortex-swarm swarm "bulk task description" --count 10
cortex-swarm roles
cortex-swarm status
```

## DATA FLOW

```
User task → TaskRouter.route()
  → classify complexity (token estimate)
  → map to AgentRole
  → ModelRegistry.resolve_model(role)
  → AgentPool.execute(model_id, prompt, query_fn)
    → if premium: acquire Semaphore(2) first
    → query_fn(model_id, prompt)
    → return AgentResult
```

Council, Swarm, and DAG are higher-level orchestrators that use the same `query_fn` callback internally.
