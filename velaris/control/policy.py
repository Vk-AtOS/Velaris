"""Per-task action schema and the verdict for one proposed action.

The verdict comes from code, from four things: the task's schema, the observation the action
was decided against, the surface's own classification of the action, and what can be undone.

  class of the action        verdict
  read                       allow
  undoable                   allow (the surface checkpoints before it changes anything)
  compensatable              allow if an inverse is registered for it, else needs_approval
  irreversible               needs_approval: a NAMED person decides (Prime gate or local approval)
  task asks for approval     needs_approval (e.g. submitting a form)
  anything else              deny: an action not in the task's schema, an element role or name
                             the schema does not name, a value the code did not expect, a stale
                             or missing snapshot, a refusal by the surface (jail, host list,
                             allow-list), an unknown class, any error while deciding

The schema is what stops a page or a file name from redirecting the agent: whatever text an
observed element holds, only the actions, roles, names and values the task declares can pass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Optional

from velaris.control.core import (CLASSES, COMPENSATABLE, IRREVERSIBLE, READ, Action, ControlError, Element,
                                  Observation, Surface)

ALLOW, APPROVE, DENY = "allow", "approve", "deny"
# check(action, element, expected) -> bool: code-computed expectations decide what values are acceptable
Check = Callable[[Action, Element, Any], bool]


@dataclass(frozen=True)
class ActionSpec:
    roles: FrozenSet[str]
    name_re: Optional[str] = None            # the element's name must match (fullmatch, case-insensitive)
    check: Optional[Check] = None
    approval: bool = False                   # always needs a named approver, whatever the class


@dataclass(frozen=True)
class Decision:
    verdict: str
    klass: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {"verdict": self.verdict, "class": self.klass, "reason": self.reason}


def deny(reason: str, klass: str = "unknown") -> Decision:
    return Decision(DENY, klass, reason)


def decide(actions: Dict[str, ActionSpec], surface: Surface, action: Action, obs: Observation, expected: Any) -> Decision:
    try:
        spec = actions.get(action.kind)
        if spec is None:
            return deny(f"'{action.kind}' is not an action of this task")
        el = obs.element(action.ref)
        if el is None:
            return deny("no such element in the observation")
        if el.role not in spec.roles:
            return deny(f"a {el.role} is not a target of '{action.kind}' in this task")
        if spec.name_re is not None and not re.fullmatch(spec.name_re, el.name, re.I):
            return deny("this element is not one the task names")
        if spec.check is not None and not spec.check(action, el, expected):
            return deny("the value or target is not what the task expects")
        klass = surface.classify(action, el)
        if klass not in CLASSES:
            return deny(f"unknown action class {klass!r}")
        if klass == COMPENSATABLE and action.kind not in surface.undo_handlers():
            return Decision(APPROVE, IRREVERSIBLE, "no inverse is registered, so it counts as irreversible")
        if klass == IRREVERSIBLE:
            return Decision(APPROVE, klass, "irreversible: a named person must approve")
        if spec.approval:
            return Decision(APPROVE, klass, "the task requires approval for this step")
        return Decision(ALLOW, klass, "within the task and reversible" if klass != READ else "a read")
    except ControlError as e:
        return deny(f"{e.code}: {str(e)[:160]}")
    except Exception as e:  # deciding failed: that is never an allow
        return deny(f"could not decide ({type(e).__name__})")
