# 🧠 cortex-swarm

**Multi-agent orchestrator with premium concurrency control, LLM council, and drone swarm — Copilot Multiplier-aware.**

> *"One brain is good. A cortex of many is better."*

cortex-swarm coordinates multiple AI agents with intelligent routing, enforcing budget constraints through Copilot's Model Multiplier system. It draws on ideas from [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent), [llm-council](https://github.com/karpathy/llm-council), and [context-distillation-orchestrator](https://github.com/johtok/context-distillation-orchestrator).

## ✨ Key Features

### 🔒 Premium Concurrency Control
At most **2 premium agents** (Opus 4.6, multiplier ≥ 3) run simultaneously. Standard and cheap agents are unlimited. GPT-5 mini (multiplier = 0) is **completely free** — use as many as you want.

### 🏛️ LLM Council
For high-stakes decisions, convene a council of 4 diverse models:
- **Gemini 2.5 Pro** — Structured reasoning
- **Claude Sonnet 4.6** — Balanced analysis
- **GPT-5.4** — Broad knowledge
- **Grok Code Fast 1** — Contrarian perspective

Three-stage process inspired by [karpathy/llm-council](https://github.com/karpathy/llm-council):
1. **Independent opinions** — All models answer in parallel
2. **Anonymized peer review** — Models rank each other's responses blind
3. **Chairman synthesis** — Best answer synthesized from all perspectives

### 🐝 Drone Swarm
Fan-out bulk work to unlimited GPT-5 mini agents (FREE!), then merge results with Sonnet 4.6 synthesis. Perfect for batch file analysis, mass linting, parallel classification.

### 🔀 Intelligent Task Routing
Auto-classifies task complexity and routes to the right model:
| Complexity | Agent | Model | Multiplier |
|------------|-------|-------|------------|
| Trivial | Drone | GPT-5 mini | 0 (FREE) |
| Simple | Scout | Claude Haiku 4.5 | 0.33 |
| Moderate | Worker | Claude Sonnet 4.6 | 1 |
| Complex | Sage | GPT-5.4 | 1 |
| Critical | Oracle | Claude Opus 4.6 | 3 (PREMIUM) |

### 📊 DAG Execution Engine
Execute multi-step task graphs with:
- Topological ordering
- Context compression between nodes (extractive, key points, summary)
- Cascade escalation on failure (auto-upgrade to higher tier)
- Per-node tool confinement

## 🚀 Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/cortex-swarm.git
cd cortex-swarm

# Install with uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"
```

## 📖 Usage

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

### View available roles
```bash
cortex-swarm roles
```

### View model multiplier table
```bash
cortex-swarm status
```

## ⚙️ Configuration

Configuration lives in `configs/default.yaml`. Override with `--config`:

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
```

## 🏗️ Architecture

```
cortex-swarm/
├── src/cortex_swarm/
│   ├── models/          # Model registry, multiplier table, tier system
│   ├── agents/          # Agent pool, router, swarm, role definitions
│   ├── council/         # 3-stage LLM council with peer review
│   ├── dag/             # DAG execution engine with compression
│   └── adapters/        # Copilot CLI and OpenAI-compatible backends
├── configs/             # YAML configuration files
└── tests/               # Test suite
```

## 📐 Model Multiplier Reference

| Model | Paid Multiplier | Free Multiplier | Tier |
|-------|----------------|-----------------|------|
| GPT-4.1 | 0 | 1 | 🟢 Free |
| GPT-4o | 0 | 1 | 🟢 Free |
| GPT-5 mini | 0 | 1 | 🟢 Free |
| Claude Haiku 4.5 | 0.33 | 1 | 🟡 Cheap |
| Grok Code Fast 1 | 0.25 | — | 🟡 Cheap |
| GPT-5.4 mini | 0.33 | — | 🟡 Cheap |
| Claude Sonnet 4.6 | 1 | — | 🔵 Standard |
| GPT-5.4 | 1 | — | 🔵 Standard |
| Gemini 2.5 Pro | 1 | — | 🔵 Standard |
| Claude Opus 4.6 | 3 | — | 🔴 Premium |
| Claude Opus 4.6 (fast) | 30 | — | 🔴 Premium |

## 🧪 Development

```bash
# Run tests
pytest

# Type checking
mypy src/

# Lint
ruff check src/ tests/
```

## 📚 Inspiration

- **[oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)** — Multi-agent orchestration, agent roles, background management, model fallback chains
- **[karpathy/llm-council](https://github.com/karpathy/llm-council)** — Multi-model council with anonymized peer review and chairman synthesis
- **[context-distillation-orchestrator](https://github.com/johtok/context-distillation-orchestrator)** — DAG execution, 3-tier model routing, context compression, cascade escalation

## 📄 License

MIT
