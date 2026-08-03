# ADR-0004: AI agent orchestration — supervisor graph, LLM port, and agent scoping

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Quantix AI engineering

## Context

Milestone 4 needed to bring the twelve specialized agents described in
the product spec (data ingestion, profiling, cleaning, SQL generation,
Python analysis, visualization, forecasting, AutoML, recommendation,
executive report, dashboard builder, explainable AI) to life as an actual
multi-agent system, on top of milestone 3's dataset/connector layer.
Three design questions shaped the milestone: how does one supervisor
decide which of twelve agents to invoke without a fragile "parse the
model's free text for something routing-shaped" mechanism; how do twelve
agent types stay maintainable without twelve bespoke classes; and how
does a LangGraph graph — which wants to be a cheap, reusable, mostly
stateless object — get access to request-scoped dependencies like a
tenant's dataset storage.

## Decisions

**Routing is a forced tool call, not parsed free text.** The supervisor's
every turn ends in exactly one tool call — `route_to_agent` or `finish` —
via the Anthropic API's `tool_choice="any"`. This was chosen over having
the supervisor write a sentence and pattern-matching an agent name out of
it: forced tool-calling turns "did the model's routing decision parse" into
a non-issue, at the cost of one extra round-trip structure to define.
`route_to_agent`'s `agent_type` parameter is a JSON Schema `enum` of the
twelve valid values, so the model literally cannot request an invalid
routing target through the API contract (the code still defensively
handles it — see "unknown agent type" in `supervisor.py` — because
defense-in-depth is cheap and models are not infallible).

**Twelve agent types, three real node implementations.** Mirroring
ADR-0003's "consolidate variation behind a small number of real classes"
decision: `PromptedAgentNode` is one class parameterized by
`AgentConfig` (system prompt, routing description, whether it gets
dataset tools) and covers ten of the twelve agent types
(`infrastructure/agents/configs.py`). The two exceptions have genuinely
different execution models rather than "just a different prompt":
`AutoMLAgentNode` trains real scikit-learn models — the LLM's only
involvement is picking the target column via one tool-forced call, after
which cross-validated model selection, feature preparation, and
importance ranking are deterministic code, not an LLM guess dressed up as
one. `DataIngestionAgentNode` wraps milestone 3's existing, tested
`SyncDatasetUseCase.resync` rather than having an LLM reimplement
ingestion in text. A thirteenth agent type is meant to be a small,
localized change: a new `AgentType` member, either a new `AgentConfig`
entry or a new node class, and one registration in
`infrastructure/agents/graph.py`.

