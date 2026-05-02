"""
evals/dataset.py — LangSmith Evaluation Dataset
=================================================
Creates and uploads the evaluation dataset to LangSmith.
This module is intentionally separate from evals/evaluate.py
following the shift-left principle — dataset creation is a
discrete, independently failable step in the eval pipeline.

Run independently:
    poetry run python -m evals.dataset

Or via Makefile:
    make dataset

Design Decisions:
  - Dataset is versioned (v1) to allow future evolution
    without losing historical comparison data in LangSmith.
  - Idempotent — skips creation if dataset already exists.
    Critical for CI pipelines where this runs repeatedly.
  - 5 examples chosen to cover the full outcome spectrum:
      MCD  → RECOMMEND        (clean pass, all screens)
      JNJ  → PROCEED CAUTION  (dividend overlap)
      KO   → PROCEED CAUTION  (dividend overlap, more urgent)
      NVDA → AVOID            (not aristocrat + earnings CAUTION)
      TSLA → AVOID            (not aristocrat + earnings FAIL)
  - Synthetic variants (same ticker, modified dates) documented
    as a future iteration — not required for this scope.
  - Each example includes both structured field expectations
    (deterministic screen results) and LLM-as-a-judge criteria
    (nuanced reasoning quality).

LangSmith Reference Docs:
  Client SDK:
    https://docs.smith.langchain.com/reference/python/client
  Dataset creation:
    https://docs.smith.langchain.com/evaluation/how_to_guides/manage_datasets_programmatically
  Example structure:
    https://docs.smith.langchain.com/evaluation/concepts#dataset
"""

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

# ---------------------------------------------------------------------------
# Dataset configuration
# Versioned to allow future evolution without losing historical data
# ---------------------------------------------------------------------------
DATASET_NAME = "options-income-advisor-eval-v1"
DATASET_DESCRIPTION = (
    "Evaluation dataset for the Options Income Advisor Agent. "
    "Tests covered call screening logic for the Income Wheel strategy "
    "in a 401k/Roth tax-advantaged account. "
    "5 examples covering the full RECOMMEND/CAUTION/AVOID spectrum."
)


