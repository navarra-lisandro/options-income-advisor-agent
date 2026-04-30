# ADR-001 — Python Version Selection

**Date:** 2026-04-30
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

This project requires a Python environment compatible with LangGraph,
LangChain, LangSmith, and the Anthropic SDK. Python version selection
has a direct impact on dependency resolution, runtime stability, and
developer reproducibility across machines.

The local development environment had Python 3.13.3 installed as the
system default — the current stable release at the time of this project.

---

## Decision

We pin the project to **Python 3.11.9**, managed via `pyenv` with a
`.python-version` file committed to the repository root.

---

## Rationale

- **LangGraph/LangChain compatibility:** The LangChain ecosystem's
  dependency tree is not yet fully validated against Python 3.13.
  Attempting to install `langchain-core` on 3.13 produces silent
  compatibility failures that are difficult to diagnose without
  prior experience with the ecosystem.

- **3.11 is the battle-tested baseline:** Python 3.11 is the version
  most LangGraph examples, tutorials, and documentation are built and
  tested against. It is the lowest-risk choice for a new project in
  this ecosystem.

- **pyenv local for isolation:** Using `pyenv local 3.11.9` creates a
  `.python-version` file scoped to this project directory only. This
  does not affect the system Python or any other project on the same
  machine — a clean, non-destructive approach consistent with good
  local development hygiene.

- **Committed to version control:** The `.python-version` file is
  committed to the repository so that any contributor who clones this
  repo and has pyenv installed will automatically use the correct
  Python version. This is configuration as code.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|---|---|
| Python 3.13.3 (system default) | Not yet fully compatible with LangChain dependency tree |
| Python 3.12.x | Viable, but 3.11 has a longer track record with this ecosystem |
| Docker-based Python | Overkill for a local development and evaluation project |

---

## Consequences

- **Positive:** Dependency resolution is stable and predictable.
  No compatibility surprises during `poetry install`.
- **Positive:** Any contributor with pyenv installed gets the correct
  version automatically via `.python-version`.
- **Neutral:** Developers without pyenv installed will need to install
  it before contributing — this is documented in the README.
- **Watch:** Python 3.13 compatibility in the LangChain ecosystem is
  improving. This decision should be revisited when LangGraph and
  langchain-core explicitly validate 3.13 support.

---

## References

- [pyenv documentation](https://github.com/pyenv/pyenv)
- [LangGraph installation docs](https://langchain-ai.github.io/langgraph/)
- See also: `FRICTION_LOG.md` Friction #1 — Python version not
  documented in LangGraph quickstart
