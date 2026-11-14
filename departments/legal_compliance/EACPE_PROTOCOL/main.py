"""EACPE_PROTOCOL: did a case follow its required procedure?

A protocol is an ordered list of required steps, for example change management:

    [{"step": "request"}, {"step": "review", "distinct_from": ["request"]},
     {"step": "approve", "distinct_from": ["request"]}, {"step": "execute"}, {"step": "verify"}]

evaluate_protocol({"protocol": name, "events": [{"step", "actor", "ts"}, ...]})
checks, deterministically:

  missing        every required step occurred
  order          each step's first occurrence comes after the previous step's
  segregation    a step marked distinct_from was done by someone other than the
                 actor(s) of the named earlier steps (four-eyes rule)
  unknown        events whose step is not in the protocol are reported

protocol_safe is True only when the protocol exists and there are no findings.
Protocols are stored on disk and can be redefined; each result names the
protocol version it was checked against.
"""
from __future__ import annotations

from typing import Any, Dict, List

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import invalid, ok
from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "EACPE_PROTOCOL"


class EACPE_PROTOCOLAgent:
    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "protocols.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def define(self, protocol: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not is_name(protocol) or not isinstance(steps, list) or not steps:
            return invalid("protocol must be a name and steps a non-empty list")
        seen: List[str] = []
        for s in steps:
            if not isinstance(s, dict) or not is_name(s.get("step")) or s["step"] in seen or set(s) - {"step", "distinct_from"}:
                return invalid("each step is {'step': unique name, 'distinct_from': [earlier steps]}")
            earlier = s.get("distinct_from", [])
            if not isinstance(earlier, list) or not all(e in seen for e in earlier):
                return invalid(f"{s['step']}: distinct_from may only name earlier steps")
            seen.append(s["step"])

        # The four-eyes rules live here: only a governance admin may redefine them, and each change is traced.
        _, refused = check_caller(NAME, "define", {"protocol": protocol, "steps": [s["step"] for s in steps]},
                                  roles=GOVERNANCE_ADMINS)
        if refused:
            return refused

        def put(data: Dict[str, Any]) -> int:
            entry = data.setdefault("protocols", {}).setdefault(protocol, {"version": 0})
            entry.update(version=entry["version"] + 1, steps=steps)
            return entry["version"]
        return ok(protocol=protocol, version=self._state.update(put))

    def evaluate_protocol(self, data: dict) -> Dict[str, Any]:
        def unsafe(status: str, reason: str, findings: List[Dict[str, str]]) -> Dict[str, Any]:
            return {"protocol_safe": False, "meta": data, "status": status, "reason": reason, "findings": findings}
        if not isinstance(data, dict) or not isinstance(data.get("protocol"), str) or not isinstance(data.get("events"), list):
            return unsafe("invalid_input", "need {'protocol': name, 'events': [...]}", [])
        events = data["events"]
        if not all(isinstance(e, dict) and is_name(e.get("step")) and is_name(e.get("actor")) and is_number(e.get("ts"), 0)
                   for e in events):
            return unsafe("invalid_input", "each event needs step, actor and a numeric ts", [])
        proto = self._state.load().get("protocols", {}).get(data["protocol"])
        if proto is None:
            return unsafe("unknown_protocol", "no protocol with this name is defined", [])
        events = sorted(events, key=lambda e: e["ts"])
        first = {}
        actors: Dict[str, set] = {}
        for e in events:
            first.setdefault(e["step"], e["ts"])
            actors.setdefault(e["step"], set()).add(e["actor"])
        findings: List[Dict[str, str]] = []
        previous = None
        for s in proto["steps"]:
            name = s["step"]
            if name not in first:
                findings.append({"check": "missing", "step": name, "detail": f"{name} never happened"})
                continue
            if previous is not None and previous in first and first[name] < first[previous]:
                findings.append({"check": "order", "step": name, "detail": f"{name} happened before {previous}"})
            for earlier in s.get("distinct_from", []):
                shared = actors[name] & actors.get(earlier, set())
                if shared:
                    findings.append({"check": "segregation", "step": name,
                                     "detail": f"{', '.join(sorted(shared))} did both {earlier} and {name}"})
            previous = name
        known = {s["step"] for s in proto["steps"]}
        findings += [{"check": "unknown", "step": st, "detail": f"{st} is not part of the protocol"}
                     for st in sorted(set(first) - known)]
        return {"protocol_safe": not findings, "meta": data, "status": "ok", "protocol": data["protocol"],
                "version": proto["version"], "findings": findings}
