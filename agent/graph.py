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
    → imports nodes from nodes.py
    → nodes.py imports tools from tools.py
    → nodes.py imports state from state.py
    → tools.py reads data from data/portfolio.json

  Nothing outside agent/ needs to import from anywhere except
  graph.py — it is the single entry point for the agent.

Graph Topology:
  START
    → load_portfolio          (loads positions into state)
    → screen_aristocrat       (Screen 1: dividend aristocrat check)
    → screen_earnings         (Screen 2: earnings calendar check)
    → screen_dividends        (Screen 3: dividend overlap check)
    → generate_report         (Claude synthesizes recommendations)
    → create_order_summary    (Conditional routing based on PASS/FAIL recommendation)
  END

Edge Strategy:
  All edges are regular (unconditional). Every node always runs
  regardless of screening results. See ADR-006 for the full
  rationale and future considerations including conditional edges,
  human-in-the-loop override, and brokerage order automation.

LangGraph Reference Docs:
  StateGraph construction:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#graphs
  Adding nodes:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#nodes
  Adding edges:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#edges
  Compiling the graph:
    https://langchain-ai.github.io/langgraph/concepts/low_level/#compiling-your-graph
  Human-in-the-loop (future consideration):
    https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
"""

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
# Conditional Route
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
    return "has_candidates" if candidates else "all_avoided"

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

    # -----------------------------------------------------------------------
    # Define edges — the execution order of nodes
    # Unconditional and Conditional Branching.
    # See ADR-006 for rationale and future edge considerations.
    # -----------------------------------------------------------------------
    builder.add_edge(START, "load_portfolio")
    builder.add_edge("load_portfolio", "screen_aristocrat")
    builder.add_edge("screen_aristocrat", "screen_earnings")
    builder.add_edge("screen_earnings", "screen_dividends")
    builder.add_edge("screen_dividends", "generate_report")
    builder.add_node("create_order_summary", create_order_summary)
    #Conditional edge branch route_after_report only executes for PASS recommendations
    builder.add_conditional_edges(
        "generate_report",
        route_after_report,
        {
            "has_candidates": "create_order_summary",
            "all_avoided": END
        }
    )
    #Always execute the create_order_summary edge summary, regardless of PASS/FAIL 
    builder.add_edge("create_order_summary", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Entry point — run the agent directly via: make run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Options Income Advisor Agent")
    print("  Income Wheel — Covered Call Screening")
    print("  Account Type: 401k / Roth (Tax-Advantaged)")
    print("=" * 60 + "\n")

    graph = build_graph()

    # Invoke the graph with empty initial state
    # load_portfolio node populates positions on first run
    result = graph.invoke({})

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
    # Execute print after the FINAL REPORT block (if order summary is present):
    if result.get("order_summary"):
        print(result["order_summary"])
