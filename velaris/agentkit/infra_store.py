"""Audit and redaction helpers for the infrastructure, memory, security and compliance agents.

  audit(...)            one entry in the process-wide hash-chained trace (velaris.intel.trace).
  redact_json(obj)      mask secrets and personal identifiers in every string of a JSON value.
  MAY_LEAVE_MACHINE     the only sensitivity labels allowed to leave this machine.

Results, input checks and durable state live in velaris.agentkit.results, .checks and .state.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from velaris.intel import guard, trace

logger = logging.getLogger("velaris.agentkit.infra")
# The only sensitivity labels allowed to leave this machine (LOCAL_ROUTER, CLOUD_HANDOFF_CONTROLLER).
# Anything else - "restricted", a typo, or no label at all - stays local.
MAY_LEAVE_MACHINE = ("public", "internal")


def audit(actor: str, action: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Append one event to the hash-chained trace. Returns its hash, or "" if it could not be written.

    Agents that authorise something treat "" as a reason to deny: an unrecorded approval must not stand.
    """
    try:
        return trace.append(actor, action, payload or {})["hash"]
    except (OSError, ValueError, TypeError) as e:
        logger.warning("%s could not record %s in the trace: %s", actor, action, e)
        return ""


def redact_json(obj: Any) -> Any:
    """A copy of a JSON value with secrets and personal identifiers masked in every string."""
    if isinstance(obj, str):
        return guard.redact(obj)[0]
    if isinstance(obj, list):
        return [redact_json(v) for v in obj]
    if isinstance(obj, dict):
        return {k: redact_json(v) for k, v in obj.items()}
    return obj
