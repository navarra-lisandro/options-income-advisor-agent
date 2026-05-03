# Friction Log

These are my candid developer experience notes captured during setup and 
development of `options-income-advisor-agent`. These observations are shared 
in the spirit of honest, constructive feedback from the perspective of 
a new user onboarding to the LangGraph + LangSmith ecosystem for the first time.

These are not intended as criticisms, as I find the tooling to be powerful 
and well-designed. These are simply moments where I paused, got confused, 
or had to search for answers that I expected to find more readily. 

If documentation or guidance already exists for any of these items, I may
have simply missed it, in which case, more prominent linking from the
quickstart might help future users find it faster.

---

## Friction #1 — Python Version Not Documented

**Category:** Setup / Onboarding
**Severity:** High — causes silent failures for new users

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
**Severity:** Medium — clear error message but resolution not obvious

**Note:** This is not a LangChain bug — it is a Poetry 2.x behavior change.
However, since it surfaces specifically when installing LangChain packages,
a note in the installation guide would meaningfully reduce friction for
users on Poetry 2.x. I mention it here only because it is part of the
full onboarding experience a developer has when building with this ecosystem.

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
The error message pointed to Poetry documentation on dependency specification
rather than suggesting the direct fix. The resolution — changing the
constraint to `requires-python = ">=3.11,<4.0.0"` — was straightforward
once identified, but took time to track down.

**Observation:**
If the LangChain installation guide noted this specific constraint for
Poetry 2.x users, it would reduce friction for developers using the newer
version of Poetry. This may already be documented somewhere I didn't find.

---

## Friction #3 — LangSmith API Key Type Not Explained

**Category:** Onboarding / Authentication
**Severity:** Low — minor confusion, easily resolved

**What happened:**
When creating a LangSmith API key, the UI presented two options —
Personal Access Token and Service Key — without explanation of when to
use each or which is appropriate for a developer building a local agent.

**Impact on my experience:**
I had to make an educated guess (Personal Access Token for local development)
based on general familiarity with similar patterns in other tools. A new
developer without that background might not have the same intuition.

**Observation:**
A brief inline description of each option's intended use case would remove
this ambiguity entirely. This is a small change that would meaningfully
improve the onboarding experience for new users.

---

## Friction #4 — Layered Architecture Not Explained Upfront

**Category:** Documentation / Conceptual Clarity
**Severity:** Medium — leads to architectural misunderstandings

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
provider-specific than it actually is. Once I understood the layering, the
design clicked immediately.

**Observation:**
An architecture overview diagram near the top of the LangGraph documentation
showing these three layers would likely accelerate understanding for new
users. Explicitly noting that tools are model-agnostic in the tool-calling
documentation would also help. If this exists somewhere, I didn't encounter
it early enough in my onboarding to benefit from it.

---

## Friction #5 — LangSmith Quickstart Mixes Eval and Agent Code

**Category:** Documentation / Code Organization
**Severity:** Medium — may lead to suboptimal architectural patterns

**What happened:**
The LangSmith evaluation examples I referenced tended to co-locate evaluation
code alongside agent logic in the same file. As someone who thinks about
separation of concerns, I found myself wanting clearer guidance on how to
structure a project that keeps these two concerns independent.

**Impact on my experience:**
I made the deliberate choice to separate `agent/` (pure agent logic) from
`evals/` (evaluation harness) in this project, but that decision required
conscious effort rather than being guided by the documentation.

**Observation:**
A "Project Structure" section in the LangSmith evaluation documentation
showing a clean separation between agent code and evaluation code might help
new users adopt better patterns from the start. I recognize there may be
valid reasons the quickstart examples are structured the way they are —
this is simply an observation from my own experience building this project.

---

## Friction #6 — LangGraph Examples Use Hardcoded Data Sources

**Category:** Documentation / Evaluation Readiness
**Severity:** Medium — causes rework when moving from dev to eval

**What happened:**
LangGraph documentation and quickstart examples tend to show agents reading
from fixed, hardcoded data sources. I built the initial agent reading from
`portfolio.json` directly inside a node, following this pattern. Only when
I reached the evaluation phase did I realize the agent needed to accept
dynamic inputs for LangSmith evaluation to work meaningfully.

**Impact on my experience:**
I had to refactor `load_portfolio()` to accept injected positions before
eval code could be written. In a larger project this could be a significant
rework rather than a small change.

**Observation:**
Earlier guidance in LangGraph documentation, or a brief note in the
evaluation section saying "your agent should accept dynamic inputs for
effective evaluation", would have surfaced this design requirement earlier
in the development cycle. If this guidance exists, I didn't encounter it
before hitting the problem myself.

---

## Friction #7 — has_dataset() Idempotency Not Mentioned in Quickstart

**Category:** Documentation / Evaluation
**Severity:** Low — easy to miss but causes confusing duplicate data

