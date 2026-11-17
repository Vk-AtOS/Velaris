"""The tool registry: agent methods as typed tools a model may be offered (KAN-29).

Built ON the two things that already exist, not beside them:
  * velaris.api.allowlist  decides WHICH agent methods are callable at all (read / act) and the caller checks
                           (roles, scope, actor, own). A method that is not in that table is never a tool.
  * velaris.intel.flow     is the run loop and its `Tool`. `flow_tool()` turns a ToolSpec into one.

A ToolSpec adds what a model-facing tool needs and the table does not say: a JSON schema of the inputs (from the
method's type hints), the first line of its docstring as description, `side_effects` (none | internal | external),
`sensitivity` (the level of data it touches, so the model call that reads its output is routed accordingly) and
the department.

Fail closed, in the direction of more human involvement:
  * side_effects is "none" only for a method the allowlist declares `read`; every `act` method is at least
    "internal", and "external" when its name says it sends, publishes, posts or hands off;
  * sensitivity is "restricted" unless the agent is on the short, reviewed list in AGENT_SENSITIVITY;
  * a tool with side effects always needs approval in the flow it is bound to (see flow_tool).

ONE ToolSpec and ONE derivation (`derive_spec`). The agent harness (velaris.agentkit.harness_tools) derives the
spec of every agent method it may expose through the same function and registers it here (`register_harness`);
the allowlist row is the READ/ACT truth wherever there is one. A spec whose method has no allowlist row is
`allowlisted=False`: the harness may use it (reads only run, acts are only proposed), but no orchestrator offers it
and `runner` refuses it, because HTTP would refuse it too.

Public interface (other modules import these names; they do not change): ToolSpec, register, get, list_tools
(also exported as `list`), clear, plus validate, to_openai, to_anthropic, register_allowlist, flow_tool.
"""
from __future__ import annotations

import builtins
import dataclasses
import inspect
import logging
import re
import threading
import typing
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

from velaris.api.allowlist import ACT, READ, http_params, prepare, rule_for
from velaris.core.access import AccessDenied, Caller, org_denied
from velaris.intel import trace
from velaris.intel.flow import Tool

logger = logging.getLogger("velaris.intel.tools")
SIDE_EFFECTS = ("none", "internal", "external")
LEVELS = ("public", "internal", "restricted")
LEVEL_RANK = {"public": 0, "internal": 1, "restricted": 2}
# Agents whose output holds nothing about people or money. Everything else is restricted (fail closed).
AGENT_SENSITIVITY: Dict[str, str] = {
    "AUTONOMOUS_RESEARCH_ENGINE": "public", "ADVANCED_SEARCH_ENGINE": "public",
    "TREASURIX": "internal", "FISCALIS": "internal", "MODEL_COUNCIL": "internal", "DOCUMENT_LIBRARY": "internal",
    "CONTROL_LAYER": "internal", "ITSM_ENGINE": "internal", "JIRA": "internal", "CONFLUENCE": "internal",
}
# collaborators wired by code, never chosen by a model
INJECTED = frozenset({"llm", "fetcher", "search_fn", "handler", "handlers", "func", "fn", "sender", "callback", "clock",
                      "registry", "engine"})
_EXTERNAL_WORDS = ("send", "publish", "post", "hand_off", "notify", "indexing", "email", "mail")
_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


class ToolError(ValueError):
    """A tool spec is unusable, or a name is registered twice."""


@dataclass(frozen=True)
class ToolSpec:
    name: str                               # "AGENT.method", the name the model uses
    agent: str
    method: str
    params: Dict[str, Any]                  # JSON schema: {"type": "object", "properties", "required", ...}
    side_effects: str = "internal"          # none | internal | external
    sensitivity: str = "restricted"         # public | internal | restricted
    department: str = ""
    description: str = ""
    kind: str = ACT                         # the allowlist's read / act
    required_roles: Tuple[str, ...] = ()    # roles the allowlist rule asks for (information; enforced by the rule)
    actor_param: Optional[str] = None       # parameter the code fills with the caller (never shown to a model)
    allowlisted: bool = True                # False: no row in velaris.api.allowlist; only the harness may use it

    def __post_init__(self) -> None:
        if self.side_effects not in SIDE_EFFECTS or self.sensitivity not in LEVELS:
            raise ToolError(f"{self.name}: side_effects is one of {SIDE_EFFECTS}, sensitivity one of {LEVELS}")
        if self.name != f"{self.agent}.{self.method}":
            raise ToolError("a tool is named AGENT.method")
        if self.kind == ACT and self.side_effects == "none":
            raise ToolError(f"{self.name}: a method that changes state cannot declare side_effects 'none'")


