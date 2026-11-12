"""CSG temporal: checks that a sequence of timestamped events is consistent in time.

check() takes events ({"id", "ts"}) in the order they were received and
reports: events that arrived out of order, repeated ids, events stamped further
in the future than the allowed clock skew, and gaps longer than `max_gap`.
It returns the ids in time order. It reports problems; it does not repair them.
"""
import time

from velaris.agentkit.aicore_a_common import fail, health, ident, number

NAME = "CSG_TEMPORAL"


class CSG_TEMPORALAgent:
    def __init__(self, max_skew=5.0):
        self.max_skew = max_skew

    def health_check(self):
        return health(NAME)

    def check(self, events, max_gap=None, now=None):
        if not isinstance(events, list):
            return fail("invalid_input", "events must be a list of {id, ts}", consistent=False)
        if max_gap is not None and (number(max_gap) is None or max_gap <= 0):
            return fail("invalid_input", "max_gap must be a positive number", consistent=False)
        now = time.time() if now is None else now
        firsts, duplicates, out_of_order, future, latest = {}, [], [], [], None
        for event in events:
            eid = ident(event.get("id")) if isinstance(event, dict) else None
            ts = number(event.get("ts")) if eid else None
            if eid is None or ts is None:
                return fail("invalid_input", f"event {event!r} needs an 'id' and a numeric 'ts'", consistent=False)
            if eid in firsts:
                duplicates.append(eid)
                continue
            firsts[eid] = ts
            if latest is not None and ts < latest:
                out_of_order.append({"id": eid, "ts": ts, "behind_by": round(latest - ts, 6)})
            latest = ts if latest is None else max(latest, ts)
            if ts > now + self.max_skew:
                future.append({"id": eid, "ahead_by": round(ts - now, 6)})
        ordered = sorted(firsts.items(), key=lambda kv: (kv[1], kv[0]))
        gaps = [{"after": a[0], "before": b[0], "gap": round(b[1] - a[1], 6)}
                for a, b in zip(ordered, ordered[1:]) if max_gap is not None and b[1] - a[1] > max_gap]
        consistent = not (duplicates or out_of_order or future or gaps)
        return {"status": "ok" if consistent else "inconsistent", "consistent": consistent,
                "order": [eid for eid, _ in ordered], "out_of_order": out_of_order, "duplicates": duplicates,
                "future": future, "gaps": gaps}
