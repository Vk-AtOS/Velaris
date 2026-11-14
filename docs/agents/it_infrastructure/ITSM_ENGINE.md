# ITSM_ENGINE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/ITSM_ENGINE/main.py` (218 lines)

## Purpose

ITSM_ENGINE: an IT ticket and incident store with priority, SLA clocks and an audit trail.

Priority is computed, never taken on trust from the reporter:

    score = IMPACT_WEIGHT[impact] + URGENCY_WEIGHT[urgency] + sum(HISTORY_WEIGHT[flag] for each true flag)
    P1 if score >= 900, P2 if >= 600, P3 if >= 300, else P4          (maximum 1400)

Each priority carries two targets (SLA_MINUTES): first response and resolution.
The response clock stops when the ticket is first assigned. The resolution clock
runs while the ticket is open and pauses while it is on hold; time on hold
extends the due time. States and allowed moves are in TRANSITIONS.

Every change is appended to the ticket's own history (who, when, from, to, note)
and to the hash-chained trace, so the record of a ticket cannot be quietly rewritten.
"Who" is the current caller (velaris.core.access): any authenticated person or service
may open and move tickets, nobody can do it anonymously, and a legacy `by` argument
must name that same caller.

## Class `Ticket`


## Class `ITSMEngine`

- `__init__()`
- `health_check()`
- `validate(t)`
- `assess(t)` — Computed priority and SLA targets for a ticket. Stores nothing.
- `open_ticket(t, by, now)`
- `transition(ticket_id, to, by, note, now)`
- `sla_status(ticket_id, now)` — Where both clocks stand: met, running (with seconds left), paused or breached.
- `get_ticket(ticket_id)`
- `list_tickets(state)` — Tickets (optionally in one state), most urgent first: priority, then earliest resolution due.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/ITSM_ENGINE/tickets.json`

## Called by

- **other agents:** `LYRA_VOICE_ENGINE`
- **platform modules:** `departments/_connectors/JIRA/atlassian.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_deployment_org.py`, `velaris/tests/test_dept_it_infrastructure_stubs_2.py`
