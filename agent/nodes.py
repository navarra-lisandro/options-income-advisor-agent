"""
agent/nodes.py — Graph Node Definitions
=========================================
Defines the individual node functions that make up the LangGraph
state machine. Each node receives the full AgentState, performs one
unit of work, and returns a partial state update.

Architectural Decision — One Node Per Screen:
  The graph uses one node per screening step (aristocrat, earnings,
  dividend overlap) rather than one node per position. This was a
  deliberate SRE-principled decision for three reasons:
    1. LangSmith observability — each screen appears as a discrete
       trace, making slow or incorrect screens immediately visible.
    2. Single responsibility — each node has one failure domain.
    3. Independent testability — nodes can be unit tested without
       running the full graph.
  See ADR-004 for full rationale.

Node Execution Flow:
  START
    → load_portfolio       loads positions from portfolio.json into state
    → screen_aristocrat    runs dividend aristocrat check for all positions
    → screen_earnings      runs earnings calendar check for all positions
    → screen_dividends     runs dividend overlap check for all positions
    → generate_report      Claude synthesizes results into recommendations
  END

LangGraph Reference Docs:
  Node basics:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#nodes
  How nodes update state:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
  ToolNode (executes LLM tool calls):
    https://langchain-ai.github.io/langgraph/reference/prebuilt/#toolnode
  Binding tools to an LLM:
    https://langchain-ai.github.io/langgraph/how-tos/tool-calling/

Design Decisions:
  - Each screening node iterates over all positions and updates the
    screenings list in state. Downstream nodes build on prior results.
  - generate_report is the only node that calls the LLM directly.
    All screening nodes use deterministic tool calls — no LLM needed
    for the screening logic itself.
  - The LLM is given the full screening results and portfolio context
    so it can write a nuanced recommendation that includes the
    estimated annual income yield (premium + dividend).
"""

import json
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic

from agent.state import AgentState, PositionScreening
from agent.tools import (
    check_dividend_aristocrat,
    check_earnings_calendar,
    check_dividend_overlap,
    TOOLS,
)


# ---------------------------------------------------------------------------
# LLM instance — bound with tools for the generate_report node
# Model is configured once here and reused across nodes
# ---------------------------------------------------------------------------
llm = ChatAnthropic(model="claude-sonnet-4-5")
llm_with_tools = llm.bind_tools(TOOLS)


# ---------------------------------------------------------------------------
# Helper — get or create a PositionScreening entry for a ticker
# ---------------------------------------------------------------------------
def _get_or_create_screening(
    screenings: list[PositionScreening], ticker: str
) -> tuple[PositionScreening, int]:
    """
    Returns the existing PositionScreening for a ticker and its index,
    or creates a new one if it doesn't exist yet.
    """
    for i, s in enumerate(screenings):
        if s["ticker"] == ticker:
            return s, i

    new_screening: PositionScreening = {
        "ticker": ticker,
        "aristocrat_screen": "FAIL",
        "earnings_screen": "FAIL",
        "dividend_screen": "FAIL",
        "recommendation": "",
    }
    screenings.append(new_screening)
    return new_screening, len(screenings) - 1


# ---------------------------------------------------------------------------
# Node 1 — load_portfolio
# Reads portfolio.json and loads positions into state
# ---------------------------------------------------------------------------
def load_portfolio(state: AgentState) -> dict:
    """
    Loads the synthetic portfolio from data/portfolio.json into state.
    This is the entry point of the graph — all subsequent nodes read
    positions from state rather than directly from the file.
    """
    portfolio_path = (
        Path(__file__).parent.parent / "data" / "portfolio.json"
    )
    with open(portfolio_path) as f:
        data = json.load(f)

    positions = [
        {
            "ticker": p["ticker"],
            "shares": p["shares"],
            "current_price": p["current_price"],
            "dividend_yield_pct": p["dividend_yield_pct"],
            "is_dividend_aristocrat": p["is_dividend_aristocrat"],
            "next_earnings_date": p["next_earnings_date"],
            "next_ex_dividend_date": p["next_ex_dividend_date"],
        }
        for p in data["positions"]
    ]

    return {"positions": positions, "screenings": []}


# ---------------------------------------------------------------------------
# Node 2 — screen_aristocrat
# Runs dividend aristocrat check (Screen 1) for all positions
# ---------------------------------------------------------------------------
def screen_aristocrat(state: AgentState) -> dict:
    """
    Runs the dividend aristocrat screen for every position in the
    portfolio. Updates the aristocrat_screen field in each
    PositionScreening entry in state.

    Screen logic:
      PASS  → stock is a dividend aristocrat
      FAIL  → stock is not a dividend aristocrat
    """
    screenings = list(state.get("screenings", []))

    for position in state["positions"]:
        ticker = position["ticker"]
        result = check_dividend_aristocrat.invoke({"ticker": ticker})

        screening, idx = _get_or_create_screening(screenings, ticker)
        screening["aristocrat_screen"] = result["screen_result"]
        screenings[idx] = screening

    return {"screenings": screenings}


