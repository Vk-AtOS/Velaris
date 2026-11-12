"""Coherence sync core: detects when copies of the same state have drifted apart, and says how to fix each.

Each replica (a service, a branch office system, an agent) reports its copy of
a state. check() takes the state held by a strict majority of replicas as the
reference and, for every replica that differs, returns the patch from
CSG_STATEALIGN that would bring it back; replicas whose report is older than
`max_lag` are listed as lagging. With no majority it reports a split and
proposes nothing. Reports stamped in the future (CSG_TEMPORAL) or older than
the one already held are refused.
State: <VELARIS_DATA>/agents/COHERENCE_SYNC_CORE/state.json.
"""
import hashlib
import json
import time

from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, number, ok
from velaris.agents.CSG_STATEALIGN.main import CSG_STATEALIGNAgent
from velaris.agents.CSG_TEMPORAL.main import CSG_TEMPORALAgent
from velaris.intel.paths import agent_dir

NAME = "COHERENCE_SYNC_CORE"


def _digest(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


class COHERENCE_SYNC_COREAgent:
    def __init__(self):
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"replicas": {}})

    def health_check(self):
        return health(NAME)

    def report(self, replica, state, ts=None, now=None):
        now = time.time() if now is None else now
        ts = now if ts is None else number(ts)
        if ident(replica) is None or not isinstance(state, dict) or ts is None:
            return fail("invalid_input", "replica must be a name, state an object and ts a number")
        if CSG_TEMPORALAgent().check([{"id": replica, "ts": ts}], now=now)["future"]:
            return fail("clock_skew", f"report from {replica} is stamped in the future")

        def change(data):
            held = data["replicas"].get(replica)
            if held and held["ts"] > ts:
                return fail("stale", f"{replica} already reported at {held['ts']}")
            data["replicas"][replica] = {"state": state, "ts": ts, "digest": _digest(state)}
            return ok(replica=replica, digest=data["replicas"][replica]["digest"])
        return self._state.update(change)

    def forget(self, replica):
        removed = self._state.update(lambda data: data["replicas"].pop(replica, None) if isinstance(replica, str) else None)
        return ok(removed=replica) if removed else fail("not_found", f"no replica {replica!r}")

    def check(self, max_lag=None):
        replicas = self._state.load()["replicas"]
        if not replicas:
            return fail("no_data", "no replica has reported", coherent=False)
        groups = {}
        for name, rec in sorted(replicas.items()):
            groups.setdefault(rec["digest"], []).append(name)
        newest = max(rec["ts"] for rec in replicas.values())
        lagging = sorted(n for n, rec in replicas.items() if number(max_lag) is not None and newest - rec["ts"] > max_lag)
        majority = max(groups.values(), key=len)
        if len(majority) * 2 <= len(replicas):
            return fail("split", "no state is held by a majority of replicas", coherent=False,
                        groups=sorted(groups.values()), lagging=lagging, patches={})
        reference = replicas[majority[0]]["state"]
        patches = {n: CSG_STATEALIGNAgent().align(reference, rec["state"])["patch"]
                   for n, rec in sorted(replicas.items()) if n not in majority}
        return {"status": "ok" if not patches and not lagging else "drift", "coherent": not patches,
                "reference": reference, "in_sync": majority, "divergent": sorted(patches),
                "patches": patches, "lagging": lagging}
