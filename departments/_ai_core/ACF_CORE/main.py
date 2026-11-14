"""ACF core: the intake pipeline that chains the other three ACF agents.

process(raw) runs ACF_CONTEXT (screen and envelope), then, when other sources
describe the same record, ACF_FUSION against each in turn, then ACF_ROUTER.
It stops at the first stage that refuses, and says which. A record whose
sources conflict is still routed, with the conflicts attached and
`signal.conflicted` set so a routing rule can send it to review.
"""
from velaris.agentkit.results import fail, health
from velaris.agents.ACF_CONTEXT.main import LEVELS, ACFContextAgent
from velaris.agents.ACF_FUSION.main import ACFFusionAgent
from velaris.agents.ACF_ROUTER.main import ACFRouterAgent

NAME = "ACF_CORE"


class ACFCoreAgent:
    def __init__(self, rules=None, default_destination="triage"):
        self.router = ACFRouterAgent(rules, default_destination)

    def health_check(self):
        return health(NAME)

    def process(self, raw, sources=None, context=None, now=None):
        """sources: optional [{"source", "data", "ts"?}] to merge into a record signal."""
        envelope = ACFContextAgent().contextualize(raw, context, now)
        if not envelope["contextualized"]:
            return fail(envelope["status"], envelope["reason"], stage="context", routed=False, destination=None)
        signal, conflicts = envelope["signal"], []
        if sources:
            if signal["kind"] != "record" or not isinstance(sources, list):
                return fail("invalid_input", "sources must be a list and can only be merged into a record",
                            stage="fusion", routed=False, destination=None)
            merged = {"source": (context or {}).get("source", "input"), "data": signal["content"]}
            for other in sources:
                fused = ACFFusionAgent().fuse(merged, other)
                if not fused["fusion"]:
                    return fail("invalid_input", fused["reason"], stage="fusion", routed=False, destination=None)
                conflicts += fused["conflicts"]
                merged = {"source": merged["source"], "data": fused["merged"]}
            # The other sources were never screened: scan and mask the merged record like the first one.
            rescreened = ACFContextAgent().contextualize(merged["data"], context, now)
            if not rescreened["contextualized"]:
                return fail(rescreened["status"], rescreened["reason"], stage="fusion", routed=False, destination=None)
            signal["content"] = rescreened["signal"]["content"]      # flattened, agreed fields only, masked
            for kind, n in rescreened["signal"]["redactions"].items():
                signal["redactions"][kind] = signal["redactions"].get(kind, 0) + n
            if LEVELS.index(rescreened["signal"]["risk"]) > LEVELS.index(signal["risk"]):
                signal["risk"] = rescreened["signal"]["risk"]
        signal["conflicted"] = bool(conflicts)
        routed = self.router.route(signal)
        return {**routed, "stage": "routed" if routed["routed"] else "router", "conflicts": conflicts}
