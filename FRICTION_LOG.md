# Friction Log

Candid developer experience notes captured during setup and development of
`options-income-advisor-agent`. These observations are shared in the spirit
of honest, constructive feedback from the perspective of a new user onboarding
to the LangGraph + LangSmith ecosystem for the first time.

These are not criticisms — the tooling is powerful and well-designed. These
are simply moments where I paused, got confused, or had to search for answers
that I expected to find more readily. I share them in case they are useful
to the team.

If documentation or guidance already exists for any of these items, I may
have simply missed it — in which case, more prominent linking from the
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

## Friction #6 — Poetry 2.x defaults to package mode
New users using Poetry purely for dependency management hit this error when CI tries to install the project. The fix (package-mode = false) is not obvious from the error message. The error suggests --no-root as a workaround but the cleaner fix is the pyproject.toml setting.

**Category:** Setup / Dependency Management
**Severity:** Medium — CI fails clearly, error message is verbose but resolution not obvious

**What happened:**
During the initial GitHub Actions CI run, the pipeline failed
at the dependency installation step with the following error:

"The current project could not be installed: No file/folder
found for package options-income-advisor-agent"

The error surfaced in CI, not during local development, as
poetry install ran cleanly on my machine without this issue.

**Impact on my experience:**
Resolving the error required searching online for the correct
Poetry 2.x configuration. While the error message does mention
package-mode = false as a possible fix, it presents it as one
of three options without clarity on which is most appropriate
for a dependency-management-only project. The correct solution
was adding package-mode = false under [tool.poetry] in
pyproject.toml.

**Observation:**
This is a Poetry 2.x behavior, not specific to LangChain.
However, since it surfaced during LangChain project setup,
it may be worth a brief mention in the installation guide
for developers using Poetry — simply noting that
package-mode = false is recommended for dependency-only
projects.


## Summary

| # | Category | Severity |
|---|---|---|
| 1 | Python version not documented in quickstart | High |
| 2 | Poetry 2.x + langchain-core constraint conflict | Medium |
| 3 | LangSmith API key type not explained in UI | Low |
| 4 | Layered architecture not explained upfront | Medium |
| 5 | Eval + agent code mixed in quickstart examples | Medium |