# ---------------------------------------------------------------------------
# Evaluation examples
# Each example contains:
#   inputs  → single position data (mirrors Position TypedDict)
#   outputs → expected screening results + LLM-as-a-judge criteria
# ---------------------------------------------------------------------------
EXAMPLES = [
    # -----------------------------------------------------------------------
    # Example 1 — MCD (McDonald's)
    # Expected: RECOMMEND — clean pass on all three screens
    # -----------------------------------------------------------------------
    {
        "inputs": {
            "ticker": "MCD",
            "shares": 100,
            "current_price": 295.50,
            "dividend_yield_pct": 2.3,
            "is_dividend_aristocrat": True,
            "next_earnings_date": "2026-08-01",
            "next_ex_dividend_date": "2026-06-15",
        },
        "outputs": {
            "aristocrat_screen": "PASS",
            "earnings_screen": "PASS",
            "dividend_screen": "PASS",
            "overall_recommendation": "RECOMMEND",
            "llm_judge_criteria": (
                "The agent should identify MCD as a dividend aristocrat, "
                "confirm that earnings on August 1 are safely outside the "
                "30-day expiry window, confirm the ex-dividend date on "
                "June 15 is outside the expiry window, and recommend a "
                "covered call without caveats. The recommendation should "
                "include an estimated annual income yield combining "
                "dividend yield and covered call premium."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Example 2 — JNJ (Johnson & Johnson)
    # Expected: PROCEED WITH CAUTION — dividend overlap within expiry window
    # -----------------------------------------------------------------------
    {
        "inputs": {
            "ticker": "JNJ",
            "shares": 100,
            "current_price": 162.75,
            "dividend_yield_pct": 3.1,
            "is_dividend_aristocrat": True,
            "next_earnings_date": "2026-07-15",
            "next_ex_dividend_date": "2026-05-23",
        },
        "outputs": {
            "aristocrat_screen": "PASS",
            "earnings_screen": "PASS",
            "dividend_screen": "CAUTION",
            "overall_recommendation": "PROCEED WITH CAUTION",
            "llm_judge_criteria": (
                "The agent should identify JNJ as a dividend aristocrat, "
                "confirm earnings on July 15 are safely outside the window, "
                "flag the May 23 ex-dividend date as falling within the "
                "30-day expiry window creating early assignment risk, and "
                "recommend OTM strike selection or waiting until after the "
                "ex-dividend date. Should include estimated annual income "
                "yield and specific strike guidance."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Example 3 — KO (Coca-Cola)
    # Expected: PROCEED WITH CAUTION — dividend overlap, more urgent than JNJ
    # -----------------------------------------------------------------------
    {
        "inputs": {
            "ticker": "KO",
            "shares": 200,
            "current_price": 63.45,
            "dividend_yield_pct": 3.4,
            "is_dividend_aristocrat": True,
            "next_earnings_date": "2026-06-25",
            "next_ex_dividend_date": "2026-05-14",
        },
        "outputs": {
            "aristocrat_screen": "PASS",
            "earnings_screen": "PASS",
            "dividend_screen": "CAUTION",
            "overall_recommendation": "PROCEED WITH CAUTION",
            "llm_judge_criteria": (
                "The agent should identify KO as a dividend aristocrat, "
                "confirm earnings on June 25 are outside the window, "
                "flag the May 14 ex-dividend date as more urgent than JNJ "
                "since it is only 13 days away, and recommend either "
                "waiting until after May 14 or selling with strikes at "
                "least 3-4% OTM to reduce early assignment risk. "
                "Should note the 200-share position allows selling "
                "2 contracts and suggest a split strategy."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Example 4 — NVDA (NVIDIA)
    # Expected: AVOID — not a dividend aristocrat + earnings CAUTION
    # -----------------------------------------------------------------------
    {
        "inputs": {
            "ticker": "NVDA",
            "shares": 50,
            "current_price": 875.50,
            "dividend_yield_pct": 0.03,
            "is_dividend_aristocrat": False,
            "next_earnings_date": "2026-05-28",
            "next_ex_dividend_date": None,
        },
        "outputs": {
            "aristocrat_screen": "FAIL",
            "earnings_screen": "CAUTION",
            "dividend_screen": "FAIL",
            "overall_recommendation": "AVOID",
            "llm_judge_criteria": (
                "The agent should identify NVDA as not a dividend aristocrat, "
                "flag earnings on May 28 as falling within the 30-day window "
                "creating elevated volatility risk, note the negligible "
                "dividend yield makes Income Wheel less suitable, and "
                "recommend avoiding a covered call this cycle. Should "
                "suggest revisiting after earnings clarity and note NVDA "
                "as a potential Cash-Secured Put candidate for entry."
            ),
        },
    },
    # -----------------------------------------------------------------------
    # Example 5 — TSLA (Tesla)
    # Expected: AVOID — not a dividend aristocrat + earnings FAIL (hard stop)
    # -----------------------------------------------------------------------
    {
        "inputs": {
            "ticker": "TSLA",
            "shares": 25,
            "current_price": 182.50,
            "dividend_yield_pct": 0.0,
            "is_dividend_aristocrat": False,
            "next_earnings_date": "2026-05-12",
            "next_ex_dividend_date": None,
        },
        "outputs": {
            "aristocrat_screen": "FAIL",
            "earnings_screen": "FAIL",
            "dividend_screen": "FAIL",
            "overall_recommendation": "AVOID",
            "llm_judge_criteria": (
                "The agent should identify TSLA as not a dividend aristocrat, "
                "flag earnings on May 12 as a hard stop (within 7 days), "
                "note the position has no dividend income component, "
                "and recommend avoiding this cycle entirely. Should flag "
                "that 25 shares is insufficient for a covered call contract "
                "(requires 100 shares minimum) as an additional reason "
                "to avoid. Should suggest waiting for post-earnings "
                "stability and accumulating to 100 shares."
            ),
        },
    },
]


# ---------------------------------------------------------------------------
# Dataset creation function
# ---------------------------------------------------------------------------
def create_eval_dataset() -> str:
    """
    Creates the LangSmith evaluation dataset and uploads all examples.

    Idempotent — skips creation if the dataset already exists.
    This is critical for CI pipelines where this script runs repeatedly.

    Returns:
        str: The dataset name confirming successful creation or existence.
    """
    client = Client()

    # Check if dataset already exists — idempotency guard
    if client.has_dataset(dataset_name=DATASET_NAME):
        print(f"Dataset '{DATASET_NAME}' already exists — skipping creation.")
        print(f"To recreate, delete the dataset in LangSmith UI first.")
        return DATASET_NAME

    print(f"Creating dataset '{DATASET_NAME}'...")
    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description=DATASET_DESCRIPTION,
    )

    # Upload examples
    print(f"Uploading {len(EXAMPLES)} examples...")
    client.create_examples(
        inputs=[e["inputs"] for e in EXAMPLES],
        outputs=[e["outputs"] for e in EXAMPLES],
        dataset_id=dataset.id,
    )

    print(f"[OK] Dataset '{DATASET_NAME}' created with {len(EXAMPLES)} examples.")
    print(f"View at: https://smith.langchain.com")
    return DATASET_NAME


# ---------------------------------------------------------------------------
# Entry point — run independently via: make dataset
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    create_eval_dataset()
