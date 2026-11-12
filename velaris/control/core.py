"""The Surface interface: observe, then act on an element of THAT observation.

An observation lists the elements an actor could use (ref, role, name, value). Its
snapshot_id is a hash of its whole content. Every action names an element ref and
carries the snapshot_id it was decided against; act() looks at the live state again and
refuses when the state is not the one the snapshot describes ("reject stale references").
The snapshot_id goes into the tool arguments, so the call hash a person approves covers
the exact screen the approver was shown.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

READ, UNDOABLE, COMPENSATABLE, IRREVERSIBLE = "read", "undoable", "compensatable", "irreversible"
CLASSES = (READ, UNDOABLE, COMPENSATABLE, IRREVERSIBLE)


class ControlError(RuntimeError):
    """A refusal. `code` is machine-readable; the message never echoes observed content."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


class StaleSnapshot(ControlError):
    pass


class Refused(ControlError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


@dataclass(frozen=True)
class Element:
    ref: str
    role: str
    name: str
    value: Optional[str] = None
    extra: Tuple[Tuple[str, str], ...] = ()          # href, disabled, secret ...

    def get(self, key: str, default: str = "") -> str:
        return dict(self.extra).get(key, default)


@dataclass(frozen=True)
class Observation:
    snapshot_id: str
    surface: str
    elements: Tuple[Element, ...]
    text: str = ""
    context: str = ""                                # url, jail name, ... never a host path

    def element(self, ref: Any) -> Optional[Element]:
        return next((e for e in self.elements if e.ref == ref), None) if isinstance(ref, str) else None

    @property
    def digest(self) -> str:
        return self.snapshot_id

    def summary(self) -> Dict[str, Any]:
        """Ids and counts only: safe to keep in an audit trail."""
        return {"snapshot_id": self.snapshot_id, "surface": self.surface, "elements": len(self.elements),
                "text_chars": len(self.text)}


@dataclass(frozen=True)
class Action:
    kind: str
    ref: str
    value: Optional[str] = None
    to: Optional[str] = None


@dataclass
class ActResult:
    ok: bool
    output: str = ""
    status: str = "done"
    data: Dict[str, Any] = field(default_factory=dict)


class Surface:
    """Subclasses supply _raw(), classify(), _do() and (if they mutate) undo_handlers()."""

    kind = "surface"

    def _raw(self) -> Tuple[List[Dict[str, Any]], str, str]:
        """(elements as dicts with role, name, value?, extra?; text; context), in a stable order."""
        raise NotImplementedError

    def classify(self, action: Action, el: Element) -> str:
        """The reversibility class of this action on this element. Raises Refused if it cannot be done at all."""
        raise NotImplementedError

    def _do(self, action: Action, el: Element, obs: Observation) -> ActResult:
        raise NotImplementedError

    def undo_handlers(self) -> Dict[str, Callable[[Dict[str, Any]], str]]:
        return {}

    def observe(self) -> Observation:
        raw, text, context = self._raw()
        els = tuple(Element(f"e{i}", str(d["role"]), str(d.get("name", "")), d.get("value"),
                            tuple(sorted((str(k), str(v)) for k, v in (d.get("extra") or {}).items())))
                    for i, d in enumerate(raw, start=1))
        body = canon([self.kind, [[e.role, e.name, e.value, e.extra] for e in els], text, context])
        return Observation(hashlib.sha256(body.encode()).hexdigest()[:24], self.kind, els, text, context)

    def act(self, action: Action, snapshot_id: Optional[str]) -> ActResult:
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise StaleSnapshot("missing_snapshot", "an action must carry the snapshot_id it was decided against")
        obs = self.observe()
        if obs.snapshot_id != snapshot_id:
            raise StaleSnapshot("stale_snapshot", "the interface changed since that observation; observe again")
        el = obs.element(action.ref)
        if el is None:
            raise Refused("unknown_ref", "no such element in that observation")
        self.classify(action, el)               # a surface never acts on what it would not classify (jail, hosts, allow-list)
        return self._do(action, el, obs)
