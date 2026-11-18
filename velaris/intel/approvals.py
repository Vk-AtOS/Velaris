"""ONE audit helper for every approval mechanism (KAN-27 defect 11).

Velaris has five places where a person (or Prime) approves something: velaris.intel.flow (the run loop), VCAS_CORE, AAE_RUNTIME,
the PRIME agent's grants and HUMAN_APPROVAL_WORKFLOW. Each kept its own state and wrote its own differently shaped trace entry
(or none). They still keep their own state, but every request, decision, execution, refusal and revocation is now written by
`audit()`, so the trace holds ONE uniform record of the approval trail:

    payload = {system, event, request_id, subject_sha256, by, decision, note, ...the mechanism's own fields}

  system      FLOW | VCAS_CORE | AAE_RUNTIME | PRIME | HUMAN_APPROVAL_WORKFLOW | VCAS_AUTOPILOT
  event       requested | decided | executed | refused | granted | revoked | cleared | ...
  request_id  the thing being decided (run id, task id, action id, grant id, request id)
  subject     what exactly is approved; stored only as its sha256 (never the content)
  by          the person who acted; decision  approve | reject | allow | deny | needs_approval (or None)

`trace_actor` / `trace_action` keep the trace entry's own actor and action where another module VERIFIES that entry by its
shape (PRIME's prime.decision and VCAS_CORE's decision are looked up by hash in aicore_b_authz.approval_proven). Like
trace.append, audit() raises when the trace cannot be written: an approval that cannot be recorded must not happen.
`trail()` reads the uniform record back across all mechanisms.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterator, Optional

from velaris.intel import trace

SYSTEMS = ("FLOW", "VCAS_CORE", "VCAS_AUTOPILOT", "AAE_RUNTIME", "PRIME", "HUMAN_APPROVAL_WORKFLOW")


def digest(subject: Any) -> Optional[str]:
    """sha256 of the subject's canonical JSON, or None when there is none."""
    if subject is None:
        return None
    return hashlib.sha256(json.dumps(subject, sort_keys=True, default=str).encode()).hexdigest()


def audit(system: str, event: str, *, request_id: Any = "", subject: Any = None, by: str = "", decision: Optional[str] = None,
          note: str = "", trace_actor: Optional[str] = None, trace_action: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
    """Write one approval-trail entry; returns the trace entry (its `hash` is what other modules may cite)."""
    if system not in SYSTEMS:
        raise ValueError(f"unknown approval system {system!r}")
    uniform = {"system": system, "event": event, "request_id": str(request_id)[:128], "subject_sha256": digest(subject),
               "by": str(by or "")[:128], "decision": decision, "note": str(note or "")[:300]}
    return trace.append(trace_actor or "approval", trace_action or f"{system}.{event}", {**extra, **uniform})


def trail(*, system: Optional[str] = None, request_id: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    """The payloads of the approval trail, oldest first, optionally of one system or one request."""
    for e in trace.entries():
        p = e.get("payload") or {}
        if p.get("system") in SYSTEMS and p.get("event") and (system is None or p["system"] == system) \
                and (request_id is None or p.get("request_id") == str(request_id)):
            yield p
