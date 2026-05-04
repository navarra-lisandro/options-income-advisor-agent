# Friction Log

These are my candid developer experience notes captured during setup and development of
`options-income-advisor-agent`. These observations are shared in the spirit
of honest, constructive feedback from the perspective of a new user onboarding
to the LangGraph + LangSmith ecosystem for the first time.

These are not intended as criticisms, as I think the tooling is powerful and well-designed. These
are simply moments where I paused, got confused, or had to search for answers
that I expected to find more readily. I share them in case they are useful
to the team.

If documentation or guidance already exists for any of these items, I may have simply missed it as I'm still finding my way around the ecosystem and the docs are extensive. More prominent linking from the quickstart would help future users in my position find answers faster.

---

## Friction #1 — Python Version Not Documented

**Category:** Setup / Onboarding

**What happened:**
I started with Python 3.13.3 (the current stable release) and encountered
compatibility issues with LangGraph and LangChain dependencies. The
LangGraph documentation I referenced did not explicitly state a recommended
Python version, so I had no signal that 3.13 might be problematic until
I hit errors.

**Impact on my experience:**
I spent time debugging cryptic dependency errors before identifying the root
cause. Downgrading to Python 3.11.9 via pyenv resolved the issue immediately.

**Observation:**
A "Prerequisites" section in the LangGraph quickstart that explicitly
recommends Python 3.11.x would likely save new users meaningful setup time.
If this recommendation exists somewhere in the docs, I wasn't able to find
it easily from the quickstart entry point.

---

## Friction #2 — Poetry 2.x + langchain-core Constraint Conflict

**Category:** Setup / Dependency Management

**Note:** This is not a LangChain bug since it is a Poetry 2.x behavior change.
However, since it surfaces specifically when installing LangChain packages,
a note in the installation guide would meaningfully reduce friction for
users on Poetry 2.x.

**What happened:**
When initializing a new Poetry 2.x project with the default `python = "^3.11"`
constraint, running `poetry add langchain-core` failed with a dependency
resolution error. The cause turned out to be that Poetry 2.x interprets the
caret constraint as potentially allowing Python 4.0+, while `langchain-core`
explicitly requires `<4.0.0`.

**Error message received:**
```
The current project's supported Python range (>=3.11) is not compatible
with some of the required packages Python requirement:
- langchain-core requires Python <4.0.0,>=3.10.0
```

**Impact on my experience:**
The error message pointed to Poetry documentation rather than suggesting
the direct fix. The resolution was to change the constraint to
`requires-python = ">=3.11,<4.0.0"` and was straightforward once identified.

**Observation:**
If the LangChain installation guide noted this specific constraint for
Poetry 2.x users, it would reduce friction for developers using the newer
version of Poetry.

---

## Friction #3 — LangSmith API Key Type Not Explained

**Category:** Setup / Authentication

**What happened:**
When creating a LangSmith API key, the UI presented two options:
(1) Personal Access Token and (2) Service Key. However, it did not include explanation of when to
use each or which is appropriate for a developer building a local agent.

**Impact on my experience:**
I had to make an educated guess (Personal Access Token for local development)
based on general familiarity with similar patterns in other tools.

**Observation:**
A brief inline description of each option's intended use case would remove
this ambiguity entirely.

---

## Friction #4 — Layered Architecture Not Explained Upfront

**Category:** LangGraph / Conceptual Clarity

**What happened:**
I initially assumed that constructs like `@tool` and `ToolNode` were
specific to a particular LLM provider. Through experimentation and reading,
I came to understand that these are LangChain primitives that sit below
LangGraph and work identically across all supported LLM providers:

```
LangGraph     → orchestration (nodes, edges, state machine)
LangChain     → primitives (@tool, ToolNode, tool binding)
LLM Provider  → the model that executes reasoning (Claude, GPT-4o, etc.)
```

