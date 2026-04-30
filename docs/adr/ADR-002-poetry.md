# ADR-002 — Package Management: Poetry over pip

**Date:** 2026-04-30
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

This project requires a repeatable, reproducible Python dependency
management strategy. The choice of package manager affects onboarding
speed, dependency conflict resolution, environment isolation, and the
overall developer experience for anyone who clones and runs this project.

The two most common options in the Python ecosystem are bare `pip` with
a `requirements.txt` file, and `Poetry` with a `pyproject.toml` and
`poetry.lock` file.

---

## Decision

We use **Poetry 2.x** for all dependency management, with dependencies
declared in `pyproject.toml` and locked versions committed in
`poetry.lock`.

---

## Rationale

- **Lock file guarantees reproducibility:** `poetry.lock` pins every
  dependency — including transitive ones — to exact versions. Anyone
  running `poetry install` gets an identical environment regardless of
  when or where they run it. A `requirements.txt` file only pins what
  you explicitly declare, leaving transitive dependencies to float.

- **Automatic dependency conflict resolution:** Poetry detects and
  resolves version conflicts at install time rather than at runtime.
  This surfaces incompatibilities early and clearly rather than
  producing cryptic import errors later.

- **Clean separation of dev and prod dependencies:** Poetry natively
  supports dependency groups — core runtime dependencies live in
  `[tool.poetry.dependencies]` while development tools (pytest, ruff,
  ipykernel) live in `[tool.poetry.group.dev.dependencies]`. This
  keeps production installs lean and makes the dependency intent
  explicit.

- **pyproject.toml is the modern standard:** PEP 517 and PEP 518
  establish `pyproject.toml` as the standard for Python project
  configuration. It consolidates package metadata, dependencies, and
  tool configuration (ruff, pytest) in a single file, replacing the
  fragmented `setup.py` + `requirements.txt` + `setup.cfg` pattern.

- **Virtual environment management included:** `poetry shell` activates
  a project-scoped virtual environment automatically. No manual
  `python -m venv` or `source activate` steps required.

---

## Development Tools Included

| Tool | Group | Purpose |
|---|---|---|
| `pytest` | dev | Test runner for unit tests |
| `ruff` | dev | Fast Python linter and formatter — replaces flake8 + black in a single tool |
| `ipykernel` | dev | Jupyter kernel for exploratory prototyping within the Poetry venv |

`ruff` was chosen over the traditional `flake8` + `black` combination
because it provides identical functionality in a single dependency,
runs significantly faster, and requires only one configuration block
in `pyproject.toml`.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|---|---|
| `pip` + `requirements.txt` | No lock file, manual conflict resolution, no dev/prod separation |
| `pip` + `pip-tools` | Adds lock file support but still requires manual toolchain assembly |
| `conda` | Overkill for a pure Python project with no scientific computing dependencies |
| `pipenv` | Superseded by Poetry in most modern Python workflows |

---

## Consequences

- **Positive:** Any contributor running `poetry install` gets an exact
  replica of the development environment with no guesswork.
- **Positive:** Dependency conflicts are caught at install time, not
  at runtime.
- **Positive:** Single `pyproject.toml` consolidates all project
  configuration.
- **Neutral:** Contributors unfamiliar with Poetry need a one-time
  install (`curl -sSL https://install.python-poetry.org | python3 -`).
  This is documented in the README.
- **Watch:** Poetry 2.x introduced breaking changes in how Python
  version constraints are interpreted. See `FRICTION_LOG.md` Friction
  #2 for a specific incompatibility encountered during setup.

---

## References

- [Poetry documentation](https://python-poetry.org/docs/)
- [PEP 517 — Build system interface](https://peps.python.org/pep-0517/)
- [PEP 518 — Build system requirements](https://peps.python.org/pep-0518/)
- [ruff documentation](https://docs.astral.sh/ruff/)
- See also: `FRICTION_LOG.md` Friction #2 — Poetry 2.x + langchain-core
  constraint conflict