# ── the registry ─────────────────────────────────────────────────────────────
_tools: Dict[str, ToolSpec] = {}
_lock = threading.Lock()


def register(tool: ToolSpec) -> ToolSpec:
    """Add a tool. The same spec again is a no-op; a different spec under the same name is refused."""
    if not isinstance(tool, ToolSpec):
        raise ToolError("register() takes a ToolSpec")
    with _lock:
        known = _tools.get(tool.name)
        if known is not None and known != tool:
            raise ToolError(f"a different tool is already registered as {tool.name}")
        _tools[tool.name] = tool
    return tool


def get(name: str) -> Optional[ToolSpec]:
    return _tools.get(name)


def list_tools(department: Optional[str] = None) -> List[ToolSpec]:
    """Every tool, or one department's, sorted by name."""
    with _lock:
        return sorted((t for t in _tools.values() if department is None or t.department == department),
                      key=lambda t: t.name)


list = list_tools          # the interface name; shadows the builtin only inside this module (see _as_list)


def clear() -> None:
    with _lock:
        _tools.clear()


# ── schema from a method's signature ─────────────────────────────────────────
_TEXT_TYPES = ((r"dict|mapping", "object"), (r"list|sequence|tuple|set\b|iterable", "array"), (r"\bbool", "boolean"),
               (r"\bfloat|decimal", "number"), (r"\bint\b|^int", "integer"), (r"\bstr\b|^str", "string"))


def _text_schema(tp: Any) -> Dict[str, Any]:
    """The schema of an annotation that could not be resolved (a string): judged by its text, {} when unclear."""
    t = (getattr(tp, "__name__", None) if isinstance(tp, type) else str(tp)).lower()
    return next(({"type": kind} for pattern, kind in _TEXT_TYPES if re.search(pattern, t)), {})


def _schema(tp: Any) -> Dict[str, Any]:
    if tp is inspect.Parameter.empty or tp is typing.Any:
        return {}
    if isinstance(tp, str):
        return _text_schema(tp)
    origin, args = typing.get_origin(tp), typing.get_args(tp)
    if origin is typing.Union:
        non_null = [a for a in args if a is not type(None)]
        if len(non_null) != 1:
            return {}                      # a union of several types: no constraint (the method checks its own input)
        inner = _schema(non_null[0])
        return {**inner, "type": [inner["type"], "null"]} if "type" in inner and len(args) > 1 else inner
    if origin in (builtins.list, typing.List):
        return {"type": "array", "items": _schema(args[0])} if args else {"type": "array"}
    if origin in (dict, typing.Dict):
        return {"type": "object"}
    if tp in _JSON_TYPES:
        return {"type": _JSON_TYPES[tp]}
    return _text_schema(tp) if isinstance(tp, type) else {}


def _first_line(obj: Any) -> str:
    return (inspect.getdoc(obj) or "").strip().split("\n")[0][:300]


def _hints(fn: Any) -> Dict[str, Any]:
    try:
        return typing.get_type_hints(fn)
    except (NameError, TypeError) as e:     # a forward reference that cannot be resolved: judged by the text instead
        logger.debug("type hints of %s unresolved: %s", getattr(fn, "__name__", fn), type(e).__name__)
        return {}


def dataclass_params(fn: Any) -> Dict[str, type]:
    """Parameters annotated with a dataclass: the model writes them as a JSON object and the harness builds the instance."""
    hints = _hints(fn)
    return {p.name: hints[p.name] for p in http_params(fn)
            if isinstance(hints.get(p.name), type) and dataclasses.is_dataclass(hints[p.name])}