# ---------------------------------------------------------------------------
# Node 3 — screen_earnings
# Runs earnings calendar check (Screen 2) for all positions
# ---------------------------------------------------------------------------
def screen_earnings(state: AgentState) -> dict:
    """
    Runs the earnings calendar screen for every position in the
    portfolio. Updates the earnings_screen field in each
    PositionScreening entry in state.

    Screen logic (30-day expiry window default):
      PASS    → earnings outside the expiry window
      CAUTION → earnings within window but more than 7 days away
      FAIL    → earnings within 7 days — hard stop
    """
    screenings = list(state.get("screenings", []))

    for position in state["positions"]:
        ticker = position["ticker"]
        result = check_earnings_calendar.invoke(
            {"ticker": ticker, "expiry_days": 30}
        )

        screening, idx = _get_or_create_screening(screenings, ticker)
        screening["earnings_screen"] = result["screen_result"]
        screenings[idx] = screening

    return {"screenings": screenings}


# ---------------------------------------------------------------------------
# Node 4 — screen_dividends
# Runs dividend overlap check (Screen 3) for all positions
# ---------------------------------------------------------------------------
def screen_dividends(state: AgentState) -> dict:
    """
    Runs the dividend overlap screen for every position in the
    portfolio. Updates the dividend_screen field in each
    PositionScreening entry in state.

    Screen logic (30-day expiry window default):
      PASS    → ex-dividend date outside expiry window
      CAUTION → ex-dividend date falls within expiry window
      FAIL    → no dividend (not applicable for income wheel)
    """
    screenings = list(state.get("screenings", []))

    for position in state["positions"]:
        ticker = position["ticker"]
        result = check_dividend_overlap.invoke(
            {"ticker": ticker, "expiry_days": 30}
        )

        screening, idx = _get_or_create_screening(screenings, ticker)
        screening["dividend_screen"] = result["screen_result"]
        screenings[idx] = screening

    return {"screenings": screenings}


# ---------------------------------------------------------------------------
# Node 5 — generate_report
# Claude synthesizes all screening results into final recommendations
# ---------------------------------------------------------------------------
def generate_report(state: AgentState) -> dict:
    """
    Uses Claude to synthesize all three screening results into a final
    recommendation for each position. This is the only node that calls
    the LLM directly — all screening logic is deterministic.

    Claude is given:
      - The full portfolio context (positions + screening results)
      - A system prompt encoding the Income Wheel domain logic
      - Instructions to calculate estimated annual income yield

    Output is written to state as final_report (formatted string)
    and as individual recommendation fields in each PositionScreening.
    """
    today = date.today().isoformat()

    # Build context for Claude
    portfolio_context = []
    for position in state["positions"]:
        ticker = position["ticker"]
        screening = next(
            (s for s in state["screenings"] if s["ticker"] == ticker),
            None,
        )
        if screening:
            portfolio_context.append({
                "position": position,
                "screening": screening,
            })

    system_prompt = f"""You are an expert options income advisor specializing in
the Income Wheel strategy for tax-advantaged retirement accounts (401k/Roth).

Today's date is {today}. You are analyzing a portfolio of equity positions
to identify covered call opportunities for the current 30-day expiry cycle.

For each position, you have been provided with three screening results:
  - aristocrat_screen: whether the stock is a dividend aristocrat (PASS/FAIL)
  - earnings_screen: whether earnings fall within the expiry window (PASS/CAUTION/FAIL)
  - dividend_screen: whether the ex-dividend date overlaps the expiry (PASS/CAUTION/FAIL)

Screening result interpretation:
  PASS    → condition is favorable
  CAUTION → condition requires judgment — flag the risk but don't hard stop
  FAIL    → hard stop — do not recommend a covered call this cycle

Overall recommendation logic:
  - RECOMMEND if all screens are PASS
  - PROCEED WITH CAUTION if any screen is CAUTION but none are FAIL
  - AVOID if any screen is FAIL

For each RECOMMEND or PROCEED WITH CAUTION position, include:
  - Estimated annual income yield = dividend_yield_pct + estimated covered call premium yield
  - Use 5-8% as a reasonable covered call premium yield estimate for blue chip stocks
  - Use 8-12% for higher volatility stocks

Write in plain English. Be concise but specific. Think like a human trader, not a robot."""

    user_message = f"""Please analyze the following portfolio and provide
covered call recommendations for the current 30-day expiry cycle:

{json.dumps(portfolio_context, indent=2)}

For each position provide:
1. Overall recommendation (RECOMMEND / PROCEED WITH CAUTION / AVOID)
2. Brief rationale referencing the specific screening results
3. Estimated annual income yield where applicable
4. Any specific guidance on strike selection or timing where relevant

End with a brief portfolio-level summary."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    final_report = response.content

    # Update recommendation field in each screening
    screenings = list(state["screenings"])

    return {
        "messages": messages + [response],
        "final_report": final_report,
        "screenings": screenings,
    }
