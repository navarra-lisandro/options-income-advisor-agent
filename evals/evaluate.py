"""
evals/evaluate.py — LangSmith SDK Evaluation
==============================================
Runs an offline evaluation experiment against the LangSmith dataset
created by evals/dataset.py. Uses two complementary evaluation approaches:

  1. Structured field matching
     Validates screening logic deterministically. Checks that
     aristocrat_screen, earnings_screen, and dividend_screen match
     expected PASS/CAUTION/FAIL values exactly. Binary — right or wrong.

  2. LLM-as-a-judge
     Validates reasoning quality using Claude as the scoring model.
     Checks whether the final recommendation correctly identifies the
     key risk, explains it accurately, and provides actionable guidance.
     Scored 0-10 with explicit criteria per example.

Run independently:
    poetry run python -m evals.evaluate

Or via Makefile:
    make eval

Prerequisites:
    make dataset must be run first to create the LangSmith dataset.

Offline vs Online Evaluation:
    This module implements OFFLINE evaluation — the agent is evaluated
    against a fixed dataset of known inputs and expected outputs before
    deployment. This is analogous to QA pre-production testing in
    traditional software development. Online evaluation (scoring
    production traces as they arrive) is a future consideration.

LangSmith Reference Docs:
    How to evaluate a LangGraph graph:
        https://docs.smith.langchain.com/evaluation/how_to_guides/langgraph
    How to define a target function:
        https://docs.smith.langchain.com/evaluation/how_to_guides/define_target
    LLM-as-a-judge evaluator:
        https://docs.smith.langchain.com/evaluation/how_to_guides/llm_as_judge
    Python SDK evaluate() reference:
        https://docs.smith.langchain.com/reference/python/evaluation

Design Decisions:
    - run_agent() wraps graph.invoke() as a plain function per LangSmith
      recommended pattern. The compiled graph is built once outside the
      function to avoid rebuilding on every evaluation example.
    - Two evaluators are used together because structured field matching
      alone cannot validate reasoning quality, and LLM-as-a-judge alone
      cannot catch incorrect screening logic.
    - experiment_prefix is set to allow comparison across runs in the
      LangSmith UI — each run is versioned automatically.
    See ADR-007 for full evaluation strategy rationale.
"""

import json
from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate
from langsmith.schemas import Run, Example
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph import build_graph
from evals.dataset import DATASET_NAME

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_PREFIX = "options-income-advisor"
LLM_JUDGE_MODEL = "claude-sonnet-4-5"

# ---------------------------------------------------------------------------
# Build graph once — reused across all evaluation examples
# Avoids rebuilding the graph on every evaluate() call
# ---------------------------------------------------------------------------
graph = build_graph()


# ---------------------------------------------------------------------------
# Target function — wraps graph.invoke() for LangSmith evaluate()
# Receives a single position dict from the dataset example inputs
# Returns the agent output as a dict for evaluators to score
# ---------------------------------------------------------------------------
def run_agent(inputs: dict) -> dict:
    """
    Target function passed to LangSmith evaluate().

    Receives a single position dict from the dataset example,
    injects it into agent state via the load_portfolio bypass,
    and returns the full agent output.

    This is the recommended LangSmith pattern for LangGraph agents:
    https://docs.smith.langchain.com/evaluation/how_to_guides/define_target

    Args:
        inputs: Single position dict from dataset example inputs.
                Mirrors the Position TypedDict in agent/state.py.

    Returns:
        dict containing screenings, final_report, and order_summary.
    """
    result = graph.invoke({
        "positions": [inputs],
        "screenings": [],
    })

    # Extract screening result for this specific ticker
    ticker = inputs.get("ticker", "")
    screening = next(
        (s for s in result.get("screenings", []) if s["ticker"] == ticker),
        {}
    )

    # Debug Line — used for investigation on local development
    print(f"DEBUG {ticker} screening: {screening}")

    return {
        "ticker": ticker,
        "aristocrat_screen": screening.get("aristocrat_screen", ""),
        "earnings_screen": screening.get("earnings_screen", ""),
        "dividend_screen": screening.get("dividend_screen", ""),
        "final_report": result.get("final_report", ""),
        "order_summary": result.get("order_summary", ""),
    }


# ---------------------------------------------------------------------------
# Evaluator 1 — Structured field matching
# Validates screening logic deterministically
# Checks PASS/CAUTION/FAIL values match expected outputs exactly
# ---------------------------------------------------------------------------
def evaluate_screening_logic(run: Run, example: Example) -> dict:
    """
    Structured field matching evaluator.

    Compares actual screening results against expected values from
    the dataset. Each screen is checked independently — a single
    mismatch fails the entire screening logic score.

    Returns:
        dict with key "screening_logic" and score 0 or 1.
    """
    actual = run.outputs or {}
    expected = example.outputs or {}

    checks = [
        actual.get("aristocrat_screen") == expected.get("aristocrat_screen"),
        actual.get("earnings_screen") == expected.get("earnings_screen"),
        actual.get("dividend_screen") == expected.get("dividend_screen"),
    ]

    score = 1 if all(checks) else 0

    # Build detailed comment for LangSmith UI
    comment_lines = []
    screens = ["aristocrat_screen", "earnings_screen", "dividend_screen"]
    for screen in screens:
        actual_val = actual.get(screen, "MISSING")
        expected_val = expected.get(screen, "MISSING")
        match = "[PASS]" if actual_val == expected_val else "[FAIL]"
        comment_lines.append(
            f"{match} {screen}: got {actual_val}, expected {expected_val}"
        )

    return {
        "key": "screening_logic",
        "score": score,
        "comment": "\n".join(comment_lines),
    }


