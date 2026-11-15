# EOF_GATEWAY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/EOF_GATEWAY/main.py` (144 lines)

## Purpose

EOF_GATEWAY: a durable message hand-off between agents.

route(dst, payload, via=None) checks the message and appends it to the
destination's inbox (one owner-only file per destination under this agent's
state directory); receive(dst) returns the messages not yet taken. It delivers
to an inbox and nothing more: it does not call the destination agent.

Who sent it is never a free-text argument. Every message records:
  on_behalf_of   the current caller (velaris.core.access); routing without one is refused.
  src            the agent that sent it when an agent routes for a person: that agent
                 passes itself (`via=self`) and its name is read from where its class is
                 defined (departments/<dept>/<AGENT>/main.py), so it cannot claim another
                 agent's name. A direct call (no `via`) sends as the caller: src is the
                 caller's id.
  sender         "agent" or "caller", saying which of the two src is.
Limit: in-process code can construct any agent and route through it; what it cannot do
is make the message say it came from an agent it did not use, or from someone other
than the authenticated caller.

Checks, all deterministic: both ends are agents that exist, the payload is a
JSON object within a size limit, and no text in it looks like an attempt to
instruct a model (velaris.intel.guard). Every decision is written to the
trace without the payload.

receive(dst) is bound to the caller (velaris.core.access): only the agent whose
name is `dst` may take its messages, and `dst` must be a known agent name (no path
separators), so it can never name a file outside this agent's directory.

## Class `EOF_GATEWAYAgent`

- `__init__()`
- `health_check()`
- `route(dst, payload, via)` — Queue `payload` for `dst` as the current caller, through agent `via` if given (see the module docstring).
- `receive(dst, limit)` — Messages queued for `dst` that were not returned before, oldest first. Only `dst` itself may ask.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents`
- `velaris.core.access`
- `velaris.intel`
- `velaris.intel.paths`

## State and configuration

- state file: `<VELARIS_DATA>/agents/EOF_GATEWAY/cursors.json`

## Called by

- **other agents:** `CORE_CONVERGENCE`, `EOF_CORE`, `EOF_POLICY`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_layer31_eof.py`