**What happened:**
The LangSmith quickstart and evaluation examples do not mention the
`has_dataset()` idempotency check when creating datasets programmatically.
Running a dataset creation script more than once, something that is common 
in CI pipelines or during development iteration — silently creates duplicate 
datasets in LangSmith.

**Impact on my experience:**
I added an explicit `has_dataset()` check based on prior experience with
similar patterns in other APIs, but a developer without that instinct would
create duplicate datasets and wonder why their eval results appeared doubled.

**Observation:**
A note in the dataset creation documentation, or a code snippet showing
the idempotency check, would be a small addition that prevents a confusing
experience for new users running scripts more than once.

---

## Friction #8 — LangSmith to_pandas() Requires pandas but Is Not Documented

**Category:** Documentation / Evaluation
**Severity:** Medium — causes silent failure without a safety net

**What happened:**
The LangSmith SDK's `EvaluationResults` object exposes a `to_pandas()`
method that is shown in evaluation documentation examples. Calling this
method requires `pandas` to be installed as a separate dependency, but
this requirement is not mentioned in the LangSmith documentation or the
`evaluate()` function reference.

**Impact on my experience:**
`pandas` was not installed in the project's Poetry virtual environment.
The `to_pandas()` call failed silently because it was wrapped in a
`try/except Exception` block, but without that safety net, the evaluation
script would have crashed with a `ModuleNotFoundError` that would have
been confusing to diagnose given no mention of pandas in the LangSmith
docs. The `pandas` package was subsequently added explicitly to `pyproject.toml`.

**Observation:**
A note in the `to_pandas()` documentation, or a dependency callout in
the evaluation how-to guide, would prevent this surprise. Something as
simple as "Note: to_pandas() requires pandas to be installed separately"
would be sufficient.

---

## Friction #9 — "Run in Playground" Misleading from Experiment Context

**Category:** UI / Evaluation
**Severity:** Medium — creates false expectation, wastes setup time

**What happened:**
From within a LangSmith dataset experiment view, the dropdown menu
presents a "Run in Playground" option. The context strongly implies
this will replay the experiment interactively against the dataset.
Instead, it opens a generic prompt playground with no connection to
the LangGraph agent, no awareness of the dataset, and no ability to
run stateful multi-node graphs.

**Impact on my experience:**
I spent time attempting to configure the Playground before realizing
it is designed for simple prompt-based LLMs, and not stateful LangGraph
agents. The output was a generic Claude chatbot response treating the
dataset input fields as raw user messages.

**Observation:**
The "Run in Playground" option appearing inside an experiment context
creates a reasonable expectation that it will replay that experiment
interactively. A tooltip or inline note clarifying that the Playground
supports prompt-based LLMs only — not LangGraph agents — would
prevent this confusion. Alternatively, disabling or hiding the option
for LangGraph-based experiments would be cleaner.

---

## Friction #10 — LangSmith Applications Cannot Link Existing Projects

**Category:** UI / Project Organization
**Severity:** Medium — forces history split, no migration path

**What happened:**
After successfully setting up tracing, experiments, and evaluation
under a workspace-level project named `options-income-advisor-agent`,
I discovered the LangSmith UI has an "Applications" feature that
groups traces and datasets under a named application context. When
I attempted to create an Application and associate the existing
project with it, the UI only offered the option to create a new
project — not to link an existing one.

Entering the existing project name produced this error:

```
"A tracing project with this name already exists.
Please use a different name."
```

See `docs/images/langsmith-application-project-exists-error.png`
for a screenshot of this error.

**Impact on my experience:**
All historical traces, experiments, and evaluation results remain
at the workspace level and cannot be migrated to the Application
context. Starting fresh with a new project would mean losing all
experiment history and the iterative improvement trend visible
across experiments #1 through #6.

**Observation:**
The natural developer onboarding order is: start tracing first,
then discover the Applications feature later. This order makes it
impossible to use Applications with existing project history.
I think that a "Link existing project" option in the Application 
creation flow would solve this entirely. Alternatively, clearer 
onboarding guidance suggesting developers create an Application 
before generating any traces would help new users avoid this trap.

If this migration path exists somewhere in the documentation,
I was not able to find it.

---

## Summary

| # | Category | Severity |
|---|---|---|
| 1 | Python version not documented in quickstart | High |
| 2 | Poetry 2.x + langchain-core constraint conflict | Medium |
| 3 | LangSmith API key type not explained in UI | Low |
| 4 | Layered architecture not explained upfront | Medium |
| 5 | Eval + agent code mixed in quickstart examples | Medium |
| 6 | LangGraph examples use hardcoded data sources | Medium |
| 7 | has_dataset() idempotency not mentioned | Low |
| 8 | to_pandas() requires pandas but undocumented | Medium |
| 9 | "Run in Playground" misleading from experiment context | Medium |
| 10 | Applications cannot link existing projects — no migration path | Medium |
