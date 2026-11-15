"""The tool registry as the harness sees it: ONE file, so switching to E3's registry (velaris/intel/tools.py) is a change here only.

A ToolSpec is one public agent method as a model may call it: name, agent, method, params (a small JSON schema),
side_effects ("none" = a read; "state" = it changes something), sensitivity, department. Same field names as E3's
ToolSpec, so `specs_for` can return theirs unchanged when it lands.

ponytail: the adapter DERIVES the specs from the agent class (signature + annotations) because velaris.intel.tools does
not exist yet (E3, branch r3/v_e3). When it lands: delete `_derive`, make `specs_for` call its `list(agent=...)`.
"""
from __future__ import annotations

import dataclasses
import inspect
import logging
import re
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from velaris.api.allowlist import METHODS, http_params, rule_for, READ

logger = logging.getLogger("velaris.harness")
SECRET_PARAM = re.compile(r"(^|_)(secret|password|passcode|passphrase|pin|token|api_?key|private_?key|credential)s?$")
INJECTED = frozenset({"llm", "fetcher", "search_fn", "handler", "handlers", "func", "fn", "sender", "callback", "clock", "registry", "engine"})
SKIP_METHODS = frozenset({"health_check", "health", "on_event"})
JSON_TYPES = ("string", "integer", "number", "boolean", "object", "array", "any")


@dataclass(frozen=True)
class ToolSpec:
    name: str                                   # "AGENT.method"
    agent: str
    method: str
    params: Dict[str, Dict[str, Any]] = field(default_factory=dict)    # name -> {"type", "required", "default"?}
    side_effects: str = "state"                 # "none" | "state": fail closed, unknown is "state"
    sensitivity: str = "restricted"
    department: str = ""
    doc: str = ""


def json_type(annotation: Any) -> str:
    """The JSON type an annotation asks for ("any" when unclear). Text based: annotations may be strings."""
    if annotation is inspect.Parameter.empty:
        return "any"
    t = getattr(annotation, "__name__", None) if isinstance(annotation, type) else str(annotation)
    t = (t or "").lower()
    for pattern, kind in ((r"dict|mapping", "object"), (r"list|sequence|tuple|set\b|iterable", "array"),
                          (r"\bbool", "boolean"), (r"\bfloat|decimal", "number"), (r"\bint\b|^int", "integer"),
                          (r"\bstr\b|^str", "string")):
        if re.search(pattern, t):
            return kind
    return "any"


def type_ok(kind: str, value: Any) -> bool:
    if kind == "any":
        return True
    if kind == "boolean":
        return isinstance(value, bool)
    if isinstance(value, bool):
        return False
    return {"string": isinstance(value, str), "integer": isinstance(value, int),
            "number": isinstance(value, (int, float)), "object": isinstance(value, dict),
            "array": isinstance(value, list)}[kind]


