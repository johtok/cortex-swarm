# 🧠 cortex-swarm

**Multi-agent orchestrator with premium concurrency control, LLM council, drone swarm, and DAG execution — Copilot Multiplier-aware.**

> *"One brain is good. A cortex of many is better."*

You have access to 24+ models with wildly different costs. Don't think about which one to use.

cortex-swarm routes tasks to the right model automatically, gates expensive calls behind a semaphore, fans out free models in swarms, and convenes multi-model councils for high-stakes decisions. All budget-aware through Copilot's Model Multiplier system.

---

## Installation

### For Humans

One command. It clones, creates a venv, installs, and runs tests:

```bash
curl -sSL https://raw.githubusercontent.com/johtok/cortex-swarm/master/install.sh | bash
```

Or do it manually:

```bash
git clone https://github.com/johtok/cortex-swarm.git
cd cortex-swarm
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v   # verify everything works
```

### For LLM Agents

Fetch the agent instructions and follow them:

```bash
curl -s https://raw.githubusercontent.com/johtok/cortex-swarm/master/AGENTS.md
```

Or read [`AGENTS.md`](AGENTS.md) directly — it contains the full structure map, conventions, anti-patterns, and where-to-look table for any modification task.

**Quick install** (no venv, no tests — for agents that manage their own environment):

```bash
git clone https://github.com/johtok/cortex-swarm.git && cd cortex-swarm && pip install -e ".[dev]"
```

---

## Why This Exists

| Problem | cortex-swarm's Answer |
|---------|-----------------------|
| "Which model do I use?" | Auto-routes by task complexity |
| "Opus is eating my quota" | Max 2 premium agents at once (semaphore) |
| "I need consensus" | 4-model council with blind peer review |
| "Bulk work is expensive" | GPT-5 mini swarms (multiplier = 0, FREE) |
| "My pipeline has steps" | DAG engine with compression + cascade |

---

## Highlights

### 🔒 Premium Concurrency Control

At most **2 premium agents** (Opus 4.6, multiplier ≥ 3) run simultaneously. Standard and cheap agents are unlimited. GPT-5 mini (multiplier = 0) is **completely free** — use as many as you want.

```
Premium tasks ──► Semaphore(2) ────► max 2 concurrent Opus calls
Standard tasks ─► (no gate) ───────► unlimited Sonnet/GPT-5.4
Free tasks ─────► (no gate) ───────► unlimited GPT-5 mini
```

### 🏛️ LLM Council

For high-stakes decisions, convene a council of 4 diverse models:

| Member | Model | Strength |
|--------|-------|----------|
| 🔬 Analyst | Gemini 2.5 Pro | Structured reasoning |
| ⚖️ Chairman | Claude Sonnet 4.6 | Balanced analysis (also synthesizes) |
| 📚 Generalist | GPT-5.4 | Broad knowledge, long context |
| 🏴 Contrarian | Grok Code Fast 1 | Different perspective, fast |

