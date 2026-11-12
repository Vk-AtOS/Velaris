"""CCSF core: one agreed view of an entity that several systems each hold a copy of.

ingest() stores the latest snapshot each system reported for an entity (an
older snapshot than the one held is refused as stale). view() merges the
snapshots with CCSF_FUSION, settles disagreements with CCSF_RESOLVER using the
configured strategies, and returns the agreed state, where each field came
from, and the fields still waiting for a person.
State: <VELARIS_DATA>/agents/CCSF_CORE/state.json.
"""
import time

from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, invalid, number, ok
from velaris.agents.CCSF_FUSION.main import CCSF_FUSIONAgent
from velaris.agents.CCSF_RESOLVER.main import CCSF_RESOLVERAgent
from velaris.intel.paths import agent_dir

NAME = "CCSF_CORE"


class CCSF_COREAgent:
    def __init__(self, strategies=None, default_strategy="manual"):
        self.strategies, self.default_strategy = strategies or {}, default_strategy
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"entities": {}})

    def health_check(self):
        return health(NAME)

    def ingest(self, entity, source, data, ts=None):
        entity, source = ident(entity), ident(source)
        ts = time.time() if ts is None else number(ts)
        if entity is None or source is None or ts is None or not isinstance(data, dict):
            return invalid("entity and source must be names, data an object and ts a number")
        check = CCSF_FUSIONAgent().fuse([{"source": source, "data": data, "ts": ts}])
        if check["status"] == "invalid_input":
            return check

        def change(state):
            held = state["entities"].setdefault(entity, {})
            if source in held and held[source]["ts"] > ts:
                return fail("stale", f"{source} already reported {entity} at {held[source]['ts']}")
            held[source] = {"data": data, "ts": ts}
            return ok(entity=entity, source=source, sources=sorted(held))
        return self._state.update(change)

    def view(self, entity):
        held = self._state.load()["entities"].get(entity) if isinstance(entity, str) else None
        if not held:
            return fail("not_found", f"nothing ingested for entity {entity!r}")
        fused = CCSF_FUSIONAgent().fuse([{"source": s, **snap} for s, snap in sorted(held.items())])
        settled = CCSF_RESOLVERAgent().resolve(fused["conflicts"], self.strategies, self.default_strategy)
        if settled["status"] == "invalid_input":
            return fail("not_configured", f"resolution strategies were rejected: {settled['reason']}")
        state, provenance = dict(fused["merged"]), dict(fused["provenance"])
        for field, win in settled["resolved"].items():
            state[field], provenance[field] = win["value"], [win["source"]]
        return {"status": "ok" if not settled["unresolved"] else "unresolved", "entity": entity, "state": state,
                "provenance": provenance, "resolved": settled["resolved"], "unresolved": settled["unresolved"],
                "sources": fused["sources"]}
