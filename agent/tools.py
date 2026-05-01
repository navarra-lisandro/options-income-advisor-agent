"""
agent/tools.py — Tool Definitions
===================================
Defines the tools Claude can autonomously call during graph execution.
Tools are LangChain primitives — they are model-agnostic and work
identically regardless of which LLM is used.

IMPORTANT: My docstrings are written for Claude, not just humans. 
Claude reads each tool's name, docstring, and parameter types to decide
when to call it and with what arguments. The tools themselves are passive
as they only return data. Claude is the active reasoner that interprets 
the chained results.

LangChain Reference Docs:
  @tool decorator:
    https://python.langchain.com/docs/concepts/tools/
  ToolNode (executes tools called by the LLM):
    https://langchain-ai.github.io/langgraph/reference/prebuilt/#toolnode
  Tool calling pattern in LangGraph:
    https://langchain-ai.github.io/langgraph/how-tos/tool-calling/
  How Claude decides which tools to call:
    https://docs.anthropic.com/en/docs/build-with-claude/tool-use

Design Decisions:
  - All data is synthetic — no live market API calls. Tools read from
    portfolio.json loaded into state. This keeps the project self-contained
    and eliminates external dependencies that could break during a demo.
  - expiry_days defaults to 30 but is parameterized — a trader might
    want 45-day or 60-day expiry windows. See ADR-004.
  - Tools return structured dicts with explicit field names so Claude
    can reason clearly over the results in natural language.
  - Each docstring is written for Claude, not just for humans — Claude
    reads the docstring to understand when and how to use the tool.
"""

import json
from datetime import date, datetime
from pathlib import Path

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Helper — load portfolio data from portfolio.json
# ---------------------------------------------------------------------------
def _load_portfolio() -> list[dict]:
    """Load synthetic portfolio data from data/portfolio.json."""
    portfolio_path = Path(__file__).parent.parent / "data" / "portfolio.json"
    with open(portfolio_path) as f:
        data = json.load(f)
    return data["positions"]


def _get_position(ticker: str) -> dict | None:
    """Look up a single position by ticker symbol."""
    positions = _load_portfolio()
    return next((p for p in positions if p["ticker"] == ticker), None)


def _days_until(date_str: str | None) -> int | None:
    """Calculate days from today until a given ISO date string."""
    if not date_str:
        return None
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (target - date.today()).days


# ---------------------------------------------------------------------------
# Tool 1 — Get portfolio positions
# ---------------------------------------------------------------------------
@tool
def get_portfolio_positions() -> list[dict]:
    """
    Returns all current equity positions in the 401k/Roth portfolio.

    Use this tool first before analyzing any individual position.
    Returns a list of positions, each containing ticker, shares,
    current price, dividend yield, aristocrat status, and key dates.
    """
    positions = _load_portfolio()
    return [
        {
            "ticker": p["ticker"],
            "shares": p["shares"],
            "current_price": p["current_price"],
            "dividend_yield_pct": p["dividend_yield_pct"],
            "is_dividend_aristocrat": p["is_dividend_aristocrat"],
            "next_earnings_date": p["next_earnings_date"],
            "next_ex_dividend_date": p["next_ex_dividend_date"],
        }
        for p in positions
    ]


