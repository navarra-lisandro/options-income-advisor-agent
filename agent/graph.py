"""
agent/graph.py — LangGraph State Machine
==========================================
Wires all nodes and edges into a compiled LangGraph StateGraph.
This is the only file that knows the full graph topology — nodes,
edges, entry point, and finish point.

Key architectural principle: graph.py knows nothing about tools,
screening logic, or domain rules. It only knows about nodes and
the order they run in. All intelligence lives in nodes.py and
tools.py.

File Dependency Map:
  graph.py
    -> imports nodes from nodes.py
    -> nodes.py imports tools from tools.py
    -> nodes.py imports state from state.py
    -> tools.py reads data from data/portfolio.json

  Nothing outside agent/ needs to import from anywhere except
  graph.py — it is the single entry point for the agent.

Graph Topology:
  START
    -> load_portfolio      (loads positions into state)
    -> screen_aristocrat   (Screen 1: dividend aristocrat check)
    -> screen_earnings     (Screen 2: earnings calendar check)
    -> screen_dividends    (Screen 3: dividend overlap check)
    -> generate_report     (Claude synthesizes recommendations)
    -> create_order_summary (conditional: only when candidates exist)
  END

Edge Strategy:
  Screens use straight edges — every screening node always runs.
  After generate_report a conditional edge routes to
  create_order_summary when candidates exist, or END when all
  positions are avoided. See ADR-006 for full rationale.

Logging:
  Graph-level logging covers build, compile, and invocation events.
  Node-level logging is handled in nodes.py.
  Configure log level via basicConfig in this module.
  See ADR-007 for full observability strategy.

LangGraph Reference Docs:
  StateGraph construction:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#graphs
  Adding nodes:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#nodes
  Adding edges:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#edges
  Conditional edges:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
  Compiling the graph:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#compiling-your-graph
  Human-in-the-loop (future consideration):
    https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
"""

import logging
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.nodes import (
    load_portfolio,
    screen_aristocrat,
    screen_earnings,
    screen_dividends,
    generate_report,
    create_order_summary,
)

# ---------------------------------------------------------------------------
# Load environment variables from .env
# Required: ANTHROPIC_API_KEY, LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Logging configuration
# INFO level by default — captures graph lifecycle events
# Set LANGCHAIN_VERBOSE=true in .env for detailed LangChain debug logs
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conditional routing function
# Determines whether to route to create_order_summary or END
# after generate_report completes
# ---------------------------------------------------------------------------
def route_after_report(state: AgentState) -> str:
    """
    Conditional routing after generate_report.
    Routes to create_order_summary if any position cleared
    all three screens with no FAIL — Option B routing logic.
    Routes to END if all positions have at least one FAIL screen.
    See ADR-006 for full rationale including Option A future consideration.
    """
    candidates = [
        s for s in state["screenings"]
        if s["aristocrat_screen"] != "FAIL"
        and s["earnings_screen"] != "FAIL"
        and s["dividend_screen"] != "FAIL"
    ]
    route = "has_candidates" if candidates else "all_avoided"
    logger.info("route_after_report: %d candidate(s) -> %s", len(candidates), route)
    return route


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
def build_graph() -> StateGraph:
    """
    Constructs and compiles the LangGraph state machine.

    Returns a compiled graph ready to invoke. The graph is built
    fresh on each call — stateless construction, stateful execution.

    Usage:
        graph = build_graph()
        result = graph.invoke({})
    """
    logger.info("build_graph: building options income advisor agent graph")
    builder = StateGraph(AgentState)

    # -----------------------------------------------------------------------
    # Register nodes
    # Each node is a function from nodes.py that receives AgentState
    # and returns a partial state update.
    # -----------------------------------------------------------------------
    builder.add_node("load_portfolio", load_portfolio)
    builder.add_node("screen_aristocrat", screen_aristocrat)
    builder.add_node("screen_earnings", screen_earnings)
    builder.add_node("screen_dividends", screen_dividends)
    builder.add_node("generate_report", generate_report)
    builder.add_node("create_order_summary", create_order_summary)

    # -----------------------------------------------------------------------
    # Define edges — the execution order of nodes
    # Screening nodes use straight edges — always run in sequence.
    # After generate_report a conditional edge routes based on
    # whether any positions cleared all three screens.
    # See ADR-006 for rationale and future conditional edge considerations.
    # -----------------------------------------------------------------------
    builder.add_edge(START, "load_portfolio")
    builder.add_edge("load_portfolio", "screen_aristocrat")
    builder.add_edge("screen_aristocrat", "screen_earnings")
    builder.add_edge("screen_earnings", "screen_dividends")
    builder.add_edge("screen_dividends", "generate_report")
    builder.add_conditional_edges(
        "generate_report",
        route_after_report,
        {
            "has_candidates": "create_order_summary",
            "all_avoided": END
        }
    )
    builder.add_edge("create_order_summary", END)

    graph = builder.compile()
    logger.info("build_graph: graph compiled successfully with 6 nodes")
    return graph


# ---------------------------------------------------------------------------
# Entry point — run the agent directly via: make run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting options income advisor agent")

    print("\n" + "=" * 60)
    print("  Options Income Advisor Agent")
    print("  Income Wheel — Covered Call Screening")
    print("  Account Type: 401k / Roth (Tax-Advantaged)")
    print("=" * 60 + "\n")

    graph = build_graph()

    logger.info("Invoking graph against portfolio")
    result = graph.invoke({})
    logger.info("Graph execution complete")

    print("\n" + "=" * 60)
    print("  SCREENING RESULTS")
    print("=" * 60)

    for screening in result.get("screenings", []):
        print(f"\n  {screening['ticker']}")
        print(f"    Aristocrat Screen : {screening['aristocrat_screen']}")
        print(f"    Earnings Screen   : {screening['earnings_screen']}")
        print(f"    Dividend Screen   : {screening['dividend_screen']}")

    print("\n" + "=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)
    print(f"\n{result.get('final_report', 'No report generated.')}\n")

    if result.get("order_summary"):
        print(result["order_summary"])
