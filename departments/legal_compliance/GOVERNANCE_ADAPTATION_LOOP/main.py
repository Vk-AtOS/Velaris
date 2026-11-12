"""GOVERNANCE_ADAPTATION_LOOP: learns from human overrides which rules need review. Proposes; never applies.

Every time a person overrides an automated decision, that is evidence the rule
behind it may be wrong. record() stores outcomes {"rule", "decision",
"overridden": bool}. adapt() computes, per rule with at least MIN_SAMPLES outcomes:

    override_rate = overridden / total
    >= REVIEW_RATE        proposal "review_rule"  (people disagree with it often)
    == 0 and >= 4x MIN    proposal "keep"         (consistently accepted)

A proposal only becomes "accepted" when a governance admin (the caller) accepts it with
resolve(); even then this agent changes no rule. The owner of the policy
(POLICY_CONTROLLER) makes the change. Outcomes and proposals persist.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_name
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agentkit.infra_store import audit
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "GOVERNANCE_ADAPTATION_LOOP"
MIN_SAMPLES = 10
REVIEW_RATE = 0.3
MAX_OUTCOMES = 20000


class GovernanceAdaptationLoop:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    @staticmethod
    def _valid(o: Any) -> bool:
        return (isinstance(o, dict) and is_name(o.get("rule")) and o.get("decision") in ("allow", "deny")
                and isinstance(o.get("overridden"), bool))

    def record(self, outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(outcomes, list):
            return invalid("outcomes must be a list")
        good = [{"rule": o["rule"], "decision": o["decision"], "overridden": o["overridden"], "ts": time.time()}
                for o in outcomes if self._valid(o)]
        self._state.update(lambda d: d.__setitem__("outcomes", (d.get("outcomes", []) + good)[-MAX_OUTCOMES:]))
        return ok(recorded=len(good), rejected=len(outcomes) - len(good))

    def adapt(self, shaped: Optional[dict] = None) -> Dict[str, Any]:
        """Record any shaped["outcomes"], then return the current proposals.

        The input is echoed back as "adaptive_policy" for pipelines that pass it on unchanged.
        """
        recorded = None
        if isinstance(shaped, dict) and "outcomes" in shaped:
            recorded = self.record(shaped["outcomes"])
            if recorded["status"] != "ok":
                return {**recorded, "adaptive_policy": shaped, "proposals": []}

        def propose(data: Dict[str, Any]) -> List[Dict[str, Any]]:
            stats: Dict[str, List[int]] = {}
            for o in data.get("outcomes", []):
                s = stats.setdefault(o["rule"], [0, 0])
                s[0] += 1
                s[1] += o["overridden"]
            proposals = data.setdefault("proposals", {})
            out = []
            for rule, (total, over) in sorted(stats.items()):
                if total < MIN_SAMPLES:
                    continue
                rate = over / total
                kind = "review_rule" if rate >= REVIEW_RATE else "keep" if over == 0 and total >= 4 * MIN_SAMPLES else None
                if kind is None:
                    continue
                existing = next((p for p in proposals.values() if p["rule"] == rule and p["state"] == "proposed"), None)
                p = existing or {"id": uuid.uuid4().hex, "rule": rule, "state": "proposed"}
                p.update(kind=kind, override_rate=round(rate, 4), samples=total)
                proposals[p["id"]] = p
                out.append(dict(p))
            return out
        proposals = self._state.update(propose)
        return {"status": "ok", "adaptive_policy": shaped, "proposals": proposals,
                **({"recorded": recorded["recorded"]} if recorded else {})}

    def resolve(self, proposal_id: str, accept: bool, by: Optional[str] = None) -> Dict[str, Any]:
        """The current caller, a governance admin, accepts or rejects a proposal. Nothing else changes.

        `by`, if given, must be the caller's own id (velaris.core.access)."""
        if not isinstance(accept, bool):
            return invalid("accept must be true or false")
        caller, refused = check_caller(NAME, "resolve", {"id": str(proposal_id)[:64], "accept": accept},
                                       roles=GOVERNANCE_ADMINS, claimed=by)
        if refused:
            return refused
        by = caller.id

        def apply(data: Dict[str, Any]) -> Dict[str, Any]:
            p = data.get("proposals", {}).get(proposal_id) if isinstance(proposal_id, str) else None
            if p is None:
                return fail("unknown_proposal", "no such proposal")
            if p["state"] != "proposed":
                return fail("denied", f"proposal is already {p['state']}")
            p.update(state="accepted" if accept else "rejected", by=by)
            return ok(proposal=dict(p))
        result = self._state.update(apply)
        if result["status"] == "ok":
            audit(NAME, "proposal.resolved", {"id": proposal_id, "accept": accept, "by": by})
        return result