Three-stage process inspired by [karpathy/llm-council](https://github.com/karpathy/llm-council):

1. **Independent opinions** — All 4 models answer in parallel
2. **Anonymized peer review** — Models rank each other's responses blind (Response A/B/C/D)
3. **Chairman synthesis** — Sonnet combines insights weighted by peer rankings

### 🐝 Drone Swarm

Fan-out bulk work to unlimited GPT-5 mini agents (FREE!), then merge results with a single Sonnet synthesis pass.

> *"Summarize each of 50 Python files"* → 50 drone tasks + 1 synthesis = 51 LLM calls, **50 of which are free.**

### 🔀 Intelligent Task Routing

Auto-classifies task complexity and routes to the right model:

| Complexity | Role | Model | Multiplier | When |
|------------|------|-------|------------|------|
| Trivial | Drone | GPT-5 mini | 0 (FREE) | ≤500 tokens |
| Simple | Scout | Claude Haiku 4.5 | 0.33 | ≤2k tokens |
| Moderate | Worker | Claude Sonnet 4.6 | 1 | ≤10k tokens |
| Complex | Sage | GPT-5.4 | 1 | ≤50k tokens |
| Critical | Oracle | Claude Opus 4.6 | 3 (PREMIUM) | >50k tokens |

**Cascade escalation:** if a task fails, it auto-retries with the next tier up:
```
Drone → Scout → Worker → Sage → Oracle
```

### 📊 DAG Execution Engine

Execute multi-step task graphs with:
- Topological ordering (Kahn's algorithm)
- Context compression between nodes (extractive, key_points, summary)
- Cascade escalation on failure (auto-upgrade to higher tier)
- Dependency-aware skip (upstream failure → downstream skipped, never executed blind)

---

## Usage

### Execute a single task (auto-routed)
```bash
cortex-swarm run "Refactor the authentication module for better testability"
cortex-swarm run --role oracle "Review this security-critical code for vulnerabilities"
cortex-swarm run --role drone "Format this JSON file"
```

### Convene the LLM Council
```bash
cortex-swarm council "Should we use microservices or a monolith for this project?"
```

### Deploy a drone swarm
```bash
cortex-swarm swarm "Summarize each Python file in this directory" --count 20
```

### View available roles and models
```bash
cortex-swarm roles    # Show all 5 agent roles with descriptions
cortex-swarm status   # Show full model multiplier table
```

---

## Configuration

Configuration lives in `src/cortex_swarm/default_config.yaml` (shipped with the package). Override with `--config`:

```yaml
# Max concurrent premium agents (Opus 4.6, etc.)
max_premium_concurrent: 2

# Default model (Sonnet 4.6 — the workhorse)
default_model: claude-sonnet-4.6

# Council composition
council:
  members:
    - gemini-2.5-pro
    - claude-sonnet-4.6
    - gpt-5.4
    - grok-code-fast-1
  chairman: claude-sonnet-4.6

# Drone swarm settings
swarm:
  model: gpt-5-mini          # FREE!
  max_parallel: 20
  synthesis_model: claude-sonnet-4.6

# DAG execution
dag:
  max_retries: 2
  compression_level: 0.5     # 0 = no compression, 1 = maximum
  cascade_on_failure: true
```

---

## Architecture

```
cortex-swarm/
├── src/cortex_swarm/
│   ├── models/          # Model registry, multiplier table (24 models), tier system
│   ├── agents/          # Agent pool (semaphore), router, swarm, role definitions
│   ├── council/         # 3-stage LLM council with peer review + synthesis
│   ├── dag/             # DAG engine with topo sort, compression, cascade
│   ├── adapters/        # Copilot CLI, OpenAI-compat, and mock backends
│   ├── config.py        # YAML config loader with validation
│   └── cli.py           # Click CLI entry point
├── tests/               # 43 tests (unit + edge cases from 2 critic passes)
├── examples/demo.py     # End-to-end demo exercising all 8 subsystems
├── docs/                # Architecture guide + FAQ
├── AGENTS.md            # LLM agent instructions for working with this codebase
└── install.sh           # One-line installer
```

See [`docs/architecture.md`](docs/architecture.md) for the full module map, data flow diagrams, and concurrency model.

---

## Model Multiplier Reference

The system routes models based on Copilot's multiplier pricing:

| Model | Paid × | Free × | Tier | Role |
|-------|--------|--------|------|------|
| GPT-4.1 | 0 | 1 | 🟢 Free | — |
| GPT-4o | 0 | 1 | 🟢 Free | — |
| **GPT-5 mini** | **0** | 1 | 🟢 **Free** | **Drone** |
| Grok Code Fast 1 | 0.25 | — | 🟡 Cheap | Council |
| Claude Haiku 4.5 | 0.33 | 1 | 🟡 Cheap | Scout |
| GPT-5.4 mini | 0.33 | — | 🟡 Cheap | — |
| Gemini 2.5 Pro | 1 | — | 🔵 Standard | Council |
| **Claude Sonnet 4.6** | **1** | — | 🔵 **Standard** | **Worker (default)** |
| **GPT-5.4** | **1** | — | 🔵 **Standard** | **Sage** |
| GPT-5.1 | 1 | — | 🔵 Standard | — |
| GPT-5.2 | 1 | — | 🔵 Standard | — |
| **Claude Opus 4.6** | **3** | — | 🔴 **Premium** | **Oracle** |
| Claude Opus 4.6 (fast) | 30 | — | 🔴 Premium | — |

Bold = actively assigned to agent roles. Full table: `cortex-swarm status`

---

## Development

```bash
# Run tests (43 total — unit + edge cases)
pytest -v

# Type checking
mypy src/

# Lint
ruff check src/ tests/

# Run the full demo (no API keys needed — uses mock backend)
python examples/demo.py
```

---

## Documentation

| Doc | What's in it |
|-----|-------------|
| [`README.md`](README.md) | This file — overview, install, usage |
| [`AGENTS.md`](AGENTS.md) | **LLM instructions** — structure, conventions, anti-patterns, where-to-look |
| [`docs/architecture.md`](docs/architecture.md) | Architecture guide — module map, data flows, concurrency model, extension guide |
| [`docs/faq.md`](docs/faq.md) | FAQ — 25+ questions on models, pricing, routing, council, swarm, DAG, config |
| [`examples/demo.py`](examples/demo.py) | End-to-end demo exercising all 8 subsystems |

---

## Inspiration

- **[oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)** — Multi-agent orchestration, agent roles, background management, model fallback chains, install-and-go philosophy
- **[karpathy/llm-council](https://github.com/karpathy/llm-council)** — Multi-model council with anonymized peer review and chairman synthesis
- **[context-distillation-orchestrator](https://github.com/johtok/context-distillation-orchestrator)** — DAG execution, 3-tier model routing, context compression, cascade escalation

---

## License

MIT
