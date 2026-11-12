"""RESUME_EVIDENCE: résumé facts with their source passages, skills through a reviewed alias table, evidence
against a requisition, and a four-fifths audit aid.

No model reads a résumé here, so nothing in a résumé can instruct anything. The output is evidence for a
person; it states that it makes no hire or reject decision and carries no score and no ranking. Parsed facts are
stored per candidate under agent_dir("RESUME_EVIDENCE") (org-stamped, owner-only) and are removed by
ATS_CORE.erase_candidates; the résumé text itself is not stored, only its hash.
"""
import logging
from typing import Any, Dict, List, Optional

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_match as hm
from velaris.agentkit import hiring_resume as hr
from velaris.agentkit import hiring_skills as sk
from velaris.agentkit.hiring_common import HIRING, RECRUITING, HiringError, acts, audit, hid, reads
from velaris.agentkit.results import ok
from velaris.core.access import authorize_read

logger = logging.getLogger("RESUME_EVIDENCE")
AGENT = "RESUME_EVIDENCE"


class ResumeEvidence:
    """Résumé -> facts + evidence. Never a decision about a person."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "seed_skills": len(sk.load_table("-").skills)}

    @acts(AGENT, RECRUITING)
    def parse_resume(self, caller, candidate_id: str, filename: str = "resume.txt", text: Optional[str] = None,
                     content_base64: Optional[str] = None) -> Dict[str, Any]:
        """Parse a résumé (plain text, or a file as base64: pdf/docx/txt) into facts with source passages and store them for
        this candidate. Skill-list phrases the table does not know are queued for review, never guessed."""
        org = caller.org
        if not hc.candidate_known(org, candidate_id):
            raise HiringError("not_found", "no such candidate (add the candidate, with consent, first)")
        body, converter = hr.read_text(filename, text, content_base64)
        parsed = hr.parse(org, body)
        audit(AGENT, "resume.parsed", org, caller, candidate=hid(org, candidate_id), resume_sha256=parsed["text_sha256"],
              flags=len(parsed["screening"]["flags"]))
        sk.note_unknown(org, parsed["unknown_skill_phrases"])
        rec = hr.save(org, str(candidate_id), filename, parsed, caller.id)
        return ok(evidence_id=rec["id"], converter=converter, parsed=parsed)

    @reads(AGENT, HIRING)
    def match_requisition(self, caller, evidence_id: str, requisition_id: str) -> Dict[str, Any]:
        """Evidence and gaps of one parsed résumé against a requisition's must/nice skills, with the arithmetic. No decision,
        no ranking, no score. Résumé facts identify a person, so access.authorize_read('identity') applies."""
        org = caller.org
        ev = hr.get(org, evidence_id)
        if not ev:
            raise HiringError("not_found", "no such evidence record")
        authorize_read("identity", ev["candidate_id"], agent=AGENT, caller=caller, org=org)
        req = hc.load_requisition(org, requisition_id)
        if not req:
            raise HiringError("not_found", "no such requisition")
        return ok(evidence_id=evidence_id, candidate_id=ev["candidate_id"],
                  **hm.match_evidence(ev["parsed"], req, sk.load_table(org)))

    @reads(AGENT, HIRING)
    def get_evidence(self, caller, evidence_id: str) -> Dict[str, Any]:
        """The stored facts of one résumé (identity data: authorize_read)."""
        ev = hr.get(caller.org, evidence_id)
        if not ev:
            raise HiringError("not_found", "no such evidence record")
        authorize_read("identity", ev["candidate_id"], agent=AGENT, caller=caller, org=caller.org)
        return ok(evidence=ev)

    # ---- the reviewed alias table ------------------------------------------------------------------
    @reads(AGENT, HIRING)
    def unknown_skills(self, caller) -> Dict[str, Any]:
        """Skill-list phrases seen in résumés that the table does not know, most frequent first (phrases only, no people)."""
        return ok(unknown=sk.unknown(caller.org))

    @reads(AGENT, HIRING)
    def alias_proposals(self, caller, status: str = "proposed") -> Dict[str, Any]:
        return ok(proposals=sk.proposals(caller.org, status))

    @acts(AGENT, RECRUITING)
    def propose_alias(self, caller, surface: str, skill_id: str = "", new_skill: str = "") -> Dict[str, Any]:
        """Queue a phrase for review: map it to an existing skill_id, or name a new skill. It is not used until reviewed."""
        row = sk.propose(caller.org, caller.id, surface, skill_id or None, new_skill or None)
        audit(AGENT, "alias.proposed", caller.org, caller, alias=hid(caller.org, row["id"]))
        return ok(proposal=row)

    @acts(AGENT, frozenset())
    def review_alias(self, caller, proposal_id: str, approve: bool, esco_id: str = "", no_esco_match: bool = False) -> Dict[str, Any]:
        """HR admin approves or rejects a proposal (not their own). Approving needs an ESCO skill URI/UUID from an ESCO release
        in `esco_id`, or `no_esco_match=true` (the admin looked and there is none); stored with who and when. No id is ever
        supplied by the code. Approved aliases are used from the next parse."""
        audit(AGENT, "alias.reviewed", caller.org, caller, alias=hid(caller.org, proposal_id), approve=bool(approve),
              esco_no_match=no_esco_match is True)
        return ok(proposal=sk.review(caller.org, caller.id, proposal_id, bool(approve), esco_id or None, no_esco_match is True))

    @reads(AGENT, HIRING)
    def list_skills(self, caller) -> Dict[str, Any]:
        t = sk.load_table(caller.org)
        return ok(skills=[{"id": i, "label": v["label"], "esco_id": v["esco_id"], "source": v["source"]} for i, v in sorted(t.skills.items())])

    # ---- audit aid ----------------------------------------------------------------------------------
    @reads(AGENT, RECRUITING)
    def bias_audit(self, caller, records: List[Dict[str, Any]], stages: List[str], min_count: int = hm.MIN_GROUP) -> Dict[str, Any]:
        """Four-fifths impact ratios per funnel step for group labels the caller supplies (not stored). An audit aid."""
        return ok(**hm.impact_ratios(records, stages, min_count))
