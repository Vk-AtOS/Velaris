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

Public interface (other modules import these names; they do not change): ToolSpec, register, get, list_tools
(also exported as `list`), clear, plus validate, to_openai, to_anthropic, register_allowlist, flow_tool.
"""
from __future__ import annotations

import builtins
import inspect
import logging
import threading
import typing
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from velaris.api.allowlist import ACT, READ, Rule, http_params, prepare, rule_for
from velaris.core.access import AccessDenied, Caller, org_denied
from velaris.intel import trace
from velaris.intel.flow import Tool

logger = logging.getLogger("velaris.intel.tools")
SIDE_EFFECTS = ("none", "internal", "external")
LEVELS = ("public", "internal", "restricted")
# Agents whose output holds nothing about people or money. Everything else is restricted (fail closed).
AGENT_SENSITIVITY: Dict[str, str] = {
    "AUTONOMOUS_RESEARCH_ENGINE": "public", "ADVANCED_SEARCH_ENGINE": "public",
    "TREASURIX": "internal", "FISCALIS": "internal", "MODEL_COUNCIL": "internal", "DOCUMENT_LIBRARY": "internal",
    "CONTROL_LAYER": "internal", "ITSM_ENGINE": "internal", "JIRA": "internal", "CONFLUENCE": "internal",
}
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
def _schema(tp: Any) -> Dict[str, Any]:
    if tp is inspect.Parameter.empty or tp is typing.Any:
        return {}
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
    return {"type": _JSON_TYPES[tp]} if tp in _JSON_TYPES else {}


def _first_line(obj: Any) -> str:
    return (inspect.getdoc(obj) or "").strip().split("\n")[0][:300]


def input_schema(fn: Any, rule: Rule) -> Dict[str, Any]:
    """JSON schema of the arguments a model may send: the method's parameters without the actor parameter."""
    try:
        hints = typing.get_type_hints(fn)
    except (NameError, TypeError):
        hints = {}
    props, required = {}, []
    for p in http_params(fn):
        if p.name == rule.actor:
            continue
        props[p.name] = _schema(hints.get(p.name, p.annotation))
        if p.default is p.empty:
            required.append(p.name)
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def side_effects_of(method: str, rule: Rule) -> str:
    if rule.kind == READ:
        return "none"
    return "external" if any(w in method.lower() for w in _EXTERNAL_WORDS) else "internal"


def spec_for(agent: str, method: str, fn: Any, department: str) -> Optional[ToolSpec]:
    """The ToolSpec of one allowlisted method, or None when the allowlist does not declare it."""
    rule = rule_for(agent, method)
    if rule is None:
        return None
    return ToolSpec(name=f"{agent}.{method}", agent=agent, method=method, params=input_schema(fn, rule),
                    side_effects=side_effects_of(method, rule), sensitivity=AGENT_SENSITIVITY.get(agent, "restricted"),
                    department=department, description=_first_line(fn) or f"{agent}.{method}", kind=rule.kind,
                    required_roles=tuple(sorted(rule.roles or ())), actor_param=rule.actor)


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