**Request-scoped dependencies flow through `RunnableConfig`, not node
closures.** The compiled LangGraph graph is built once, in
`core/container.py` — compiling a `StateGraph` has real cost, and every
node closure in it only captures the stateless `LLMClient`. But agent
nodes need request-scoped things too (a specific request's dataset
storage, the calling user's other use cases). Rather than rebuilding the
graph per request (simple, but throws away the point of compiling once)
or making the graph itself request-scoped (defeats the singleton), request
dependencies are packaged into an `AgentRunContext`
(`application/interfaces/agent_graph.py`) and passed at `ainvoke()` time
via LangGraph's own `config={"configurable": {...}}` mechanism — the
idiomatic LangGraph pattern for exactly this, and it keeps the graph a
true singleton.

**`AgentState` is a plain dataclass, not LangGraph's `TypedDict`, at the
port boundary.** `application/interfaces/agent_graph.py` defines
`AgentState`/`AgentTurn`/`AgentRunResult` as ordinary dataclasses — the
same treatment ADR-0003 gave `pyarrow.Table` as connector.py's lingua
franca. `infrastructure/agents/graph.py` defines its own `GraphState`
`TypedDict` (LangGraph's expected shape) and converts at the boundary
(`_to_agent_state`), so nothing outside `infrastructure.agents` needs to
know LangGraph's state representation exists, and `SendMessageUseCase`
can be tested against a scripted fake `AgentGraph` with zero LangGraph
dependency in the test.

**Agent failures degrade gracefully; they don't become HTTP errors.**
Every node implementation (`PromptedAgentNode`, `AutoMLAgentNode`,
`DataIngestionAgentNode`, `SupervisorNode`) catches its own exceptions
and returns a `FAILED` `AgentRunResult` (or, for the supervisor, a
graceful `finished=True` decision with an apologetic `final_response`)
rather than propagating. The consequence: `POST
/conversations/{id}/messages` essentially always returns 201 with
*something* to show the user, even when an agent errored out —
`AgentRun.status` and `error_message` carry the failure detail for
observability/debugging, and the domain exceptions in
`domain/exceptions/agents.py` (`AgentExecutionError`, `LLMProviderError`,
etc.) are registered in `exception_handlers.py` for completeness but are
not expected to reach it in normal operation, since they're caught
upstream by design.

**Tool-loop sandboxing is best-effort, not a hard boundary — documented,
not hidden.** `run_python_analysis` executes model-generated code via
`exec()` with a restricted builtins allowlist (`_SAFE_BUILTINS` in
`tools.py`) — no `import`, `open`, `eval`, or filesystem/network access
through the allowed names. This stops the obvious misuse paths but is not
a true security sandbox (a determined adversary with code-execution
primitives can often still find an escape from a restricted-`exec`
environment); a real boundary would need a subprocess or container with
its own resource limits. Scoped out of this milestone because the
practical risk here is a misbehaving *model*, not an adversarial one —
the user is asking their own conversational agent to analyze their own
data — but flagged explicitly as a follow-up before this is ever exposed
to less-trusted input.

**No streaming yet.** `SendMessageUseCase` runs the graph synchronously
end-to-end and returns the finished response in one HTTP round trip,
unlike milestone 3's Celery-backed large dataset syncs. A multi-agent
turn with several tool round-trips can take tens of seconds; a streaming
(SSE) response would improve perceived latency but requires restructuring
`SendMessageUseCase` and the LangGraph invocation around `astream()` /
`astream_events()` rather than `ainvoke()`, and figuring out how partial
agent output gets persisted if the client disconnects mid-stream. Called
out explicitly as the most valuable near-term follow-up rather than
silently shipped as if this were the final shape.

## Alternatives considered

- **A single mega-agent with all twelve capabilities as tools on one LLM
  loop, no supervisor** — rejected: one system prompt trying to describe
  twelve specialties produces worse per-task quality than a router handing
  off to focused prompts, and it forecloses ever parallelizing or
  independently rate-limiting specific agent types.
- **`langchain`'s higher-level agent abstractions instead of raw
  `LLMClient` + hand-rolled tool loop** — rejected for the same reason M2
  hand-rolled OAuth clients instead of pulling in `authlib`: the actual
  surface needed (one completion call, tool-calling, usage accounting) is
  small and well-understood, and owning it keeps the LLM provider
  genuinely swappable behind one narrow port rather than behind a large
  framework's abstractions.
- **Celery-backed conversation turns** (matching milestone 3's ingestion
  pattern) — rejected for now: a chat turn is expected to be
  human-interactive-latency, not a background job: users are watching for
  a reply, not polling a job ID. Revisited if/when turns can involve truly
  long-running work (e.g. a full AutoML hyperparameter search instead of
  today's two-candidate-model comparison).
- **Rebuilding the LangGraph graph per request** instead of the
  `RunnableConfig`-based singleton pattern — rejected: throws away the
  point of compiling a graph once, for no benefit once idiomatic
  request-scoped injection via `configurable` was available.

## Consequences

**Positive:** adding a thirteenth agent type is additive and small; the
supervisor's routing is structurally reliable (JSON Schema enum, not text
parsing); `SendMessageUseCase` and every node are unit-testable against
fakes with zero network calls; agent failures never take down a
conversation turn, only degrade it with a clear error trail in `AgentRun`.

**Negative:** no streaming means a multi-hop agent turn is a single long
HTTP wait from the client's perspective; the Python-analysis tool's
sandbox is explicitly not hardened against adversarial code, only
accidental misuse; `AutoMLAgentNode`'s feature engineering is
intentionally modest (numeric + low-cardinality categorical only, two
model families, k-fold CV for selection) — a real AutoML platform's
feature engineering and hyperparameter search are out of scope here;
`DataIngestionAgentNode` can only refresh a dataset already attached to
the conversation, not connect a brand-new data source from a chat
message (deliberate, for the credential-handling reasons in the module's
own docstring, but a real scoping limitation worth restating here).

**Follow-ups tracked for later milestones:** SSE streaming for assistant
replies; letting `DataIngestionAgentNode` choose among a tenant's
already-configured data sources by name (still no credentials in chat);
richer AutoML (hyperparameter search, more model families, proper
train/validation/test splits instead of CV-only selection); a real
Python-execution sandbox (subprocess/container isolation) before this tool
is ever exposed to less-trusted input; per-agent-type rate limiting and
cost budgets now that `AgentRun` is already recording token counts.
