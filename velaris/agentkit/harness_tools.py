"""What the harness adds to the ONE tool registry (velaris.intel.tools): which methods a model may be offered, and how.

There is one ToolSpec and one derivation (`tools.derive_spec`): the harness derives the spec of every agent method its
manifest entry exposes through it and registers it. The allowlist row decides READ or ACT where there is one; for a method the
table does not cover the manifest's kind is used, and the strict read proof (harness_derive.read_or_act) is what the manifest
was generated from. This file keeps the harness's own rules: which methods are exposable at all (secrets, collaborators, objects
JSON cannot carry), objects built from JSON, and the walk that registers everything.
"""
from __future__ import annotations

import dataclasses
import inspect
import logging
import re
import typing
from typing import Any, Dict, List, Optional

from velaris.api.allowlist import METHODS, http_params, rule_for, READ
from velaris.intel import tools
from velaris.intel.tools import INJECTED, ToolSpec

logger = logging.getLogger("velaris.harness")
SECRET_PARAM = re.compile(r"(^|_)((secret|password|passcode|passphrase|pin|api_?key|private_?key|credential|fingerprint|face|voice)s?|token)$")
SECRET_RETURN = re.compile(r"^(issue|generate|get|reveal|export|mint|derive|create)_.*(secret|token|keypair|private|credential|password|recovery_code)")
SKIP_METHODS = frozenset({"health_check", "health", "on_event"})


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
    if SECRET_RETURN.search(getattr(fn, "__name__", "")):
        return "the method returns a secret, which would pass through the model"
    custom = object_param(fn)
    if custom:
        return f"required parameter '{custom}' is an object of the agent's own class, which JSON cannot carry"
    for p in http_params(fn):
        if p.default is p.empty and (p.name in INJECTED or "Callable" in str(p.annotation)):
            return f"required parameter '{p.name}' is a collaborator or callable, wired by code"
        if p.annotation is bytes:
            return f"parameter '{p.name}' is bytes, which JSON cannot carry"
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
    """The ToolSpecs of the methods an agent's harness entry exposes (`entry["tools"]`: method -> {"kind"}), registered."""
    methods = public_methods(cls)
    return [tools.register(tools.derive_spec(agent, m, methods[m], department, kind=meta.get("kind", "act")))
            for m, meta in entry.get("tools", {}).items() if m in methods]


def register_all(engine: Any) -> int:
    """Register the tools of every harnessed agent (and so, through the same derivation, of every allowlisted method).
    Returns how many specs the registry holds afterwards."""
    from velaris.agentkit.harness_spec import load_json, manifest_path
    tools.register_allowlist(engine)
    for agent, department in sorted(engine.router.departments.items()):
        try:
            entry = load_json(manifest_path(department, agent)).get("harness")
            if isinstance(entry, dict) and entry.get("status") != "not_harnessed":
                specs_for(agent, engine.agent_class(agent), entry, department)
        except (ValueError, LookupError) as e:     # an agent that cannot be built has no tools; the harness check reports why
            logger.debug("no harness tools for %s: %s", agent, type(e).__name__)
    return len(tools.list_tools())
