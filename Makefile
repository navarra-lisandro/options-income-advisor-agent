# =============================================================================
# options-income-advisor-agent — Local Development Pipeline
# =============================================================================
# This Makefile serves as the local CI/CD pipeline for this project.
# It mirrors the same principles as a remote pipeline (GitHub Actions,
# Jenkins) — a single source of truth for how the project is installed,
# run, tested, linted, and evaluated.
#
# Usage:
#   make install   install dependencies
#   make run       run the agent against the synthetic portfolio
#   make lint      check code quality
#   make test      run unit tests
#   make eval      run LangSmith evaluation experiment
#   make help      show this help message
# =============================================================================

.DEFAULT_GOAL := help
.PHONY: install run lint test eval help

# -----------------------------------------------------------------------------
# install — set up the project for the first time
# -----------------------------------------------------------------------------
install:
	@echo "Installing dependencies via Poetry..."
	poetry install
	@echo ""
	@echo "Next step: copy .env.example to .env and add your API keys."
	@echo "  cp .env.example .env"

# -----------------------------------------------------------------------------
# run — execute the agent against the synthetic portfolio
# -----------------------------------------------------------------------------
# TODO: add argparse support to agent/graph.py to allow per-ticker invocation
#       e.g. make run TICKER=JNJ
#       Until then, the agent runs against all positions in data/portfolio.json
# -----------------------------------------------------------------------------
run:
	@echo "Running options income advisor agent..."
	poetry run python agent/graph.py

# -----------------------------------------------------------------------------
# lint — check code quality with ruff
# -----------------------------------------------------------------------------
# ruff replaces flake8 + black + isort in a single tool.
# Configuration lives in pyproject.toml under [tool.ruff].
# -----------------------------------------------------------------------------
lint:
	@echo "Running ruff linter..."
	poetry run ruff check .
	@echo "Lint passed."

# -----------------------------------------------------------------------------
# test — run unit tests with pytest
# -----------------------------------------------------------------------------
test:
	@echo "Running unit tests..."
	poetry run pytest tests/ -v || [ $$? -eq 5 ]

# -----------------------------------------------------------------------------
# eval — run LangSmith evaluation experiment via SDK
# -----------------------------------------------------------------------------
# Requires LANGCHAIN_API_KEY and ANTHROPIC_API_KEY to be set in .env
# Uploads dataset to LangSmith and runs evaluate() against the agent.
# Results are visible in the LangSmith UI at smith.langchain.com
# -----------------------------------------------------------------------------
eval:
	@echo "Running LangSmith evaluation experiment..."
	poetry run python evals/evaluate.py

# -----------------------------------------------------------------------------
# help — list all available targets
# -----------------------------------------------------------------------------
help:
	@echo ""
	@echo "options-income-advisor-agent — available commands:"
	@echo ""
	@echo "  make install   Install project dependencies via Poetry"
	@echo "  make run       Run the agent against the synthetic portfolio"
	@echo "  make lint      Check code quality with ruff"
	@echo "  make test      Run unit tests with pytest"
	@echo "  make eval      Run LangSmith evaluation experiment via SDK"
	@echo "  make help      Show this help message"
	@echo ""
