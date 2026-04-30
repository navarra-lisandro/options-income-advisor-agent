# ADR-003 — LLM Provider: Anthropic Claude over OpenAI

**Date:** 2026-04-30
**Status:** Accepted
**Author:** Lisandro Navarra

---

## Context

This project requires a large language model (LLM) to power the reasoning
core of the LangGraph agent. Because LangGraph is model-agnostic by design, the
LLM is simply a node in the graph, and swapping providers requires changing
exactly one line of code. The choice of provider is therefore a deliberate
preference decision, not an architectural constraint.

The two most common choices in the LangGraph ecosystem are OpenAI (GPT-4o)
and Anthropic (Claude). Both are fully supported by LangChain's abstraction
layer.

---

## Decision

We use **Anthropic Claude** (`claude-sonnet-4-5`) as the LLM provider,
accessed via the `langchain-anthropic` package.

---

## Rationale

- **LangChain abstraction makes this genuinely swappable:** The `@tool`
  decorator, `ToolNode`, tool binding, and all other LangChain primitives
  are model-agnostic. They work identically regardless of which LLM is
  underneath. Switching to GPT-4o in the future requires changing exactly
  one line:

  ```python
  # Current
  from langchain_anthropic import ChatAnthropic
  llm = ChatAnthropic(model="claude-sonnet-4-5")

  # If switching to OpenAI
  from langchain_openai import ChatOpenAI
  llm = ChatOpenAI(model="gpt-4o")
  ```

  This is not a lock-in decision.

- **Strong tool-calling support:** Claude has robust support for
  structured tool/function calling, which is central to the agent
  pattern this project demonstrates. Claude reliably interprets tool
  definitions from docstrings and parameter types.

- **Cost profile:** Claude Sonnet offers a strong balance of capability
  and cost for a development and evaluation workload. For a project of
  this scale, API spend is expected to be under $1.00 total.

- **Familiarity with the API:** Direct experience with the Anthropic
  API reduces the risk of provider-specific surprises during
  development and evaluation.

---

## Key Architectural Note

It is worth explicitly stating what this decision does *not* affect:

- `agent/tools.py` — model-agnostic, unchanged by provider choice
- `agent/state.py` — model-agnostic, unchanged by provider choice
- `agent/graph.py` — model-agnostic except for the one LLM instantiation line
- `evals/` — model-agnostic, evaluates output regardless of provider
- LangSmith tracing — works identically across all LangChain-supported providers

The LangGraph → LangChain → LLM Provider layered architecture ensures
that the provider choice is isolated to a single configuration concern.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|---|---|
| OpenAI GPT-4o | Viable — would require changing one line. No strong reason to prefer it here. |
| Google Gemini | Supported by LangChain but less battle-tested in the LangGraph ecosystem |
| Local model via Ollama | Interesting for cost/privacy, but adds infrastructure complexity inappropriate for this scope |

---

## Consequences

- **Positive:** Strong tool-calling capability supports the agent
  pattern cleanly.
- **Positive:** No architectural lock-in — provider is swappable
  in under 60 seconds.
- **Neutral:** Requires an Anthropic API key and a small credit
  purchase (~$5) to run. Documented in README.
- **Watch:** Model version (`claude-sonnet-4-5`) should be reviewed
  periodically as Anthropic releases newer versions.

---

## References

- [langchain-anthropic documentation](https://python.langchain.com/docs/integrations/chat/anthropic/)
- [Anthropic API documentation](https://docs.anthropic.com)
- [LangGraph model-agnostic design](https://langchain-ai.github.io/langgraph/)
- See also: `FRICTION_LOG.md` Friction #4 — Layered architecture
  not explained upfront in LangGraph docs
