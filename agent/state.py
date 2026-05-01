"""
agent/state.py — Agent State Definitions
=========================================
Defines the shared state schema that flows through every node in the
LangGraph state machine. State is the single source of truth for a
single graph run — every node reads from it and writes back to it.

LangGraph Reference Docs:
  State basics:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#state
  TypedDict pattern:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#schema
  Messages in state (add_messages reducer):
    https://langchain-ai.github.io/langgraph/reference/graphs/#add_messages
  Why messages live in state (tool call loop):
    https://langchain-ai.github.io/langgraph/reference/agents/

Design Decisions:
  - Position TypedDict contains only fields the agent actively reasons
    about. Display-only fields (company name, sector, notes) are
    intentionally excluded to keep state minimal and purposeful.
  - ScreenResult uses a three-state model (PASS / CAUTION / FAIL)
    rather than binary to preserve trading nuance. See ADR-004.
  - messages uses Annotated[list, add_messages] so LangGraph
    automatically appends new messages rather than replacing the list.
    This drives the tool-calling loop — Claude reads the full message
    history on each iteration to decide its next action.
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


# ---------------------------------------------------------------------------
# Screening result type — three states to preserve trading nuance
# PASS    → condition is favorable, proceed
# CAUTION → condition requires trader judgment before executing
# FAIL    → hard stop, do not execute this cycle
# ---------------------------------------------------------------------------
ScreenResult = Literal["PASS", "CAUTION", "FAIL"]


# ---------------------------------------------------------------------------
# Position — a single equity holding in the portfolio
# Only fields the agent actively reasons about are included.
# ---------------------------------------------------------------------------
class Position(TypedDict):
    ticker:                 str        # equity ticker symbol e.g. "JNJ"
    shares:                 int        # number of shares held
    current_price:          float      # current market price per share
    dividend_yield_pct:     float      # annual dividend yield as a percentage
    is_dividend_aristocrat: bool       # 25+ consecutive years of dividend growth
    next_earnings_date:     str | None # ISO date string e.g. "2026-07-15"
    next_ex_dividend_date:  str | None # ISO date string e.g. "2026-05-23"


# ---------------------------------------------------------------------------
# PositionScreening — screening results for a single position
# Populated incrementally as each screening node runs.
# ---------------------------------------------------------------------------
class PositionScreening(TypedDict):
    ticker:            str           # ties result back to the position
    aristocrat_screen: ScreenResult  # Screen 1: is it a dividend aristocrat?
    earnings_screen:   ScreenResult  # Screen 2: earnings outside expiry window?
    dividend_screen:   ScreenResult  # Screen 3: no dividend overlap risk?
    recommendation:    str           # final recommendation text from LLM


# ---------------------------------------------------------------------------
# AgentState — the full state of a single graph run
# Passed into every node. Nodes return partial updates.
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    positions:    list[Position]          # raw portfolio loaded from portfolio.json
    screenings:   list[PositionScreening] # screening results, one per position
    messages:     Annotated[list, add_messages]  # tool call / LLM message history
    final_report: str                     # formatted output written by last node
