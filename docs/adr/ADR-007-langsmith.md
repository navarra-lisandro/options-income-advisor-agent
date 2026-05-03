# ADR-007 — LangSmith: Observability and Evaluation Strategy

**Date:** 2026-05-02
**Updated:** 2026-05-03
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

The project required running a LangSmith evaluation
experiment using both the SDK and the UI. Beyond the evaluation
requirement, LangSmith also serves as the observability layer for
the agent, providing tracing, cost tracking, and performance
monitoring out of the box.

This ADR documents the full LangSmith strategy: how I use it for
observability, how I designed the evaluation dataset, how I
implemented the evaluators, and why certain decisions were made.

---

## Decision

I use LangSmith for two distinct purposes:

1. **Observability** — automatic tracing of every agent run,
   providing the four golden signals plus cost tracking.
2. **Offline evaluation** — a fixed dataset of 5 examples evaluated
   against the agent using structured field matching and
   LLM-as-a-judge scoring.

---

## LangSmith as Observability Layer

LangSmith tracing was confirmed working on Day 2 of development.
A single agent run produced the following trace:

```
LangGraph run — 30.91s total, $0.0229
  load_portfolio        0.00s
  screen_aristocrat     0.00s  (4 tool calls)
  screen_earnings       0.00s  (4 tool calls)
  screen_dividends      0.00s  (4 tool calls)
  generate_report       30.85s (Claude call — 2.4K tokens)
```

### Four Golden Signals Mapped to LangSmith

**Latency:**
Node execution times are visible per run. `generate_report` is
the expensive step at ~30s — the LLM call dominates. All screening
nodes complete in under 0.01s — deterministic tool calls are fast.

**Errors:**
Failed runs appear as red traces in LangSmith UI. Tool errors,
LLM failures, and node exceptions are all captured with full
stack traces and input/output context.

**Traffic:**
Run frequency and usage patterns are tracked automatically.
The LangSmith dashboard shows runs per day, experiment history,
and project-level aggregates.

**Saturation:**
Token usage is tracked per run (input tokens, output tokens,
total tokens). Approaching rate limits would be visible as
increasing latency in the trace timeline.

**Cost:**
LangSmith tracks cost per run automatically.
- Cost per run: $0.0229
- Projected monthly cost at 30 runs/day: ~$0.69
- Evaluation experiment (5 examples, 2 evaluators): $0.0529

**Logs:**
Full tool input/output is inspectable per run. The complete 
message history between Claude and its tools is visible in 
the LangSmith trace — equivalent to structured application 
logs with full context preserved.

### Node Granularity Validates Observability Design

The decision to use one node per screen (ADR-006) pays dividends
in LangSmith. Each screening step appears as a discrete trace
entry, and slow or incorrect screens are immediately visible without
digging through aggregated logs. This is the same principle as
breaking a monolithic service into discrete components for
independent monitoring.

---

## Application-Level Logging

LangSmith provides APM-level distributed tracing but does not
replace application-level logging. Python's built-in `logging`
module was added to complement LangSmith tracing with lifecycle
events that exist outside the request scope.

### What Was Added

```python
# agent/graph.py — graph lifecycle events
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
```

Each node in `agent/nodes.py` has its own logger:

```
INFO  level: node start/completion, position counts
DEBUG level: per-ticker screening results (troubleshooting)
```

### Log Output Example

```
2026-05-03 09:41:55 [INFO] __main__: Starting options income advisor agent
2026-05-03 09:41:55 [INFO] __main__: build_graph: graph compiled with 6 nodes
2026-05-03 09:41:55 [INFO] agent.nodes: load_portfolio: loaded 5 positions
2026-05-03 09:41:55 [INFO] agent.nodes: screen_aristocrat: screening 5 positions
2026-05-03 09:41:55 [INFO] agent.nodes: screen_aristocrat: complete
2026-05-03 09:42:34 [INFO] __main__: route_after_report: 3 candidate(s) -> has_candidates
2026-05-03 09:42:34 [INFO] __main__: Graph execution complete
```

### Logging vs Tracing — The Distinction

```
LangSmith tracing:      APM-level: node spans, tool calls,
                        LLM inputs/outputs, latency, cost.
                        Request-scoped, structured data.

Python logging:         Application-level: bootstrapping,
                        startup events, node lifecycle,
                        routing decisions, debug output.
                        Outside the request scope.
```

Both are needed in production. LangSmith cannot capture what
happens before the first graph node runs, therefore Python 
logging fills that gap.

### LANGCHAIN_VERBOSE Setting

The `.env.example` includes `LANGCHAIN_VERBOSE=false`. Setting
this to `true` enables detailed LangChain internal debug logs,
useful for troubleshooting but too verbose for normal operation.

---

## LangSmith Applications — Decision Not to Use