def input_schema(fn: Any, actor: Any = None) -> Dict[str, Any]:
    """JSON schema of the arguments a model may send: the method's parameters, without the actor parameter code fills in
    and without collaborators (llm, callables) code wires. `actor` is the name or an allowlist Rule."""
    actor = getattr(actor, "actor", actor)
    hints, objects, props, required = _hints(fn), dataclass_params(fn), {}, []
    for p in http_params(fn):
        if p.name == actor or p.name in INJECTED or "Callable" in str(p.annotation):
            continue
        prop = _schema(hints.get(p.name, p.annotation))
        if p.name in objects:
            fields = [f for f in dataclasses.fields(objects[p.name]) if f.init]
            prop = {"type": "object", "properties": {f.name: _schema(f.type) for f in fields},
                    "required": [f.name for f in fields if f.default is dataclasses.MISSING
                                 and f.default_factory is dataclasses.MISSING], "additionalProperties": False}
        if p.default is not p.empty and isinstance(p.default, (str, int, float, bool, type(None))):
            prop = {**prop, "default": p.default}
        props[p.name] = prop
        if p.default is p.empty:
            required.append(p.name)
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def side_effects_of(method: str, kind: str) -> str:
    if kind == READ:
        return "none"
    return "external" if any(w in method.lower() for w in _EXTERNAL_WORDS) else "internal"


@lru_cache(maxsize=None)
def _manifest_level(agent: str, department: str) -> Optional[str]:
    from velaris.agentkit.harness_spec import load_json, manifest_path      # a leaf module; deferred, it reads files
    try:
        entry = load_json(manifest_path(department, agent)).get("harness")
    except ValueError as e:                  # no manifest (a test double) or unreadable: the fail-closed default applies
        logger.debug("no harness level for %s: %s", agent, type(e).__name__)
        return None
    return entry.get("sensitivity") if isinstance(entry, dict) and entry.get("sensitivity") in LEVELS else None


def sensitivity_of(agent: str, department: str = "", fn: Any = None, *, allowlisted: bool = True) -> str:
    """The level of the data a tool touches. FAIL CLOSED: an allowlisted spec (the only kind orchestrators, the brain
    and Flows route and classify with) is restricted unless the agent is on the short reviewed list AGENT_SENSITIVITY;
    a manifest never lowers it. A harness-only spec (no allowlist row; the harness never uses this field for its own
    model calls, it uses the manifest level) may take the manifest level, but never below the department/code floor
    (harness_derive.min_sensitivity: hr, finance, legal, security, or code that checks callers or seals data)."""
    base = AGENT_SENSITIVITY.get(agent, "restricted")
    if allowlisted or not department:
        return base
    level = _manifest_level(agent, department)
    if level is None:
        return base
    from velaris.agentkit.harness_derive import min_sensitivity, source_of     # deferred: it imports this module
    module = inspect.getmodule(fn)
    try:
        floor = min_sensitivity(department, source_of(module)) if module else "restricted"
    except OSError as e:                                  # source unreadable: no floor can be proven, so restricted
        logger.debug("no source for %s: %s", agent, type(e).__name__)
        floor = "restricted"
    return max(level, floor, key=LEVEL_RANK.__getitem__)


def derive_spec(agent: str, method: str, fn: Any, department: str, *, kind: str = ACT) -> ToolSpec:
    """THE derivation of a ToolSpec from an agent method. The allowlist row, where there is one, decides READ or ACT
    (and the actor parameter); `kind` is only used for a method the table does not cover, and anything but READ is ACT."""
    rule = rule_for(agent, method)
    kind = rule.kind if rule else (READ if kind == READ else ACT)
    return ToolSpec(name=f"{agent}.{method}", agent=agent, method=method, params=input_schema(fn, rule),
                    side_effects=side_effects_of(method, kind), sensitivity=sensitivity_of(agent, department, fn, allowlisted=rule is not None),
                    department=department, description=_first_line(fn) or f"{agent}.{method}", kind=kind,
                    required_roles=tuple(sorted(rule.roles or ())) if rule else (),
                    actor_param=rule.actor if rule else None, allowlisted=rule is not None)


def spec_for(agent: str, method: str, fn: Any, department: str) -> Optional[ToolSpec]:
    """The ToolSpec of one allowlisted method, or None when the allowlist does not declare it."""
    return derive_spec(agent, method, fn, department) if rule_for(agent, method) is not None else None


