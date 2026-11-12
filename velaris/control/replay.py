"""Record a human or approved run once; replay it with no model. Fails closed.

A recording is a list of steps: the action, the element it used found by LOCATOR (role + name +
which of the equally named ones), and expected-observation assertions: the structure of the screen
before the step (a fingerprint of the roles and names present) and what must hold after it (the
typed value is in the field, the screen has the structure it had). Replay observes, checks the
fingerprint, finds the element by locator, asks the policy, acts with the fresh snapshot_id and
checks the assertions. Anything that no longer matches stops the replay with `drift`; a step the
policy does not allow stops it with `denied` or `needs_approval` (re-run with `approved={index: name}`
once a named person approved that step). A replay never guesses, retries or "repairs" a step.
Values may hold {{placeholders}} filled from `params`; a missing placeholder stops the replay.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from velaris.control import policy
from velaris.control.core import Action, ControlError, Element, Observation, Surface, canon, sha

PolicyFn = Callable[[Action, Observation], policy.Decision]
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fingerprint(obs: Observation) -> str:
    return sha(canon(sorted((e.role, e.name) for e in obs.elements if e.role != "page")).encode())[:24]


@dataclass
class Step:
    kind: str
    role: str
    name: str
    nth: int
    count: int
    value: Optional[str]
    to: Optional[str]
    pre: str
    post: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Program:
    name: str
    surface: str
    steps: List[Step] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Program":
        d = json.loads(text)
        return cls(d["name"], d["surface"], [Step(**s) for s in d["steps"]])

    def parametrize(self, mapping: Dict[str, str]) -> "Program":
        """Replace recorded values by {{placeholders}}: mapping is {recorded value: placeholder name}."""
        for s in self.steps:
            if s.value in mapping:
                for a in s.post:
                    if a.get("value") == s.value:
                        a["value"] = "{{%s}}" % mapping[s.value]
                s.value = "{{%s}}" % mapping[s.value]
        return self


def default_policy(surface: Surface) -> PolicyFn:
    """Reads and undoable steps allowed, everything else needs approval, anything unclassifiable is denied."""
    def decide(action: Action, obs: Observation) -> policy.Decision:
        el = obs.element(action.ref)
        if el is None:
            return policy.deny("no such element")
        try:
            k = surface.classify(action, el)
        except ControlError as e:
            return policy.deny(f"{e.code}")
        ok = k in ("read", "undoable")
        return policy.Decision(policy.ALLOW if ok else policy.APPROVE, k, "replay policy")
    return decide


class Recorder:
    """Wraps a surface; every action it performs is recorded with its locator and assertions."""

    def __init__(self, surface: Surface, name: str) -> None:
        self.surface, self.program = surface, Program(name, surface.kind)

    def act(self, action: Action, snapshot_id: str) -> Any:
        pre = self.surface.observe()
        el = pre.element(action.ref)
        res = self.surface.act(action, snapshot_id)
        if el is None:
            return res
        same = [e for e in pre.elements if (e.role, e.name) == (el.role, el.name)]
        post = self.surface.observe()
        asserts: List[Dict[str, Any]] = [{"structure": fingerprint(post)}]
        if action.kind in ("fill", "select"):
            asserts.append({"role": el.role, "name": el.name, "value": action.value})
        self.program.steps.append(Step(action.kind, el.role, el.name, same.index(el), len(same), action.value, action.to,
                                       fingerprint(pre), asserts))
        return res


@dataclass
class ReplayResult:
    status: str                 # completed | drift | assertion_failed | denied | needs_approval | failed
    step: Optional[int] = None
    detail: str = ""
    done: int = 0


def _fill(text: Optional[str], params: Dict[str, str]) -> Optional[str]:
    if text is None:
        return None
    missing = [m for m in _PLACEHOLDER.findall(text) if m not in params]
    if missing:
        raise KeyError(missing[0])
    return _PLACEHOLDER.sub(lambda m: params[m.group(1)], text)


def replay(program: Program, surface: Surface, *, params: Optional[Dict[str, str]] = None,
           policy_fn: Optional[PolicyFn] = None, approved: Optional[Dict[int, str]] = None) -> ReplayResult:
    params, approved = params or {}, approved or {}
    decide = policy_fn or default_policy(surface)
    if program.surface != surface.kind:
        return ReplayResult("drift", None, "the recording is for another kind of surface")
    for i, step in enumerate(program.steps):
        obs = surface.observe()
        if fingerprint(obs) != step.pre:
            return ReplayResult("drift", i, "the screen does not have the recorded structure", i)
        matches: List[Element] = [e for e in obs.elements if (e.role, e.name) == (step.role, step.name)]
        if len(matches) != step.count or step.nth >= len(matches):
            return ReplayResult("drift", i, "the element can no longer be found by role and name", i)
        try:
            action = Action(step.kind, matches[step.nth].ref, _fill(step.value, params), _fill(step.to, params))
        except KeyError as e:
            return ReplayResult("failed", i, f"no value for placeholder {e.args[0]}", i)
        d = decide(action, obs)
        if d.verdict == policy.DENY:
            return ReplayResult("denied", i, d.reason, i)
        if d.verdict == policy.APPROVE and not str(approved.get(i, "")).strip():
            return ReplayResult("needs_approval", i, d.reason, i)
        try:
            surface.act(action, obs.snapshot_id)
        except ControlError as e:
            return ReplayResult("failed", i, e.code, i)
        post = surface.observe()
        for a in step.post:
            if "structure" in a and fingerprint(post) != a["structure"]:
                return ReplayResult("assertion_failed", i, "the screen after the step is not the recorded one", i + 1)
            if "role" in a:
                want = _fill(a["value"], params)
                if not any((e.role, e.name, e.value) == (a["role"], a["name"], want) for e in post.elements):
                    return ReplayResult("assertion_failed", i, "the field does not hold the expected value", i + 1)
    return ReplayResult("completed", None, "", len(program.steps))