**Impact on my experience:**
This misunderstanding initially made the architecture feel more complex and
provider-specific than it actually is.

**Observation:**
An architecture overview diagram near the top of the LangGraph documentation
showing these three layers would likely accelerate understanding for new users.

---

## Friction #5 — LangSmith Quickstart Mixes Eval and Agent Code

**Category:** LangSmith / Code Organization

**What happened:**
The LangSmith evaluation examples I referenced tended to co-locate evaluation
code alongside agent logic in the same file. I found myself wanting clearer
guidance on how to structure a project that keeps these two concerns independent.

**Impact on my experience:**
I made the deliberate choice to separate `agent/` from `evals/`, but that
decision required conscious effort rather than being guided by the documentation.

**Observation:**
A "Project Structure" section in the LangSmith evaluation documentation
showing a clean separation between agent code and evaluation code might help
new users adopt better patterns from the start.

---

## Friction #6 — load_dotenv() Must Be Called Before LLM Instantiation

**Category:** LangGraph Development / Authentication

**What happened:**
The LLM was instantiated at module level in `nodes.py`, which executes at
import time, before `load_dotenv()` was called in `graph.py`. This produced
a cryptic authentication error with no hint that import order was the cause.

**Original problematic pattern:**
```python
# graph.py
load_dotenv()  # too late — nodes.py already imported above

from agent.nodes import load_portfolio, ...
```

**Error received:**
```
TypeError: Could not resolve authentication method. Expected either
api_key or auth_token to be set.
```

**Fix — moved load_dotenv() to nodes.py before LLM instantiation:**
https://github.com/navarra-lisandro/options-income-advisor-agent/blob/main/agent/nodes.py

**Observation:**
The LangChain docs show `ChatAnthropic()` instantiation but do not mention
that environment variables must be loaded before the LLM object is created.
For someone unfamiliar with Python module-level execution order, this is
a non-obvious failure mode that would take meaningful time to diagnose.

---

## Friction #7 — Annotated[list, add_messages] Required for Message History

**Category:** LangGraph Development / State Management

**What happened:**
Without the `add_messages` reducer, LangGraph silently replaces the messages
list on each state update rather than appending to it. Claude loses context
of which tools it already called, producing incorrect behavior with no error.

**What a beginner would write:**
```python
class AgentState(TypedDict):
    messages: list  # silently replaces on each update
```

**What is actually required:**
```python
from typing import Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # correctly appends
```

The `add_messages` reducer is documented in the LangGraph graphs
reference at:
https://langchain-ai.github.io/langgraph/reference/graphs/#add_messages

However, it is not prominently featured in the quickstart where
most new users first define their AgentState. Finding it requires
knowing to look in the reference docs specifically.

**Working code:**
https://github.com/navarra-lisandro/options-income-advisor-agent/blob/main/agent/state.py

**Observation:**
This requirement is documented in the LangGraph state docs but is not
prominently featured in the quickstart. The silent failure mode (i.e. where
Claude loses tool call context without any error) makes this particularly
difficult to diagnose for someone new to the framework.

---

## Friction #8 — Conditional Edge Routing Key Mismatch Produces Cryptic Error

**Category:** LangGraph Development / Conditional Routing

**What happened:**
When the string returned by the routing function doesn't exactly match a key
in the conditional edges dict, LangGraph raises a KeyError pointing to
internal LangGraph code rather than the user's routing function.

**Example of the problematic pattern:**
```python
# routing function returns:
return "has_candidates"

# edges dict has a typo:
{
    "has_candidate": "create_order_summary",  # missing 's'
    "all_avoided": END
}
# Result: KeyError deep in LangGraph internals
```

**Working code:**
https://github.com/navarra-lisandro/options-income-advisor-agent/blob/main/agent/graph.py

**Observation:**
A more helpful error message pointing to the routing function and listing
available keys would save meaningful debugging time for new users writing
their first conditional edge.

---

