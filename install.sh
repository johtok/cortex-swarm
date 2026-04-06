#!/usr/bin/env bash
# cortex-swarm installer
# Usage: curl -sSL https://raw.githubusercontent.com/johtok/cortex-swarm/master/install.sh | bash
# Or:    bash install.sh [--no-venv] [--no-test]
set -euo pipefail

REPO="https://github.com/johtok/cortex-swarm.git"
DIR="cortex-swarm"
MIN_PYTHON="3.11"

# ─── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[cortex-swarm]${NC} $*"; }
ok()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
fail()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ─── Flags ────────────────────────────────────────────────────────────
USE_VENV=true
RUN_TESTS=true
for arg in "$@"; do
  case "$arg" in
    --no-venv)  USE_VENV=false ;;
    --no-test)  RUN_TESTS=false ;;
    --help|-h)
      echo "Usage: install.sh [--no-venv] [--no-test]"
      echo "  --no-venv   Install into current Python environment"
      echo "  --no-test   Skip test suite after install"
      exit 0 ;;
  esac
done

# ─── Check Python ─────────────────────────────────────────────────────
info "Checking Python version..."
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
    if [ -n "$ver" ]; then
      major=${ver%%.*}
      minor=${ver#*.}
      if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
        PYTHON="$cmd"
        break
      fi
    fi
  fi
done
[ -z "$PYTHON" ] && fail "Python >= $MIN_PYTHON required. Found: ${ver:-none}"
ok "Python $ver ($PYTHON)"

# ─── Clone or use existing ────────────────────────────────────────────
if [ -d "$DIR/.git" ]; then
  info "Directory '$DIR' exists, pulling latest..."
  cd "$DIR"
  git pull --quiet
elif [ -f "pyproject.toml" ] && grep -q "cortex.swarm" pyproject.toml 2>/dev/null; then
  info "Already inside cortex-swarm repo"
else
  info "Cloning $REPO..."
  git clone --quiet "$REPO" "$DIR"
  cd "$DIR"
fi
ok "Source ready"

# ─── Virtual environment ──────────────────────────────────────────────
if $USE_VENV; then
  if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    $PYTHON -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  ok "Virtual environment active (.venv)"
fi

# ─── Install ──────────────────────────────────────────────────────────
info "Installing cortex-swarm + dev dependencies..."
pip install --quiet -e ".[dev]"
ok "Installed $(pip show cortex-swarm 2>/dev/null | grep '^Version' | cut -d' ' -f2)"

# ─── Tests ────────────────────────────────────────────────────────────
if $RUN_TESTS; then
  info "Running test suite..."
  if pytest --quiet --tb=short; then
    ok "All tests passed"
  else
    warn "Some tests failed — install succeeded but check output above"
  fi
fi

# ─── Done ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}┌──────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│  cortex-swarm installed successfully!        │${NC}"
echo -e "${GREEN}│                                              │${NC}"
echo -e "${GREEN}│  Quick start:                                │${NC}"
echo -e "${GREEN}│    source .venv/bin/activate                 │${NC}"
echo -e "${GREEN}│    cortex-swarm --help                       │${NC}"
echo -e "${GREEN}│    cortex-swarm roles                        │${NC}"
echo -e "${GREEN}│    cortex-swarm status                       │${NC}"
echo -e "${GREEN}│    python examples/demo.py                   │${NC}"
echo -e "${GREEN}│                                              │${NC}"
echo -e "${GREEN}│  Docs: docs/architecture.md, docs/faq.md    │${NC}"
echo -e "${GREEN}│  LLM instructions: AGENTS.md                │${NC}"
echo -e "${GREEN}└──────────────────────────────────────────────┘${NC}"
