# ADR-004 — Agent Domain: Options Income Advisor

**Date:** 2026-04-30
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

The take-home exercise required building a LangGraph agent on a domain
of my choosing. The agent needed to be simple enough to build in a few
days, but meaningful enough to demonstrate real multi-step reasoning,
conditional branching, and tool-calling that are the core capabilities 
that make LangGraph worth using in the first place.

I have a background in trading systems and active options trading, so
this felt like a natural fit. The goal was to pick something I could
speak to authentically during the walkthrough rather than reaching for
a generic Q&A bot that I'd have to pretend to care about.

---

## Decision

We build a **covered call screening agent** for a tax-advantaged account
(401k/Roth), focused on the first leg of the Income Wheel strategy. The
agent analyzes a synthetic equity portfolio and recommends whether each
position is a suitable covered call candidate based on three key screens.

---

## Why Options Income Analysis

A few things made this domain work well for this exercise:

- **Multi-step reasoning maps naturally to nodes.** LangGraph describes
  itself as a low-level orchestration framework for building controllable
  agents, designed specifically for workflows where state needs to be
  passed through a sequence of discrete steps. A covered call screening
  decision is exactly that kind of workflow: a series of distinct checks
  where each step informs the next.

- **The screening questions produce clear yes/no branching.** Conditional
  edges in LangGraph are most convincing when the conditions are
  defensible. "Don't sell a call into earnings" is a real rule that
  any options trader would recognize, not an arbitrary branch I invented
  to show off the feature.

- **The eval dataset writes itself.** Because the screening logic has
  real right and wrong answers, building a LangSmith evaluation dataset
  with meaningful expected outputs is straightforward. A position with
  earnings next week should not get a covered call recommendation, full
  stop.

---

## Why 401k/Roth Over a Taxable Account

I went back and forth on this one. A taxable account adds a tax
consideration layer that initially seemed interesting for demonstrating
agent reasoning. But when I thought it through, the taxable account
agent mostly says no, avoid dividend stocks, avoid short-term gains,
stay away from this, watch out for that. That's avoidance logic.

A 401k/Roth account lets the agent make positive, nuanced recommendations
across multiple dimensions: dividend profile, earnings risk, dividend
capture overlap. That's selection logic, and it produces a richer,
more interesting agent. The tax-advantaged context also makes the
Income Wheel strategy genuinely compelling since premiums compound
tax-free, which is the whole point.

The taxable account implementation was considered and deliberately
scoped out. It's not that it wouldn't work — it would — it just
makes for a less interesting demo.

---

## The Three Screening Questions

These came directly from real trading practice, not from engineering
convenience:

**1. Is it a Dividend Aristocrat?**
Dividend aristocrats are held for the long-term income stream. Selling
covered calls on them amplifies income on a position you already intend
to hold indefinitely. If it's not a dividend aristocrat, the income
wheel is less compelling, and you're just renting out shares you might
not care as much about keeping.

**2. Does the expiry window overlap upcoming earnings?**
Earnings cause volatility spikes and unpredictable price moves. Selling
a call into an earnings event exposes the position to assignment risk
or a loss that wipes out the premium entirely. This is a hard stop.
If earnings fall within the expiry window, the recommendation is to
wait for the next cycle.

**3. Does the covered call overlap the ex-dividend date?**
If the ex-dividend date falls before the call expiry, the call buyer
may exercise early to capture the dividend, thus pulling the shares away
before the dividend is collected. This is a subtler risk that many
new options traders miss. The agent flags it explicitly and adjusts
the recommendation accordingly.

---

## Data Approach — Synthetic Data with Tool-Calling Pattern

The portfolio data is entirely synthetic as there are no live market
API calls. This was a deliberate choice for a few reasons: it keeps
the project self-contained, eliminates external API dependencies that
could break during a demo, and lets us design the dataset to produce
interesting and varied agent outputs.

