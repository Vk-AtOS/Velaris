"""ASEL router: decides which handler carries out each plan step.

A step names the `capability` it needs; a handler lists the capabilities it
has. Each step goes to the capable handler with the fewest steps so far (name
breaks ties), respecting an optional `max_steps` per handler. Steps nobody can
take are returned as unroutable; they are not given to a default handler.
"""
from velaris.agentkit.aicore_a_common import fail, health, ident, invalid

NAME = "ASEL_ROUTER"


class ASEL_ROUTERAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def route(self, steps, handlers):
        """steps: list (or a planner result) of {"id", "capability"}; handlers: [{"name", "capabilities", "max_steps"?}]."""
        if isinstance(steps, dict):
            steps = steps.get("steps")
        if not isinstance(steps, list) or not all(isinstance(s, dict) and ident(s.get("id")) for s in steps):
            return invalid("steps must be a list of objects with an 'id'")
        if not isinstance(handlers, list):
            return invalid("handlers must be a list")
        counts, limits = {}, {}
        for h in handlers:
            name = ident(h.get("name")) if isinstance(h, dict) else None
            caps, limit = (h.get("capabilities"), h.get("max_steps")) if name else (None, None)
            if name is None or name in counts or not isinstance(caps, list):
                return invalid(f"handler {h!r} needs a unique name and a list of capabilities")
            if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
                return invalid(f"handler {name}: max_steps must be a non-negative integer")
            counts[name], limits[name] = 0, limit
        capable = {h["name"]: h["capabilities"] for h in handlers}
        routed, routes, unroutable = [], {}, []
        for step in steps:
            need = step.get("capability")
            able = [n for n, caps in capable.items() if need in caps]
            free = [n for n in able if limits[n] is None or counts[n] < limits[n]]
            if not free:
                reason = (f"no handler has capability {need!r}" if not able
                          else f"every handler with {need!r} is at its step limit")
                unroutable.append({"id": step["id"], "reason": reason})
                routed.append({**step, "handler": None})
                continue
            choice = min(free, key=lambda n: (counts[n], n))
            counts[choice] += 1
            routes[step["id"]] = choice
            routed.append({**step, "handler": choice})
        result = {"routes": routes, "steps": routed, "unroutable": unroutable, "handler_load": counts}
        if unroutable:
            return fail("partial", f"{len(unroutable)} step(s) could not be routed", **result)
        return {"status": "ok", **result}
