"""ACTION_SANDBOX: apply an action to a COPY of some state and report what would change.

sandbox_execute(action, state=None) understands four operations on a flat mapping:

  {"op": "set", "key": k, "value": v}          {"op": "delete", "key": k}
  {"op": "increment", "key": k, "by": n}       {"op": "append", "key": k, "value": v}

It returns the before and after of the key, and the whole state as it would be.
The caller's state object is never modified and nothing outside this call is
touched: `result` is always "simulated". An action without a known `op` is
returned as `unsupported` with no changes, never pretended to have run.
"""
import copy
import logging
from typing import Any, Dict

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("ACTION_SANDBOX")
OPS = ("set", "delete", "increment", "append")
_ABSENT = "<absent>"


class ACTION_SANDBOXAgent:
    def __init__(self):
        self.name = "ACTION_SANDBOX"

    def health_check(self):
        return kit.health(self.name)

    def sandbox_execute(self, action: Dict[str, Any], state: Dict[str, Any] = None) -> Dict[str, Any]:
        base = {"result": "simulated", "action": action, "changes": []}
        if not isinstance(action, dict) or (state is not None and not isinstance(state, dict)):
            return {**base, "status": "failed", "errors": ["action must be an object and state a mapping"]}
        op, key = action.get("op"), action.get("key")
        if not isinstance(op, str) or op not in OPS:
            return {**base, "status": "unsupported",
                    "reason": f"no known 'op' in the action; supported: {', '.join(OPS)}"}
        if not isinstance(key, str) or not key:
            return {**base, "status": "failed", "errors": ["key must be a non-empty string"]}
        after = copy.deepcopy(state or {})
        before = copy.deepcopy(after.get(key, _ABSENT))
        if op == "set":
            if "value" not in action:
                return {**base, "status": "failed", "errors": ["set needs a 'value'"]}
            after[key] = copy.deepcopy(action["value"])
        elif op == "delete":
            if key not in after:
                return {**base, "status": "failed", "errors": [f"cannot delete '{key}': not in the state"]}
            del after[key]
        elif op == "increment":
            by, current = kit.number(action.get("by", 1)), kit.number(after.get(key, 0))
            if by is None or current is None:
                return {**base, "status": "failed", "errors": ["increment needs a numeric 'by' and a numeric key"]}
            after[key] = after.get(key, 0) + action.get("by", 1)
        else:
            if "value" not in action or not isinstance(after.get(key, []), list):
                return {**base, "status": "failed", "errors": ["append needs a 'value' and a list (or absent) key"]}
            after[key] = after.get(key, []) + [copy.deepcopy(action["value"])]
        now = after.get(key, _ABSENT)
        return {**base, "status": "ok", "state_after": after,
                "changes": [] if now == before else [{"key": key, "before": before, "after": now}]}