# ---------------------------------------------------------------------------
# Evaluator 2 — LLM-as-a-judge
# Validates reasoning quality using Claude as the scoring model
# Scores 0-10 based on explicit criteria from the dataset example
# ---------------------------------------------------------------------------
def evaluate_reasoning_quality(run: Run, example: Example) -> dict:
    """
    LLM-as-a-judge evaluator.

    Uses Claude to score the agent's final recommendation against
    the LLM judge criteria defined in the dataset example outputs.
    Scores 0-10 with explicit reasoning.

    Returns:
        dict with key "reasoning_quality" and score 0-10 normalized to 0-1.
    """
    actual_report = (run.outputs or {}).get("final_report", "")
    criteria = (example.outputs or {}).get("llm_judge_criteria", "")
    ticker = (example.inputs or {}).get("ticker", "unknown")

    if not actual_report or not criteria:
        return {
            "key": "reasoning_quality",
            "score": 0,
            "comment": "Missing actual report or evaluation criteria.",
        }

    judge_llm = ChatAnthropic(model=LLM_JUDGE_MODEL)

    system_prompt = """You are an expert evaluator assessing the quality of
options trading recommendations generated by an AI agent.

You will be given:
1. An actual recommendation generated by the agent
2. Evaluation criteria describing what a good recommendation should include

Score the recommendation from 0-10 where:
  0-3:  Missing key information or factually incorrect
  4-6:  Partially correct but missing important details
  7-9:  Mostly correct with minor gaps
  10:   Fully correct, complete, and actionable

Respond ONLY with a JSON object in this exact format:
{
  "score": <integer 0-10>,
  "reasoning": "<one sentence explanation>"
}"""

    user_message = f"""Ticker: {ticker}

Evaluation Criteria:
{criteria}

Actual Agent Recommendation:
{actual_report}

Score this recommendation from 0-10."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    response = judge_llm.invoke(messages)

    # Parse JSON response
    try:
        # Strip markdown code blocks if present
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        raw_score = int(result.get("score", 0))
        reasoning = result.get("reasoning", "No reasoning provided.")
        normalized_score = raw_score / 10.0
    except (json.JSONDecodeError, ValueError, KeyError):
        raw_score = 0
        reasoning = "Failed to parse judge response."
        normalized_score = 0.0

    return {
        "key": "reasoning_quality",
        "score": normalized_score,
        "comment": f"Raw score: {raw_score}/10 — {reasoning}",
    }


# ---------------------------------------------------------------------------
# Run evaluation experiment
# ---------------------------------------------------------------------------
def run_evaluation() -> None:
    """
    Runs the LangSmith offline evaluation experiment.

    Calls evaluate() with:
      - run_agent as the target function
      - DATASET_NAME as the dataset to evaluate against
      - Two evaluators: structured field matching + LLM-as-a-judge

    Results are pushed to LangSmith automatically and visible in the
    Datasets & Experiments section of the UI at smith.langchain.com.
    """
    client = Client()

    # Verify dataset exists before running
    if not client.has_dataset(dataset_name=DATASET_NAME):
        print(f"[ERROR] Dataset '{DATASET_NAME}' not found.")
        print("Run 'make dataset' first to create the evaluation dataset.")
        return

    print(f"Running evaluation against dataset: {DATASET_NAME}")
    print(f"Experiment prefix: {EXPERIMENT_PREFIX}")
    print("This will make API calls to Claude for each example...")
    print("")

    results = evaluate(
        run_agent,
        data=DATASET_NAME,
        evaluators=[
            evaluate_screening_logic,
            evaluate_reasoning_quality,
        ],
        experiment_prefix=EXPERIMENT_PREFIX,
        client=client,
        metadata={
            "agent_version": "1.0",
            "eval_strategy": "structured_field_matching + llm_as_judge",
            "dataset_version": "v1",
        },
    )

    print("")
    print("Evaluation complete.")
    print(f"View results at: https://smith.langchain.com")
    print("")

    # Print summary to terminal
    print("=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)

    try:
        results_df = results.to_pandas()
        for col in results_df.columns:
            if "screening_logic" in col or "reasoning_quality" in col:
                mean_score = results_df[col].mean()
                print(f"  {col}: {mean_score:.2f}")
    except Exception:
        print("  Results available in LangSmith UI.")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point — run via: make eval
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_evaluation()
