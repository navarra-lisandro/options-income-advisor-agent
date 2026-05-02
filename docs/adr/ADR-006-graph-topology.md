# ADR-006 — Graph Topology and Edge Strategy

**Date:** 2026-05-01
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

LangGraph supports two types of edges between nodes: regular
(unconditional) edges that always execute, and conditional edges
that route based on the current state. Choosing between them is
a meaningful architectural decision that affects graph complexity,
observability, and future extensibility.

---

## Decision

For the initial release we use **straight-line regular edges** 
for all node transitions. Every node always runs regardless of 
screening results. No conditional branching is implemented in 
the current version.

---

## Graph Topology

```
START
  → load_portfolio       loads positions into state
  → screen_aristocrat    Screen 1: dividend aristocrat check
  → screen_earnings      Screen 2: earnings calendar check
  → screen_dividends     Screen 3: dividend overlap check
  → generate_report      Claude synthesizes recommendations
END
```

---

## Rationale

**The report is always valuable — even on all-FAIL portfolios:**
A report that explains *why* every position is avoided is more
useful to a trader than silence. The agent's value is reasoned
explanations, not binary outputs. Skipping `generate_report`
on an all-FAIL portfolio would eliminate the most useful part
of the output.

**Branching logic lives in Claude, not the graph:**
The three-state screening model (PASS/CAUTION/FAIL) gives Claude
rich context to reason over. Claude decides what CAUTION means
for each position and the graph doesn't need to know this. Pushing
routing logic into conditional edges would duplicate reasoning
that Claude handles more naturally in natural language.

**Simplicity over premature optimization:**
Conditional edges add routing complexity that I did couldn't justify
by for the initial agent use case. The graph topology is intentionally 
simple: LangGraph handles the orchestration, and Claude handles the 
judgment. This separation of concerns is cleaner than encoding domain
logic into graph routing functions.

**Predictable LangSmith traces:**
Straight edges produce a consistent, predictable trace in
LangSmith where every run shows the same five nodes in the same
order. This makes evaluation and debugging straightforward.
Conditional edges would produce variable trace shapes that
are harder to compare across runs.

---

## One Node Per Screen — Rationale

The graph uses one node per screening step rather than one node
per position. **This was a deliberate SRE-principled decision:**

1. **LangSmith observability** — each screen appears as a discrete
   trace entry. Slow or incorrect screens are immediately visible
   without digging through logs.

2. **Single responsibility** — each node has one failure domain.
   A bug in earnings screening doesn't affect dividend screening.

3. **Independent testability** — each node function can be unit
   tested in isolation without running the full graph.

---

## Conditional Edge — Actual Implementation

After initial development with straight edges, a conditional edge
was added after `generate_report` to demonstrate LangGraph's
routing capabilities and provide a natural handoff point for
future brokerage integration.

**Updated Graph Topology:**
```
START
  → load_portfolio
  → screen_aristocrat
  → screen_earnings
  → screen_dividends
  → generate_report
      → has_candidates → create_order_summary → END
      → all_avoided    → END
```

**Routing Function:**
```python
def route_after_report(state: AgentState) -> str:
    candidates = [
        s for s in state["screenings"]
        if s["aristocrat_screen"] != "FAIL"
        and s["earnings_screen"] != "FAIL"
        and s["dividend_screen"] != "FAIL"
    ]
    return "has_candidates" if candidates else "all_avoided"
```

**Why after `generate_report` and not before?**
The full report is always valuable — even an all-FAIL portfolio
needs a reasoned explanation. The conditional edge comes after
the report to add a condensed, actionable summary only when
there is something to act on. Routing before `generate_report`
would skip the most valuable output.

**What `create_order_summary` produces:**
A clean, structured summary of actionable positions including
share count, current value, and recommendation status. This
serves two purposes:
  1. Immediate — clean trader-facing output
  2. Future — structured input for brokerage order automation

---

## Future Considerations

**1. Short Circuit Optimization**
If ALL positions receive FAIL across all three screens, a
conditional edge after `screen_dividends` could skip the
LLM call entirely, thus saving API cost on portfolios with no
candidates. If not implemented the report is valuable even
on all-FAIL portfolios at this scale.

**2. Human-in-the-Loop Override (Option A Routing)**
LangGraph natively supports interrupting graph execution via
the `interrupt` mechanism. A future version could:
  - Route to `create_order_summary` if any aristocrat exists
    (Option A — looser criteria)
  - Pause and wait for trader approval before proceeding
  - Allow human to override FAIL screens

```
generate_report → human_review (interrupt)
    → APPROVE:   create_order_summary → END
    → OVERRIDE:  create_order_summary → END
    → REJECT:    END
```

Reference:
  https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/

**3. Brokerage Order Automation**
`create_order_summary` is designed as the natural handoff
point for a future brokerage API integration. The structured
output (ticker, shares, value, recommendation) maps directly
to the parameters needed for a covered call order:

```python
@tool
def create_options_order(
    ticker: str,
    strike: float,
    expiry: str,
    contracts: int
) -> dict:
    """Places a covered call order via the brokerage API."""
    # Fidelity / Chase API integration
```

Combined with human-in-the-loop approval, this closes the loop
from screening → recommendation → approval → execution.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|---|---|
| Conditional edge to skip LLM on all-FAIL | Report is always valuable — premature optimization |
| One node per position | **Less LangSmith observability, harder to isolate failures** |
| Human-in-the-loop now | Out of scope for this evaluation exercise, so documented as future work |
| Parallel node execution | Not needed since screens are fast and sequential logic is clearer |

---

## Consequences

- **Positive:** Simple, predictable graph topology that is easy 
  to reason about, debug, and explain during a walkthrough.
- **Positive:** Consistent LangSmith traces as every run produces
  the same shape, making evaluation straightforward.
- **Positive:** Future conditional edges and human-in-the-loop are
  clearly documented so the path to production is visible.
- **Neutral:** LLM is called even when all positions are FAIL, at
  a small cost for a demo project, but worth addressing in production.
- **Watch:** As the portfolio grows, consider parallel node execution
  for **screening steps to reduce latency** (could I monitor this with LangSmith).

---

## References

- [LangGraph edges](https://langchain-ai.github.io/langgraph/concepts/low_level/#edges)
- [LangGraph conditional edges](https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges)
- [LangGraph human-in-the-loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [LangGraph interrupt mechanism](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/#interrupt)