def params_of(fn: Any, actor: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Schema of the parameters a model may pass (never self/caller/the actor parameter code fills in)."""
    out: Dict[str, Dict[str, Any]] = {}
    objects = dataclass_params(fn)
    for p in http_params(fn):
        if p.name == actor or p.name in INJECTED or "Callable" in str(p.annotation):
            continue           # code fills the actor in; collaborators are wired by code, never chosen by a model
        spec: Dict[str, Any] = {"type": json_type(p.annotation), "required": p.default is p.empty}
        if p.name in objects:
            spec["type"], spec["fields"] = "object", {f.name: json_type(f.type) for f in dataclasses.fields(objects[p.name]) if f.init}
        if p.default is not p.empty and isinstance(p.default, (str, int, float, bool, type(None))):
            spec["default"] = p.default
        out[p.name] = spec
    return out


PLAIN_MODULES = frozenset({"builtins", "typing", "decimal", "datetime", "collections", "collections.abc", "pathlib", "uuid"})


def object_param(fn: Any) -> Optional[str]:
    """Name of a parameter that must be an object of a class defined by the agent (a dataclass, a profile): JSON cannot carry it."""
    try:
        hints = typing.get_type_hints(fn)
    except Exception as e:  # unresolvable forward references: judged by the text of the annotation instead
        logger.debug("type hints of %s unresolved: %s", getattr(fn, "__name__", fn), e)
        hints = {}
    for p in http_params(fn):
        ann = hints.get(p.name, p.annotation)
        if p.default is p.empty and ann is not p.empty and isinstance(ann, type) and ann.__module__ not in PLAIN_MODULES and not dataclasses.is_dataclass(ann):
            return p.name
    return None


def dataclass_params(fn: Any) -> Dict[str, type]:
    """Parameters annotated with a dataclass: the model writes them as a JSON object and the harness builds the instance."""
    try:
        hints = typing.get_type_hints(fn)
    except Exception as e:  # unresolvable forward references
        logger.debug("type hints of %s unresolved: %s", getattr(fn, "__name__", fn), e)
        return {}
    return {p.name: hints[p.name] for p in http_params(fn)
            if isinstance(hints.get(p.name), type) and dataclasses.is_dataclass(hints[p.name])}


def build_object(cls: type, value: Any) -> Any:
    """cls(**value) after checking the keys: unknown or missing fields are a ValueError naming them."""
    if not isinstance(value, dict):
        raise ValueError(f"a {cls.__name__} must be a JSON object")
    fields = {f.name: f for f in dataclasses.fields(cls) if f.init}
    unknown = sorted(set(value) - set(fields))
    missing = sorted(n for n, f in fields.items() if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
                     and n not in value)
    if unknown or missing:
        raise ValueError(f"{cls.__name__} has the fields {sorted(fields)}; unknown {unknown}, missing {missing}")
    return cls(**value)


def exposable(fn: Any) -> Optional[str]:
    """None when a model can call this method; else why not (a required callable or object cannot be written as JSON)."""
    custom = object_param(fn)
    if custom:
        return f"required parameter '{custom}' is an object of the agent's own class, which JSON cannot carry"
    for p in http_params(fn):
        if p.default is p.empty and (p.name in INJECTED or "Callable" in str(p.annotation)):
            return f"required parameter '{p.name}' is a collaborator or callable, wired by code"
        if SECRET_PARAM.search(p.name):
            return f"parameter '{p.name}' is a secret; it would pass through the model"
    return None


def public_methods(cls: type) -> Dict[str, Any]:
    return {m: f for m, f in inspect.getmembers(cls, inspect.isfunction) if not m.startswith("_") and m not in SKIP_METHODS}


def candidate_methods(agent: str, cls: type) -> Dict[str, str]:
    """method -> "" if it may be exposed, else the reason it may not. An agent with HTTP rules exposes only what the table lists."""
    listed = METHODS.get(agent)
    out = {}
    for m, fn in public_methods(cls).items():
        if listed is not None and m not in listed:
            out[m] = "not in the HTTP allowlist (velaris/api/allowlist.py)"
        else:
            out[m] = exposable(fn) or ""
    return out


def kind_of(agent: str, method: str, derived: str) -> str:
    """READ or ACT: the allowlist where it has a rule, else what the manifest/derivation says. Anything else is ACT."""
    rule = rule_for(agent, method)
    if rule is not None:
        return rule.kind
    return derived if derived == READ else "act"


def specs_for(agent: str, cls: type, entry: Dict[str, Any], department: str = "") -> List[ToolSpec]:
    """The ToolSpecs of the methods an agent's harness entry exposes (`entry["tools"]`: method -> {"kind"})."""
    methods = public_methods(cls)
    specs = []
    for m, meta in entry.get("tools", {}).items():
        fn = methods.get(m)
        if fn is None:
            continue
        rule = rule_for(agent, m)
        specs.append(ToolSpec(f"{agent}.{m}", agent, m, params_of(fn, rule.actor if rule else None),
                              "none" if kind_of(agent, m, meta.get("kind", "act")) == READ else "state",
                              entry.get("sensitivity", "restricted"), department,
                              (inspect.getdoc(fn) or "").strip().split("\n")[0][:200]))
    return specs
