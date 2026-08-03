# ADR-0007: Frontend chat interface

- **Status:** Accepted
- **Date:** 2026-08-03
- **Deciders:** Quantix AI engineering

## Context

Milestone 4 shipped the backend's multi-agent chat system: a `Conversation`
optionally scoped to a `Dataset`, a supervisor that routes each turn to
zero-or-more of twelve specialist agents, and `POST
/conversations/{id}/messages`, which runs that whole graph **synchronously**
and returns once it's done — no SSE, no websocket, no job-polling. ADR-0004
flagged streaming as a deliberate, documented follow-up rather than what
was built. Milestone 7 gives that system a UI: `/chat` (conversation list),
`/chat/new` (start one, optionally scoped to a ready dataset), and
`/chat/[id]` (the thread itself), following the same
`features/<domain>/{api,hooks}.ts` + `app/(app)/<domain>/...` split as
`features/connectors` (ADR-0006).

## Decisions

**The composer optimistically inserts the user's message, then waits.**
Because a turn can take tens of seconds with no incremental feedback from
the server, `useSendMessage` (`features/chat/hooks.ts`) appends the typed
message to the `messages` query cache in `onMutate` — via
`cancelQueries` + `setQueryData`, the standard TanStack Query optimistic-
update recipe — so the thread shows the user's own message immediately
instead of sitting empty. A `"Agent is working…"` indicator fills the gap
until the response lands. `onError` rolls the optimistic entry back and the
page restores the typed text into the composer, so a failed send doesn't
silently lose what was written.

**`onSuccess` invalidates and refetches rather than hand-patching the
cache**, matching the pattern ADR-0006 already established for
`useResyncDataset`/`useTestDataSource`. `SendMessageResponse` carries one
assistant message plus every `AgentRun` from that turn — refetching
`messages` and `agent-runs` is simpler than trying to merge that shape into
the existing arrays by hand, and it's also what replaces the optimistic
user message with its real server-assigned id.

**No streaming client was built.** No `EventSource`, no websocket, no
polling loop against a job id — `sendMessage` is a plain `authFetch` POST.
Building a streaming UI against a backend that doesn't stream would mean
throwing that work away (or worse, faking increments client-side) the
moment ADR-0004's `astream_events()` follow-up lands. The pending state
described above is the entire near-term answer to perceived latency.

**A dedicated "agent activity" panel surfaces `GET
.../agent-runs`, filtered to exclude the supervisor.** The supervisor's own
runs exist for backend observability but are never meant to be user-facing
(documented on the `AgentType` enum itself); the panel
(`features/chat/agent-activity-panel.tsx`) lists each specialist that ran,
its status, a one-line output summary, and latency. This is the one place
in the milestone-7 UI that goes beyond "send a message, see a reply" — it's
also the fastest way to see this app's core differentiator (a supervisor
routing to specialists) actually working, rather than a chat box that looks
like any other chat box.

**The "new conversation" dataset picker only lists datasets with `status
=== "ready"`.** A `pending`/`processing`/`failed` dataset has nothing
queryable yet; offering it in the picker would let a user scope a
conversation to a dataset the agents can't actually use. Consistent with
`useDatasetPreview`'s readiness gating from milestone 6.

**Enter sends, Shift+Enter inserts a newline** — the composer is a
multi-line `Textarea`, and this is the convention every chat product this
app resembles already trains users on. Handled with a `keydown` listener
rather than relying on `<form>` submission from a `Textarea` (which
`Enter` alone doesn't trigger).

## Alternatives considered

- **Poll `GET /conversations/{id}/messages` after sending, instead of an
  optimistic insert** — rejected: the user's own message would still be
  invisible until the *next* poll tick after the whole multi-hop agent turn
  finishes, which is strictly worse than showing it the instant they hit
  send, for no simplicity gain (the hook still needs `onSuccess`
  invalidation for the assistant's reply either way).
- **Build a minimal client-side "typing" animation that fakes incremental
  reveal of the final response** — rejected as actively misleading: it
  implies the backend is streaming when it isn't, and would need to be torn
  out (not extended) once real SSE streaming ships.
- **Skip the agent activity panel for this milestone** — considered, since
  the chat thread alone satisfies "send a message, get a reply." Kept in
  because the multi-agent routing is the product's core mechanism and
  ADR-0004 explicitly designed `AgentRun` as an observability record; not
  surfacing it anywhere in the UI would waste that.

## Consequences

**Positive:** the chat UI is honest about the backend's actual behavior
(blocking, multi-hop, non-streaming) rather than papering over it, so
there's nothing to unwind when streaming ships. The optimistic-update +
invalidate pattern is now used consistently across `features/connectors`
and `features/chat`, giving future feature modules one pattern to copy
rather than two.

**Negative:** a long-running turn with no streaming means the composer
stays disabled and the thread shows only a static "working" indicator for
however long the graph takes — acceptable for this milestone, but the
weakest part of the experience, and exactly what ADR-0004's streaming
follow-up would fix.

**Follow-ups tracked for later milestones:** SSE streaming end-to-end (see
ADR-0004) once `SendMessageUseCase` is restructured around
`astream_events()`; archiving/renaming a conversation (the backend has
`ConversationStatus.ARCHIVED` but no route to set it yet); a way to browse
or attach an existing dataset's schema inline in the composer instead of
only at conversation-creation time.
