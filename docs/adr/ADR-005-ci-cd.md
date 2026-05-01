# ADR-005 — CI/CD Strategy: GitHub Actions

**Date:** 2026-05-01
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

Before writing any agent code, I needed a safety net to ensure that
every change pushed to the repository is validated automatically. As
an SRE-principled project, "it works on my machine" is not an
acceptable standard, and every commit should be verifiable in a clean,
reproducible environment.

---

## Decision

We use **GitHub Actions** as the CI/CD pipeline, configured to run
on every pull request targeting `main` and on every push to `main`.
The pipeline runs two checks: `make lint` (ruff) and `make test`
(pytest). Main branch is protected with no direct pushes allowed, as all
changes go through a pull request.

---

## Rationale

**Branch protection before coding:**
Main branch protection was enabled before writing a single line of
agent code. This ensures the repo is always in a known good state
and every change has an intentional review step (even for a solo
project).

**GitHub Actions over alternatives:**
GitHub Actions was the natural choice given the repo is already on
GitHub. No additional tooling, accounts, or configuration required.
The workflow file lives in `.github/workflows/ci.yml` — infrastructure
as code, version controlled alongside the project.

**Makefile as the single source of truth:**
The CI pipeline calls `make lint` and `make test` — the same commands
a developer runs locally. This eliminates the "works locally but
fails in CI" problem. The Makefile is the contract between local
development and the CI environment.

**Caching for speed:**
The workflow caches the Poetry virtual environment by `poetry.lock`
hash. If dependencies haven't changed, the install step is skipped (
faster feedback loops on every PR).

**Python version parity:**
The workflow reads `.python-version` via `actions/setup-python` with
`python-version-file: .python-version`. The same pyenv pin used
locally is used in CI — one source of truth for the Python version.

---

## Workflow Design

```yaml
Triggers:
  push:         branches: [main]
  pull_request: branches: [main]

Steps:
  1. Checkout repository
  2. Set up Python (reads .python-version)
  3. Install Poetry
  4. Cache Poetry virtualenv (keyed by poetry.lock hash)
  5. Install dependencies (poetry install)
  6. Run linter (make lint)
  7. Run tests (make test)
```

---

## Challenges Encountered

Two issues surfaced during CI setup and are documented as learning
moments:

**Issue 1 — Poetry package mode:**
Poetry 2.x defaulted to package mode, causing CI to fail when trying
to install the project as a package. Fixed by setting
`package-mode = false` in `pyproject.toml`. See `FRICTION_LOG.md`.

**Issue 2 — pytest exit code 5:**
pytest returns exit code 5 when no tests are collected. Make
interprets this as a failure. Fixed by handling exit code 5
explicitly in the Makefile test target until real tests are written.

---

## Branch Protection Settings

```
Branch name pattern:     main
Require pull request:    ✅
Required approvals:      0 (solo project — PR required, approval optional)
Block force pushes:      ✅
```

Required approvals set to 0 for a solo project, since the value of branch
protection here is the CI gate and the PR audit trail, not peer review needed.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|---|---|
| No CI | Unacceptable — no safety net for regressions |
| Pre-commit hooks only | Local only — doesn't validate in clean environment |

---

## Consequences

- **Positive:** Every merge to main has passed lint and test in a
  clean environment. Green checkmarks on every commit in the history.
- **Positive:** The Makefile serves as both local and CI entrypoint —
  one interface for all environments.
- **Positive:** New contributors get immediate feedback on PRs without
  needing to run anything locally first.
- **Neutral:** CI does not run the agent or LangSmith evals — those
  require API keys that should not be in CI. Eval runs are manual.
- **Watch:** As the test suite grows, consider adding pytest coverage
  reporting and a coverage threshold gate.

---

## References

- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [snok/install-poetry action](https://github.com/snok/install-poetry)
- [actions/setup-python](https://github.com/actions/setup-python)
- See also: `FRICTION_LOG.md` — Poetry package mode issue surfaced
  during CI setup
