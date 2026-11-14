"""CSG state align: compares the state something should have with the state it has, and produces the fix.

align(expected, actual) returns a patch: the fields to add, replace or remove
to make `actual` equal `expected` (nested objects are compared field by field,
addressed by dotted paths). apply() applies such a patch to a state and returns
the new state without modifying the input.
ponytail: dotted paths, so field names that themselves contain a dot are not
supported; switch to path lists if such keys ever appear.
"""
import copy

from velaris.agentkit.results import fail, health
from velaris.agentkit.aicore_a_fusion import flatten

NAME = "CSG_STATEALIGN"


class CSG_STATEALIGNAgent:
    def health_check(self):
        return health(NAME)

    def align(self, expected, actual):
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            return fail("invalid_input", "expected and actual must be objects", aligned=False, patch=[])
        want, have = flatten(expected), flatten(actual)
        patch = [{"op": "add", "path": p, "value": want[p]} for p in sorted(want.keys() - have.keys())]
        patch += [{"op": "replace", "path": p, "value": want[p], "was": have[p]}
                  for p in sorted(want.keys() & have.keys()) if want[p] != have[p]]
        patch += [{"op": "remove", "path": p, "was": have[p]} for p in sorted(have.keys() - want.keys())]
        return {"status": "ok", "aligned": not patch, "patch": patch,
                "matching_fields": len(want.keys() & have.keys()) - sum(1 for o in patch if o["op"] == "replace")}

    def apply(self, state, patch):
        if not isinstance(state, dict) or not isinstance(patch, list):
            return fail("invalid_input", "state must be an object and patch a list", state=None)
        result = copy.deepcopy(state)
        if all(isinstance(o, dict) for o in patch):
            patch = sorted(patch, key=lambda o: o.get("op") != "remove")      # stable: removals first, so a field that turns from scalar/empty into a nested object (or back) keeps its new value
        for op in patch:
            if not isinstance(op, dict) or op.get("op") not in ("add", "replace", "remove") or not isinstance(op.get("path"), str):
                return fail("invalid_input", f"bad patch operation {op!r}", state=None)
            *parents, leaf = op["path"].split(".")
            node = result
            for key in parents:
                if not isinstance(node.get(key), dict):
                    if op["op"] == "remove":
                        node = None         # nothing to remove below a scalar or a missing object
                        break
                    node[key] = {}          # an empty object or scalar on the way to a deeper field is replaced
                node = node[key]
            if node is None:
                continue
            if op["op"] == "remove":
                node.pop(leaf, None)
            elif "value" not in op:
                return fail("invalid_input", f"operation on {op['path']} has no value", state=None)
            else:
                node[leaf] = copy.deepcopy(op["value"])
        return {"status": "ok", "state": result, "applied": len(patch)}