While doing experiment analysis, I explored the LangSmith
"Applications" feature visible in the UI sidebar. This feature
groups traces, datasets, and experiments under a named application
context. After investigation, I chose not to use it for this project.

### What LangSmith Applications Require

Per the official documentation, deploying to LangSmith Applications
requires a `langgraph.json` configuration file that specifies the
graph entry point and dependencies. This is designed for agents
deployed to LangSmith's hosting infrastructure, but not locally run
agents.

### The Migration Path Problem

Additionally, when attempting to associate the existing tracing 
project `options-income-advisor-agent` with a newly created 
Application, the LangSmith UI returned:

```
"A tracing project with this name already exists.
Please use a different name."
```

There does not appear to be a way to link an existing project 
to an Application. The Application requires a new, dedicated 
project, and that would mean splitting all historical traces, 
experiments, and evaluation history done so far.

See `docs/images/langsmith-application-project-exists-error.png`
for a screenshot of this error.

### Decision

I chose to keep all traces, experiments, and evaluation history
in the existing workspace-level project rather than split history
across two projects. The current setup is fully functional for
the purposes of this project.

This limitation is documented in `FRICTION_LOG.md` item #10.

**Future consideration:** Create the LangSmith Application and
associated project at the **start of a new project** and before \
any traces are generated. The migration path does not exist, so 
the correct order is Application first, tracing second.

---

## Offline vs Online Evaluation

I implement **offline evaluation** — the agent is evaluated against
a fixed dataset of known inputs and expected outputs before
deployment. This is analogous to QA pre-production testing in
traditional software development.

```
Offline evaluation:
  Fixed dataset + known expected outputs
  Controlled, repeatable, comparable across runs
  "How well does it perform on known cases?"

Online evaluation (future consideration):
  Production traces scored as they arrive
  "How is it performing right now in production?"
```

Offline evaluation was chosen because it directly satisfies the
take-home requirement and is the appropriate starting point for
a new agent. Online evaluation is a natural next iteration once
the agent is deployed.

---

## Evaluation Dataset Design

### Dataset: options-income-advisor-eval-v1

5 examples were chosen to cover the full outcome spectrum:

| Ticker | Expected Outcome | Key Scenario |
|--------|-----------------|--------------|
| MCD | RECOMMEND | Clean pass — all three screens clear |
| JNJ | PROCEED WITH CAUTION | Dividend overlap within expiry window |
| KO | PROCEED WITH CAUTION | Dividend overlap, more urgent than JNJ |
| NVDA | AVOID | Not an aristocrat + earnings CAUTION |
| TSLA | AVOID | Not an aristocrat + earnings FAIL (hard stop) |

### Why 5 Examples

The LangSmith evaluation documentation recommends starting with
5-10 manually curated examples. 5 examples covering the full
RECOMMEND/CAUTION/AVOID spectrum was judged more intentional
than padding the dataset with redundant cases.

### Synthetic Variants — Future Consideration

Systematic variants (same ticker, modified dates to force specific
thresholds) were considered but not implemented. For example,
an aristocrat position with earnings in 3 days would test whether
the FAIL screen overrides aristocrat status. This is the natural
next iteration for a production eval suite.

### Dataset Versioning

The dataset is named `options-income-advisor-eval-v1`. Version
suffixes allow future dataset evolution without losing historical
experiment comparisons. When the dataset changes materially,
the version is bumped and old experiments remain comparable.

### Date Stability

Synthetic dates must remain stable across the full evaluation
window. A lesson learned during development: TSLA's earnings date
was initially set too close to the current date, causing the
earnings screen to shift from FAIL to CAUTION as days elapsed.

All dates were verified to produce stable screening results
from development through the presentation date (May 8, 2026).

### Dataset Coupling to portfolio.json

The eval dataset inputs describe the scenario but the agent reads
position data from `portfolio.json` via tools — not from the
dataset inputs directly. This means `portfolio.json` is the single
source of truth for both the agent and the eval.

Future consideration: inject position data directly into tools
via state rather than reading from a file, making the agent
truly stateless and the eval dataset fully self-contained.

---

## Evaluator Design

Two complementary evaluation approaches are used together:

### 1. Structured Field Matching

Validates screening logic deterministically. Checks that
`aristocrat_screen`, `earnings_screen`, and `dividend_screen`
match expected PASS/CAUTION/FAIL values exactly. Binary: 0 or 1.

```python
checks = [
    actual.get("aristocrat_screen") == expected.get("aristocrat_screen"),
    actual.get("earnings_screen") == expected.get("earnings_screen"),
    actual.get("dividend_screen") == expected.get("dividend_screen"),
]
score = 1 if all(checks) else 0
```

### 2. LLM-as-a-Judge

Validates reasoning quality using Claude as the scoring model.
Checks whether the final recommendation correctly identifies the
key risk, explains it accurately, and provides actionable guidance.
Scored 0-10, normalized to 0-1 for LangSmith compatibility.

