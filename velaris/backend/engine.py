"""
Velaris Backend Engine
Central engine that loads the agent router and exposes platform APIs.

run() is the one dispatch path for calling an agent on someone's behalf: it sets the
caller (velaris.core.access.acting_as) for the whole call, so every agent and connector
underneath sees who is asking without each one being handed it.
"""
import asyncio
import dataclasses
import inspect
import sys
import os
from typing import Any, Dict, Optional
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velaris.agentkit.hr_wiring import hr_config
from velaris.agents.router import router
from velaris.core.access import Caller, acting_as


class BackendEngine:
    def __init__(self):
        self.router = router

    def list_agents(self):
        return self.router.list_agents()

    def get_agent(self, name):
        return self.router.get_agent(name)

    def agent_class(self, name: str):
        """The one class in an agent's main.py that the agent is made of.

        A module that defines several public classes (a helper store beside the agent) is
        resolved to the one whose name ends in Agent/Engine or, failing that, the last one
        defined; anything else is ambiguous and refused. An exception class or a dataclass record
        (a helper the module defines beside the agent) is never the agent.
        """
        module = self.router.get_agent(name)
        if module is None:
            raise LookupError(f"no agent named {name!r}")
        own = [c for _, c in inspect.getmembers(module, inspect.isclass)
               if c.__module__ == module.__name__ and not c.__name__.startswith("_")
               and not issubclass(c, BaseException) and not dataclasses.is_dataclass(c)]
        if len(own) == 1:
            return own[0]
        named = [c for c in own if c.__name__.upper().endswith(("AGENT", "ENGINE", "CONNECTOR"))]
        if len(named) == 1:
            return named[0]
        raise LookupError(f"agent {name!r} defines {len(own)} classes; cannot tell which one is the agent")

    @staticmethod
    def _build(agent: str, cls: type, config: Optional[Dict[str, Any]]) -> Any:
        """A fresh instance. An explicit `config` is the first constructor argument exactly as given. With none, the
        wiring is passed ONLY to a constructor whose first parameter is called `config` (as agents.REGISTRY.create does):
        any other first parameter (name, rules, path, llm, ...) is not a config dict, and giving it {} silently broke 92
        agents. AAE_POLICY gets the autonomy table as its rules, so what the engine decides is what Flow enforces."""
        first = next((p for p in list(inspect.signature(cls.__init__).parameters.values())[1:]
                      if p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY)), None)
        if first is None:
            return cls()
        if config is not None:
            return cls(config)
        if first.name == "config":
            return cls(hr_config(agent))
        if agent == "AAE_POLICY":
            from velaris.orchestration import autonomy      # deferred: the table imports the tool registry, which imports agents
            return cls(rules=autonomy.to_aae_rules())
        return cls()

    def run(self, agent: str, method: str, params: Optional[Dict[str, Any]] = None, *,
            caller: Optional[Caller] = None, config: Optional[Dict[str, Any]] = None) -> Any:
        """Call agent.method(**params) on behalf of `caller` (None: nobody, refused for sensitive data).

        Private methods (leading underscore) cannot be called. The agent is created fresh for
        the call, with `config` if its constructor takes one (see _build); with no `config` the HR agents get their real collaborators
        from velaris.agentkit.hr_wiring (an explicit config, even {}, is used exactly as given). An async method is run to
        completion, so do not call this from inside a running event loop.
        """
        if not isinstance(method, str) or not method.isidentifier() or method.startswith("_"):
            raise PermissionError(f"method {method!r} cannot be called")
        cls = self.agent_class(agent)
        with acting_as(caller):
            instance = self._build(agent, cls, config)
            fn = getattr(instance, method, None)
            if not callable(fn):
                raise AttributeError(f"agent {agent!r} has no method {method!r}")
            result = fn(**(params or {}))
            if inspect.iscoroutine(result):      # an async method: run it here, still as `caller`
                result = asyncio.run(result)
            return result

    def status(self):
        return {
            "status": "online",
            "agents_loaded": self.router.count(),
            "agents_failed": dict(self.router.failed),
            "agent_list": self.router.list_agents()
        }


backend = BackendEngine()
