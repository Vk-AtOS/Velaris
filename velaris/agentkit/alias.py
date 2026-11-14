"""Delegating (alias) agents: one agent name that fronts several component agents.

A delegate is an agent under departments/<dept>/<NAME>/main.py. Its module exposes classes, not
functions, so the delegate is resolved to its CLASS, instantiated once (no arguments) and the
requested method is called on the instance. run("method") calls the first component that has the
method; run("COMPONENT.method") picks the component. health_check() is "ok" only when every
component loads, builds and reports ok; a component that cannot load makes it "failed" (none
did) or "degraded" (some did), and names the component.
"""
from __future__ import annotations

import inspect
import logging
import re
from importlib import import_module
from typing import Any, Dict, List, Optional


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve_class(component: str):
    """The agent class defined in velaris.agents.<component>.main (ImportError if there is none)."""
    mod = import_module(f"velaris.agents.{component}.main")
    own = [c for n, c in inspect.getmembers(mod, inspect.isclass) if c.__module__ == mod.__name__ and not n.startswith("_")]
    if not own:
        raise ImportError(f"{component} defines no class")
    key = _norm(component)
    for pick in (lambda n: n == f"{component}Agent", lambda n: _norm(n) == key + "agent", lambda n: _norm(n) == key,
                 lambda n: key.startswith(_norm(n).removesuffix("agent")) and _norm(n) != "agent",
                 lambda n: n.endswith("Agent")):
        hit = [c for c in own if pick(c.__name__)]
        if hit:
            return hit[-1]          # the most derived/last defined (PrimeAgent over VelarisPrime)
    return own[0]


class Delegator:
    name = ""
    components: List[str] = []
    version = "0.1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.logger = logging.getLogger(self.name)
        self._instances: Optional[Dict[str, Any]] = None
        self._failed: Dict[str, str] = {}

    def _load(self) -> Dict[str, Any]:
        if self._instances is None:
            found: Dict[str, Any] = {}
            for comp in dict.fromkeys(self.components):          # unique, in order
                try:
                    found[comp] = resolve_class(comp)()
                except Exception as e:                           # a delegate is other code: report it, do not crash
                    self._failed[comp] = f"{type(e).__name__}: {e}"
                    self.logger.warning("%s delegate %s could not be loaded: %s", self.name, comp, e)
            self._instances = found
        return self._instances

    def health_check(self) -> Dict[str, Any]:
        loaded, problems = self._load(), dict(self._failed)
        for comp, inst in loaded.items():
            check = getattr(inst, "health_check", None)
            if not callable(check):
                continue
            try:
                result = check()
            except Exception as e:
                self.logger.warning("%s delegate health check failed: %s", self.name, e)
                problems[comp] = str(e)
                continue
            if isinstance(result, dict) and result.get("status", "ok") != "ok":
                problems[comp] = f"status {result['status']}"
        status = "ok" if not problems else "failed" if not loaded else "degraded"
        out: Dict[str, Any] = {"agent": self.name, "status": status, "version": self.version,
                               "components": sorted(self.components)}
        if problems:
            out["error"] = "; ".join(f"{c}: {m}" for c, m in sorted(problems.items()))
        return out

    def run(self, method: str, *args: Any, **kwargs: Any) -> Any:
        loaded = self._load()
        comp, _, meth = method.rpartition(".")
        pool = [comp] if comp else list(loaded)
        for c in pool:
            fn = getattr(loaded.get(c), meth, None)
            if callable(fn) and not meth.startswith("_"):
                return fn(*args, **kwargs)
        raise AttributeError(f"{self.name}: method {method} not found on any delegate "
                             f"(loaded: {sorted(loaded)}, failed: {sorted(self._failed)})")
