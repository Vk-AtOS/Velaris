"""CCSF fusion: merges snapshots of one entity reported by any number of systems.

fuse(sources) takes [{"source", "data", "ts"?}, ...] and returns the fields all
reporting systems agree on (with which systems reported each) and the fields
they disagree on, with every system's value and timestamp. It does not pick a
winner; that is CCSF_RESOLVER's job.
"""
from velaris.agentkit.aicore_a_common import health, invalid
from velaris.agentkit.aicore_a_fusion import clean_sources, fuse

NAME = "CCSF_FUSION"


class CCSF_FUSIONAgent:
    def health_check(self):
        return health(NAME)

    def fuse(self, sources):
        cleaned = clean_sources(sources)
        if isinstance(cleaned, str):
            return invalid(cleaned)
        result = fuse(cleaned)
        agreement = len(result["merged"]) / max(1, len(result["merged"]) + len(result["conflicts"]))
        return {"status": "ok" if not result["conflicts"] else "conflict", **result,
                "sources": [s["source"] for s in cleaned], "agreement": round(agreement, 4)}
