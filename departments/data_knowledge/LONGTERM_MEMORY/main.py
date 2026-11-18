"""Long-term memory: a persistent key-value store plus a scoped, time-aware fact memory.

put(k, v) and get(k, default=None) use a sealed JSON file (default <VELARIS_DATA>/agents/LONGTERM_MEMORY/
longterm.json; JsonState: encrypted, atomic, one locked read-modify-write per put, so two workers never lose a key);
put raises if the value is not JSON-serialisable. put needs an authenticated caller; get does not change anything.
remember(text, scope, source="") and recall(query, scope, k=5, at=None) delegate to velaris.intel.memory.MemoryStore,
which keeps durable facts, lets corrections supersede old ones and answers as of a time, and screens the text (a
blocked text is not stored). Both need an authenticated caller whose organisation owns `scope` ("<org>" or
"<org>:<anything>", velaris.core.access.may_read_scope): AccessDenied otherwise. The fact store is opened lazily.
"""
import json
import logging

from velaris.agentkit.state import JsonState
from velaris.core.access import AccessDenied, Caller, check_caller, current_caller, may_read_scope, org_denied
from velaris.intel.memory import MemoryStore
from velaris.intel.paths import agent_file

logger = logging.getLogger("LONGTERM_MEMORY")
NAME = "LONGTERM_MEMORY"


class LONGTERM_MEMORYAgent:
    def __init__(self, path: str = ""):
        self.name = NAME
        self.path = path or agent_file(NAME, "longterm.json")
        # files written before versioning were a bare {key: value} object: version 0 -> 1 nests it under "kv"
        self._kv = JsonState(NAME, path=self.path, default={"kv": {}}, encrypted="memory:LONGTERM_MEMORY",
                             migrations={0: lambda d: {"kv": d}})
        self._fact_store = None     # opened on first remember/recall
        logger.debug("LONGTERM_MEMORY initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def put(self, k, v):
        _, refused = check_caller(NAME, "put", {"key": str(k)[:128]})
        if refused:
            raise AccessDenied(refused["reason"])
        json.dumps(v)                                            # not JSON-serialisable: raise before touching the file
        self._kv.update(lambda d: d.setdefault("kv", {}).__setitem__(str(k), v))
        logger.debug("PUT %s", k)

    def get(self, k, default=None):
        return (self._kv.load().get("kv") or {}).get(str(k), default)

    @staticmethod
    def _caller_for(scope) -> Caller:
        who = current_caller()
        if not isinstance(who, Caller):
            raise AccessDenied("no authenticated caller")
        why = org_denied(who)
        if why or not may_read_scope(who, scope):
            raise AccessDenied(why or "the scope belongs to another organisation")
        return who

    def _facts(self):
        if self._fact_store is None:
            self._fact_store = MemoryStore()
        return self._fact_store

    def remember(self, text: str, scope: str, source: str = ""):
        """Keep the durable facts in `text`; corrections supersede old facts, nothing is deleted."""
        self._caller_for(scope)
        return self._facts().remember(text, scope=scope, source=source)

    def recall(self, query: str, scope: str, k: int = 5, at=None):
        """The k most relevant facts in `scope`, valid now or at time `at`."""
        self._caller_for(scope)
        return [m.to_dict() for m in self._facts().recall(query, scope=scope, k=k, at=at)]
