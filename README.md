# options-income-advisor-agent

A LangGraph agent that analyzes a synthetic equity portfolio and recommends
covered-call and cash-secured-put opportunities for income generation.

Built as part of a LangSmith/LangGraph evaluation exercise using Anthropic's
Claude as the underlying LLM.

---

## Project Structure

```
options-income-advisor-agent/
├── .env.example              # template for required env vars
├── .python-version           # pyenv pin (3.11.9)
├── pyproject.toml            # poetry config and dependencies
├── poetry.lock               # locked dependency versions
├── README.md                 # setup + architecture docs
├── Makefile                  # common commands (run, lint, test, eval)
├── FRICTION_LOG.md           # developer experience notes for LangChain team
├── agent/
│   ├── __init__.py
│   ├── graph.py              # LangGraph state machine
│   ├── nodes.py              # individual node functions
│   ├── state.py              # AgentState definition
│   └── tools.py              # tool definitions
├── data/
│   └── portfolio.json        # synthetic portfolio dataset
├── evals/
│   ├── dataset.py            # LangSmith dataset creation
│   └── evaluate.py           # SDK-based evaluate() run
├── notebooks/
│   └── exploration.ipynb     # scratch work and node prototyping
└── docs/
    └── adr/
        ├── ADR-001-python-version.md
        ├── ADR-002-poetry.md
        ├── ADR-003-anthropic.md
        └── ADR-004-agent-domain.md
```

---

## Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) — Python version management
- [Poetry](https://python-poetry.org/) 2.x — dependency management
- Python 3.11.9 (pinned via `.python-version`)
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)
- LangSmith API key — [smith.langchain.com](https://smith.langchain.com)

---

## Setup

**1. Clone the repo using SSH:**

```bash
git clone git@github.com:navarra-lisandro/options-income-advisor-agent.git
cd options-income-advisor-agent
```

**2. Confirm Python version:**

```bash
python --version  # should show 3.11.9
# If not: pyenv install 3.11.9 && pyenv local 3.11.9
```

**3. Install dependencies:**

```bash
poetry install
```

**4. Configure environment variables:**

```bash
cp .env.example .env
# Edit .env and add your API keys
```

**5. Activate the virtual environment:**

```bash
poetry shell
```

---

## Environment Variables

| Variable              | Description                                          |
|-----------------------|------------------------------------------------------|
| `ANTHROPIC_API_KEY`   | Anthropic API key from console.anthropic.com         |
| `LANGCHAIN_API_KEY`   | LangSmith API key from smith.langchain.com           |
| `LANGCHAIN_TRACING_V2`| Set to `true` to enable LangSmith tracing            |
| `LANGCHAIN_PROJECT`   | LangSmith project name for this agent                |

---

## Development Tools

| Tool         | Purpose                                                              |
|--------------|----------------------------------------------------------------------|
| `pytest`     | Test runner for unit tests                                           |
| `ruff`       | Fast Python linter and formatter (replaces flake8 + black)          |
| `ipykernel`  | Jupyter kernel for exploratory prototyping within the Poetry venv   |

---

## Architecture Decision Records

See [`docs/adr/`](docs/adr/) for documented design decisions covering
Python version selection, package management, LLM provider choice,
and agent domain rationale.

---

## Friction Log

See [`FRICTION_LOG.md`](FRICTION_LOG.md) for developer experience notes
captured during setup and development — filed as candid feedback for the
LangChain team.