# ---------------------------------------------------------------------------
# Tool 2 — Check dividend aristocrat status
# ---------------------------------------------------------------------------
@tool
def check_dividend_aristocrat(ticker: str) -> dict:
    """
    Checks whether a stock is a dividend aristocrat and returns its
    dividend yield.

    A dividend aristocrat has 25+ consecutive years of dividend growth.
    These stocks are the strongest candidates for the Income Wheel
    strategy in a tax-advantaged account because they provide both
    premium income from covered calls and reliable dividend income.

    Args:
        ticker: The equity ticker symbol e.g. 'JNJ'

    Returns a dict with:
        - ticker: the ticker symbol
        - is_dividend_aristocrat: True if the stock qualifies
        - dividend_yield_pct: annual dividend yield as a percentage
        - screen_result: PASS if aristocrat, FAIL if not
        - notes: explanation of the result
    """
    position = _get_position(ticker)
    if not position:
        return {"ticker": ticker, "error": f"Position {ticker} not found in portfolio"}

    is_aristocrat = position["is_dividend_aristocrat"]
    yield_pct = position["dividend_yield_pct"]

    return {
        "ticker": ticker,
        "is_dividend_aristocrat": is_aristocrat,
        "dividend_yield_pct": yield_pct,
        "screen_result": "PASS" if is_aristocrat else "FAIL",
        "notes": (
            f"{ticker} is a dividend aristocrat with a {yield_pct}% annual yield — "
            f"strong Income Wheel candidate."
            if is_aristocrat
            else f"{ticker} is not a dividend aristocrat (yield: {yield_pct}%) — "
            f"less ideal for Income Wheel but may still be viable."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 3 — Check earnings calendar
# ---------------------------------------------------------------------------
@tool
def check_earnings_calendar(ticker: str, expiry_days: int = 30) -> dict:
    """
    Checks whether a stock has earnings scheduled within the option
    expiry window, which creates volatility and assignment risk.

    Selling a covered call into an earnings event exposes the position
    to IV crush and unpredictable price moves. This is assessed on a
    three-state scale:
      - PASS: earnings outside the expiry window — safe to proceed
      - CAUTION: earnings within the window but more than 7 days away
      - FAIL: earnings within 7 days — hard stop, do not sell this cycle

    Args:
        ticker: The equity ticker symbol e.g. 'JNJ'
        expiry_days: Number of days in the option expiry window (default 30)

    Returns a dict with:
        - ticker: the ticker symbol
        - next_earnings_date: ISO date string or null
        - days_to_earnings: number of days until earnings
        - expiry_days: the window used for evaluation
        - screen_result: PASS, CAUTION, or FAIL
        - notes: explanation of the result
    """
    position = _get_position(ticker)
    if not position:
        return {"ticker": ticker, "error": f"Position {ticker} not found in portfolio"}

    earnings_date = position["next_earnings_date"]
    days_to_earnings = _days_until(earnings_date)

    if days_to_earnings is None:
        screen_result = "PASS"
        notes = f"{ticker} has no upcoming earnings date on record — safe to proceed."
    elif days_to_earnings <= 7:
        screen_result = "FAIL"
        notes = (
            f"{ticker} has earnings in {days_to_earnings} days — hard stop. "
            f"Do not sell a covered call this cycle. Wait until post-earnings."
        )
    elif days_to_earnings <= expiry_days:
        screen_result = "CAUTION"
        notes = (
            f"{ticker} has earnings in {days_to_earnings} days, which falls within "
            f"the {expiry_days}-day expiry window. Elevated volatility risk — "
            f"consider a shorter expiry or wait for post-earnings stability."
        )
    else:
        screen_result = "PASS"
        notes = (
            f"{ticker} earnings are {days_to_earnings} days away — "
            f"safely outside the {expiry_days}-day expiry window. Safe to proceed."
        )

    return {
        "ticker": ticker,
        "next_earnings_date": earnings_date,
        "days_to_earnings": days_to_earnings,
        "expiry_days": expiry_days,
        "screen_result": screen_result,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Tool 4 — Check dividend overlap
# ---------------------------------------------------------------------------
@tool
def check_dividend_overlap(ticker: str, expiry_days: int = 30) -> dict:
    """
    Checks whether the ex-dividend date falls within the covered call
    expiry window, creating early assignment risk.

    If the ex-dividend date falls before the call expiry, the call buyer
    may exercise early to capture the dividend — pulling shares away
    before the dividend is collected. This is a subtle but important
    risk that many options traders overlook.

    Assessment scale:
      - PASS: ex-dividend date outside the expiry window — safe to proceed
      - CAUTION: ex-dividend date falls within the expiry window
      - FAIL: no dividend (not applicable for income wheel strategy)

    Args:
        ticker: The equity ticker symbol e.g. 'JNJ'
        expiry_days: Number of days in the option expiry window (default 30)

    Returns a dict with:
        - ticker: the ticker symbol
        - next_ex_dividend_date: ISO date string or null
        - days_to_ex_dividend: number of days until ex-dividend date
        - expiry_days: the window used for evaluation
        - screen_result: PASS, CAUTION, or FAIL
        - notes: explanation of the result
    """
    position = _get_position(ticker)
    if not position:
        return {"ticker": ticker, "error": f"Position {ticker} not found in portfolio"}

    ex_div_date = position["next_ex_dividend_date"]
    days_to_ex_div = _days_until(ex_div_date)
    dividend_yield = position["dividend_yield_pct"]

    if ex_div_date is None or dividend_yield == 0.0:
        screen_result = "FAIL"
        notes = (
            f"{ticker} pays no dividend — dividend overlap is not applicable. "
            f"Income Wheel is less suitable without a dividend component."
        )
    elif days_to_ex_div <= expiry_days:
        screen_result = "CAUTION"
        notes = (
            f"{ticker} ex-dividend date is in {days_to_ex_div} days, within the "
            f"{expiry_days}-day expiry window. Early assignment risk — the call "
            f"buyer may exercise to capture the dividend. Consider selecting a "
            f"strike further OTM or waiting until after the ex-dividend date."
        )
    else:
        screen_result = "PASS"
        notes = (
            f"{ticker} ex-dividend date is {days_to_ex_div} days away — "
            f"safely outside the {expiry_days}-day expiry window. No early "
            f"assignment risk from dividend capture."
        )

    return {
        "ticker": ticker,
        "next_ex_dividend_date": ex_div_date,
        "days_to_ex_dividend": days_to_ex_div,
        "expiry_days": expiry_days,
        "screen_result": screen_result,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Tool registry — passed to ToolNode and LLM binding in graph.py
# This is the registry we'll pass to both ToolNode and the LLM binding in graph.py. 
# One place, referenced everywhere --> D.R.Y. SRE principle.
# ---------------------------------------------------------------------------

TOOLS = [
    get_portfolio_positions,
    check_dividend_aristocrat,
    check_earnings_calendar,
    check_dividend_overlap,
]