### Why Both Are Needed

```
Structured field matching alone:
  "Screens were correct but recommendation was incoherent"
  -> passes eval, fails in production

LLM-as-a-judge alone:
  "Reasoning was eloquent but agent said RECOMMEND
   when it should say AVOID"
  -> passes eval, gives wrong advice

Together:
  Screens correct AND reasoning sound
  -> meaningful, trustworthy score
```

---

## Target Function — graph.invoke() as Evaluation Target

The LangSmith `evaluate()` function accepts a target function
that takes a dict and returns a dict. The `run_agent()` wrapper
follows the officially recommended LangSmith pattern:

Reference:
  https://docs.smith.langchain.com/evaluation/how_to_guides/define_target

```python
graph = build_graph()  # built once at module level

def run_agent(inputs: dict) -> dict:
    result = graph.invoke({
        "positions": [inputs],
        "screenings": [],
    })
    return {...}  # extracted screening results
```

The graph is built once outside `run_agent()` to avoid
rebuilding on every evaluation example — a performance
optimization for datasets with many examples.

---

## CI/CD Integration — Manual Eval by Design

Evaluation runs are **intentionally excluded from CI**:

```
CI runs automatically:
  make lint    -> ruff, no API keys needed, free
  make test    -> pytest, no API keys needed, free

Manual runs only:
  make run     -> requires ANTHROPIC_API_KEY, costs money
  make dataset -> requires LANGCHAIN_API_KEY
  make eval    -> requires both keys, ~$0.25/run
```

Running `make eval` in CI would:
- Cost money on every push (~$0.25 per PR)
- Clutter LangSmith experiment history with non-deliberate runs
- Require API keys stored as CI secrets (security surface area)

Eval runs are a deliberate human decision, not an automated gate.

**Future consideration:** A scheduled nightly GitHub Actions workflow
could run `make eval` automatically using secrets stored in the
CI environment. This would be the appropriate path once the agent 
is in production and regression detection is needed.

---

## Lessons Learned

**1. Parameterize agent inputs early:**
The agent was initially built reading from a hardcoded file.
Refactoring `load_portfolio()` to accept injected positions
was required before evaluation could work meaningfully.
Earlier guidance in LangGraph docs toward parameterized inputs
would have surfaced this requirement sooner.

**2. Synthetic dates become stale:**
Absolute dates in eval datasets drift relative to screening
thresholds as time passes. Dates should be set with enough
buffer to remain stable across the full evaluation window,
or expressed relative to a fixed reference date.

**3. to_pandas() requires pandas (undocumented):**
LangSmith's `EvaluationResults.to_pandas()` method requires
pandas to be installed separately. This is not documented in
the LangSmith evaluation guides. The call was wrapped in a
try/except block which prevented a hard crash, but a new user
without that safety net would encounter a confusing
`ModuleNotFoundError`. Pandas was added explicitly to
`pyproject.toml` as a result.

**4. Create LangSmith Application before tracing:**
The LangSmith Applications feature cannot link existing tracing
projects. If using Applications, create the Application and its
associated project first — before running any traces. The
migration path does not exist once traces have been generated
under a workspace-level project.

---

## Consequences

- **Positive:** Full observability out of the box — tracing, cost
  tracking, and experiment history with zero additional code.
- **Positive:** Python logging complements LangSmith with
  application-level lifecycle events outside the request scope.
- **Positive:** Evaluation results are comparable across runs via
  dataset versioning and experiment prefixes.
- **Positive:** Two-evaluator approach catches both logic errors
  and reasoning quality gaps independently.
- **Neutral:** Eval runs are manual which is appropriate for this
  scope, but a scheduled CI eval is the natural next step.
- **Neutral:** LangSmith Applications are not used, and all 
  observability lives at workspace project level. Fully functional 
  for this scope.
- **Watch:** Dataset coupling to portfolio.json means data changes
  affect eval results silently. Future refactor should make the
  eval dataset fully self-contained.

---

## References

- [LangSmith evaluation concepts](https://docs.smith.langchain.com/evaluation/concepts)
- [How to evaluate a LangGraph graph](https://docs.smith.langchain.com/evaluation/how_to_guides/langgraph)
- [How to define a target function](https://docs.smith.langchain.com/evaluation/how_to_guides/define_target)
- [LLM-as-a-judge evaluator](https://docs.smith.langchain.com/evaluation/how_to_guides/llm_as_judge)
- [Python SDK evaluate() reference](https://docs.smith.langchain.com/reference/python/evaluation)
- [LangSmith application structure](https://docs.langchain.com/langsmith/application-structure)
- [LangSmith tracing with LangChain](https://docs.langchain.com/langsmith/trace-with-langchain)
- See also: FRICTION_LOG.md items #6, #7, #8, #9, #10
- See also: docs/images/langsmith-application-project-exists-error.png
