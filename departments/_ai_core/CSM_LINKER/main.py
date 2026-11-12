"""CSM linker: a register of named relationships between things (goals, policies, owners, accounts).

link(a, b, relation) records an undirected link once; neighbours() lists what
an item is linked to; path() finds the shortest chain of links between two
items. Items are identified by name. It stores links people or code assert; it
does not discover them.
State: <VELARIS_DATA>/agents/CSM_LINKER/state.json.
"""
from collections import deque

from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, ok
from velaris.intel.paths import agent_dir

NAME = "CSM_LINKER"


class CSMLinkerAgent:
    def __init__(self):
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"links": []})

    def health_check(self):
        return health(NAME)

    def link(self, a, b, relation="related"):
        """`linked` is True when the link exists after the call; `created` is False for a repeat."""
        a, b, relation = ident(a), ident(b), ident(relation)
        if a is None or b is None or relation is None or a == b:
            return fail("invalid_input", "need two different non-empty names and a relation name",
                        linked=False, a=a, b=b)
        low, high = sorted((a, b))
        entry = {"a": low, "b": high, "relation": relation}

        def change(data):
            if entry in data["links"]:
                return False
            data["links"].append(entry)
            return True
        return ok(linked=True, created=self._state.update(change), a=a, b=b, relation=relation)

    def unlink(self, a, b, relation=None):
        if ident(a) is None or ident(b) is None:
            return fail("invalid_input", "need two item names", removed=0)

        def change(data):
            keep = [l for l in data["links"] if not ({l["a"], l["b"]} == {a, b} and relation in (None, l["relation"]))]
            removed = len(data["links"]) - len(keep)
            data["links"] = keep
            return removed
        removed = self._state.update(change)
        return ok(removed=removed) if removed else fail("not_found", "no such link", removed=0)

    def neighbours(self, item, relation=None):
        found = [{"item": l["b"] if l["a"] == item else l["a"], "relation": l["relation"]}
                 for l in self._state.load()["links"]
                 if item in (l["a"], l["b"]) and relation in (None, l["relation"])]
        return sorted(found, key=lambda n: (n["item"], n["relation"]))

    def path(self, a, b):
        """Shortest chain of linked items from a to b (breadth-first), or not_found."""
        links = self._state.load()["links"]
        known = {x for l in links for x in (l["a"], l["b"])}
        if not isinstance(a, str) or not isinstance(b, str) or a not in known or b not in known:
            return fail("not_found", "one or both items have no links", path=None)
        previous, queue = {a: None}, deque([a])
        while queue:
            item = queue.popleft()
            if item == b:
                chain = []
                while item is not None:
                    chain.append(item)
                    item = previous[item]
                return ok(path=chain[::-1], hops=len(chain) - 1)
            for n in self.neighbours(item):
                if n["item"] not in previous:
                    previous[n["item"]] = item
                    queue.append(n["item"])
        return fail("not_found", f"{a} and {b} are not connected", path=None)