That said, the agent accesses this data through tools rather than
reading it directly from a file. This was important because it
demonstrates the tool-calling pattern properly; Claude reads the
tool docstrings, decides which tools to invoke, and reasons over
the results. The data is synthetic but the reasoning pattern is real.

The synthetic portfolio is designed to produce naturally varied outputs:
- One position that is a clean covered call candidate (JNJ)
- One position with earnings risk (NVDA)
- One position that needs dividend overlap caution (KO)

This variety makes the LangSmith evaluation dataset meaningful rather
than trivially easy to pass.

---

## Module Structure Rationale

The agent is split across four modules, each with a single responsibility:

**`state.py`** — defines the `AgentState` TypedDict that flows through
every node. State is the single source of truth for a graph run. Keeping
it in its own file makes it independently readable and testable.

**`tools.py`** — defines the tools Claude can call during execution.
These are LangChain primitives (`@tool` decorated functions) and are
completely model-agnostic. Separating them from node logic keeps the
tool definitions clean and reusable.

**`nodes.py`** — defines the individual node functions. Each node
does one thing: reads from state, does its work, returns updated state.
Node functions are pure enough to unit test without spinning up the
full graph.

**`graph.py`** — wires everything together. This is the only file
that knows about the full graph topology. Nothing outside `agent/`
needs to import from `graph.py` directly except the entry points
in `evals/` and the notebooks.

---

## Separation of evals/ from agent/

The evaluation harness lives in `evals/` rather than alongside the
agent code. This is an SRE-principled decision based on three tenets:

- **Separation of concerns** — `agent/` has zero awareness of LangSmith
  or how it is being evaluated. Deleting `evals/` entirely should not
  affect agent behavior in any way.

- **DRY** — the evaluation harness can be pointed at any agent without
  modification to the agent code itself.

- **Clarity** — the directory structure communicates intent immediately.
  `agent/` is what runs in production. `evals/` is what measures it.

---

## Income Wheel Leg 2 — Designed, Not Built

The full Income Wheel involves a second leg: selling a cash-secured put
to enter a new position at a lower cost basis while collecting premium.
This leg was designed but not implemented in the production agent due
to time constraints.

The CSP node is prototyped in `notebooks/exploration.ipynb` and the
full wheel design is documented here so that the intent is clear. The
natural next iteration of this agent is wiring in the CSP leg and
adding account-level position sizing logic.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|---|---|
| Generic Q&A bot | Too simple — doesn't demonstrate meaningful conditional branching |
| Fantasy football lineup optimizer | Weaker eval dataset — subjective outputs harder to score |
| RAG-based research agent | Adds retrieval infrastructure complexity that distracts from LangGraph/LangSmith focus |
| Full Income Wheel (both legs) | Time constraint — Leg 1 alone demonstrates the pattern cleanly |
| Taxable account | Produces avoidance logic rather than selection logic — less interesting agent behavior |

---

## Consequences

- **Positive:** Domain expertise allows authentic, fluent discussion
  during the 30-minute walkthrough without needing to fake it.
- **Positive:** Three clear screening questions produce natural
  conditional branching that demonstrates LangGraph properly.
- **Positive:** Synthetic dataset is designed for eval variety —
  not all positions pass all screens.
- **Neutral:** No live market data means the agent cannot be used
  for real trading decisions. This is intentional for this scope.
- **Watch:** The CSP leg (Income Wheel Leg 2) is the obvious next
  feature. If time permits before the deadline, it will be prototyped
  in the Jupyter notebook.

---

## References

- [LangGraph nodes and edges](https://langchain-ai.github.io/langgraph/concepts/low_level/)
- [LangGraph tool calling](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
- [Income Wheel options strategy](https://www.investopedia.com/terms/w/wheel-strategy.asp)
- [Dividend Aristocrats](https://www.investopedia.com/terms/d/dividend-aristocrat.asp)
- See also: `FRICTION_LOG.md` Friction #5 — evals/ separation pattern
  not demonstrated in LangSmith quickstart examples