## Friction #9 — LangGraph Examples Use Hardcoded Data Sources

**Category:** LangGraph Development / Evaluation Readiness

**What happened:**
LangGraph documentation and quickstart examples tend to show agents reading
from fixed, hardcoded data sources. I built the initial agent reading from
`portfolio.json` directly inside a node. Only when I reached the evaluation
phase did I realize the agent needed to accept dynamic inputs for LangSmith
evaluation to work meaningfully, thus requiring a refactor.

**Observation:**
Earlier guidance (even a brief note saying "your agent should accept dynamic
inputs for effective evaluation") would have surfaced this design requirement
earlier in the development cycle.

---

## Friction #10 — has_dataset() Idempotency Not Mentioned in Quickstart

**Category:** LangSmith Development / Dataset Management

**What happened:**
The LangSmith quickstart does not mention the `has_dataset()` idempotency
check when creating datasets programmatically. Running a dataset creation
script more than once silently creates duplicate datasets.

**Observation:**
A note or code snippet showing the idempotency check would prevent a
confusing experience for new users running scripts more than once,
particularly in CI pipelines.

---

## Friction #11 — LangSmith to_pandas() Requires pandas but Is Not Documented

**Category:** LangSmith Development / Evaluation Results

**What happened:**
The LangSmith SDK's `EvaluationResults.to_pandas()` method requires `pandas`
to be installed separately. This is not mentioned in the LangSmith docs.
The call failed silently because it was wrapped in a `try/except Exception`
block and without that safety net it would have crashed with a confusing
`ModuleNotFoundError`.

**Observation:**
A note such as "to_pandas() requires pandas to be installed separately"
in the evaluation how-to guide would be sufficient.

---

## Friction #12 — "Run in Playground" Option Misleading from Experiment Context

**Category:** LangSmith UI / Evaluation

**What happened:**
From within a dataset experiment view, the "Run in Playground" option
implies it will replay the experiment interactively against the dataset.
Instead it opens a generic prompt playground with no connection to the
LangGraph agent.

**Observation:**
A tooltip clarifying that Playground supports prompt-based LLMs only,
not stateful LangGraph agents, would help set the right expectation.
If this limitation is documented somewhere, I wasn't able to find it
before spending time attempting to configure the Playground.

---

## Friction #13 — LangSmith Applications Cannot Link Existing Projects

**Category:** LangSmith UI / Project Organization

**What happened:**
After setting up tracing under a workspace-level project, I discovered the
Applications feature but could not associate my existing project with it.
The UI only allows creating new projects but not linking existing ones.

**Error received:**
```
"A tracing project with this name already exists.
Please use a different name."
```

See `docs/images/langsmith-application-project-exists-error.png`

**Observation:**
A "Link existing project" option, or clearer onboarding guidance to create
the Application before generating any traces, would solve this entirely.
The natural developer onboarding order is to start tracing first and
discover Applications later and this order makes migration impossible after the fact.

---

## Summary

| # | Area | Category |
|---|---|---|
| 1 | Setup | Python version not documented in quickstart |
| 2 | Setup | Poetry 2.x + langchain-core constraint conflict |
| 3 | Setup | LangSmith API key type not explained in UI |
| 4 | LangGraph | Layered architecture not explained upfront |
| 5 | LangSmith | Eval + agent code mixed in quickstart examples |
| 6 | LangGraph | load_dotenv() must precede LLM instantiation |
| 7 | LangGraph | Annotated[list, add_messages] required — silent failure |
| 8 | LangGraph | Conditional edge key mismatch (cryptic error) |
| 9 | LangGraph | Examples use hardcoded data sources |
| 10 | LangSmith | has_dataset() idempotency not mentioned |
| 11 | LangSmith | to_pandas() requires pandas ( undocumented) |
| 12 | LangSmith | "Run in Playground" misleading from experiment context |
| 13 | LangSmith | Applications cannot link existing projects |
