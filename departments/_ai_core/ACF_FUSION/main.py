"""ACF fusion: merges two records about the same thing and reports where they disagree.

fuse(a, b) takes two objects (plain data, or {"source", "data", "ts"}) and
returns the fields they agree on or that only one has, which source each came
from, and the conflicting fields with both values. Conflicts are left out of
the merged record; CCSF_RESOLVER can settle them by a declared rule.
"""
from velaris.agentkit.results import health
from velaris.agentkit.aicore_a_fusion import clean_sources, fuse

NAME = "ACF_FUSION"


def _as_source(value, default_name):
    if isinstance(value, dict) and "data" in value and "source" in value:
        return value
    return {"source": default_name, "data": value}


class ACFFusionAgent:
    def health_check(self):
        return health(NAME)

    def fuse(self, a, b):
        """`fusion` is True only when both inputs were usable; `clean` is True when nothing conflicted."""
        sources = clean_sources([_as_source(a, "a"), _as_source(b, "b")])
        if isinstance(sources, str):
            return {"fusion": False, "status": "invalid_input", "reason": sources, "a": a, "b": b}
        result = fuse(sources)
        return {"fusion": True, "status": "ok" if not result["conflicts"] else "conflict",
                "clean": not result["conflicts"], "a": a, "b": b, **result}