def register_allowlist(engine: Any) -> int:
    """Register every method of velaris.api.allowlist.METHODS that the engine has loaded. Returns how many."""
    from velaris.api.allowlist import METHODS
    n = 0
    for agent, methods in METHODS.items():
        try:
            cls = engine.agent_class(agent)
        except LookupError:
            continue
        dept = engine.router.departments.get(agent, "")
        for method in methods:
            fn = getattr(cls, method, None)
            spec = spec_for(agent, method, fn, dept) if fn is not None else None
            if spec is not None:
                register(spec)
                n += 1
    return n


# ── validation and export ────────────────────────────────────────────────────
def _type_ok(value: Any, schema: Dict[str, Any]) -> bool:
    t = schema.get("type")
    if t is None:
        return True
    for one in (t if isinstance(t, builtins.list) else [t]):
        if one == "null" and value is None:
            return True
        if one == "string" and isinstance(value, str):
            return True
        if one == "boolean" and isinstance(value, bool):
            return True
        if one == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if one == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if one == "array" and isinstance(value, builtins.list) and all(_type_ok(v, schema.get("items", {})) for v in value):
            return True
        if one == "object" and isinstance(value, dict):
            return True
    return False


def validate(tool: ToolSpec, args: Any) -> builtins.list:
    """Why `args` do not fit the tool's schema: a list of short sentences, empty when they fit."""
    if not isinstance(args, dict):
        return ["the arguments must be a JSON object"]
    props, errors = tool.params.get("properties", {}), []
    errors += [f"unknown argument '{k}'" for k in sorted(set(args) - set(props), key=str)]
    errors += [f"missing argument '{k}'" for k in tool.params.get("required", []) if k not in args]
    errors += [f"argument '{k}' must be {props[k].get('type')}" for k in args
               if k in props and not _type_ok(args[k], props[k])]
    return errors


def to_openai(tool: ToolSpec) -> Dict[str, Any]:
    return {"type": "function", "function": {"name": tool.name.replace(".", "__"), "description": tool.description,
                                             "parameters": tool.params}}


def to_anthropic(tool: ToolSpec) -> Dict[str, Any]:
    return {"name": tool.name.replace(".", "__"), "description": tool.description, "input_schema": tool.params}


def _prompt_params(tool: ToolSpec) -> Dict[str, str]:
    props = tool.params.get("properties", {})
    return {k: str(v.get("type", "any")) + ("" if k in tool.params.get("required", []) else " (optional)")
            for k, v in props.items()}


def flow_tool(tool: ToolSpec, run: Callable[..., Any], *, needs_approval: Any = None) -> Tool:
    """The tool as a velaris.intel.flow Tool. `run(**args)` does the call (the caller binds who it runs for and goes
    through allowlist.prepare and BackendEngine.run). Arguments are validated against the schema before `run`;
    a tool with side effects needs approval unless the caller passes its own rule (the autonomy table does)."""
    def checked(**args: Any) -> Any:
        problems = validate(tool, args)
        if problems:
            trace.append("tools", "invalid_args", {"tool": tool.name, "problems": problems[:5]})
            raise ValueError("; ".join(problems))
        return run(**args)
    need = (tool.side_effects != "none") if needs_approval is None else needs_approval
    return Tool(tool.name, checked, tool.description, _prompt_params(tool), needs_approval=need,
                idempotent=tool.side_effects == "none")


def runner(engine: Any, tool: ToolSpec, caller: Caller) -> Callable[..., Any]:
    """`run(**args)` for flow_tool(): the allowlist's checks (roles, scope, actor, own) and then BackendEngine.run, as
    `caller`. A refusal is an AccessDenied; any other failure becomes a plain sentence (no internals reach the model)."""
    if not tool.allowlisted:
        raise ToolError(f"{tool.name} has no allowlist row: only the harness may use it")

    def run(**kwargs: Any) -> Any:
        why = org_denied(caller)
        if why:
            raise AccessDenied(why)
        fn = getattr(engine.agent_class(tool.agent), tool.method)
        args = prepare(tool.agent, tool.method, fn, kwargs, caller)
        try:
            return engine.run(tool.agent, tool.method, args, caller=caller)
        except AccessDenied:
            raise
        except Exception as e:
            logger.warning("%s failed as a tool: %s", tool.name, type(e).__name__)
            raise RuntimeError("the agent call failed") from e
    return run
