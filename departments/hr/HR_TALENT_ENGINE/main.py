"""HR_TALENT_ENGINE: evidence that a candidate has the skills a role asks for. For a human.

evaluate(candidate, requirements, documents) takes the role's stated requirements
({"must_have": [...], "nice_to_have": [...]}) and, for each skill, reports WHERE it
was found:
  * in the candidate's declared skills (with the self-rating they gave), and
  * in the supplied documents ({"resume": "..."}): the line number and the line.
Matching is whole-term and case-insensitive ("java" is not found in "javascript").

What it deliberately does not do: there is NO score, NO ranking, NO percentage and
NO hire/reject output. `decision` is always None. A skill with no evidence means
"not found in what was supplied", which is a question for the interview, not a
verdict. Education and the cultural flags are not used in matching.

Documents are outside text: each is screened by velaris.intel.guard. A document
the guard blocks is not read, and hidden characters (a known way to stuff a
resume with invisible keywords) are reported to the reviewer.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit
from velaris.intel import guard

logger = logging.getLogger("HR_TALENT_ENGINE")
MAX_SKILLS = 100
MAX_DOC_CHARS = 200_000
MAX_QUOTES_PER_DOC = 3


@dataclass
class CandidateProfile:
    candidate_id: str
    experience_years: float
    skills: Dict[str, int]            # skill -> the candidate's own 0-10 rating
    education_level: str
    cultural_flags: Dict[str, bool]
    role: str


def _skill_list(raw: Any, name: str, errors: List[str]) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)) or len(raw) > MAX_SKILLS or any(kit.text(s, 80) is None for s in raw):
        errors.append(f"requirements.{name} must be a list of at most {MAX_SKILLS} skill names")
        return []
    return list(dict.fromkeys(s.strip() for s in raw))


class HRTalentEngine:
    SUPPORTED_EDU = {"highschool", "bachelor", "master", "phd"}
    SUPPORTED_ROLES = {"developer", "manager", "analyst", "designer", "engineer"}
    MAX_EXP = 60
    MAX_SKILL = 10
    CULTURE_WEIGHT = {"team_player": 0, "leadership": 0, "adaptability": 0, "communication": 0}   # recognised flags

    def health_check(self) -> Dict[str, Any]:
        return kit.health("HR_TALENT_ENGINE")

    def validate(self, c: CandidateProfile) -> List[str]:
        e = kit.dataclass_errors(c, ["experience_years"], ["skills", "cultural_flags"],
                                 texts=["education_level", "role"])
        if kit.text(getattr(c, "candidate_id", None), 64) is None:
            e.append("candidate_id invalid")
        if e:
            return e
        if c.experience_years < 0 or c.experience_years > self.MAX_EXP:
            e.append("experience_years invalid")
        if c.education_level not in self.SUPPORTED_EDU:
            e.append("unsupported education_level")
        if c.role not in self.SUPPORTED_ROLES:
            e.append("unsupported role")
        e += [f"invalid skill rating for {k}" for k, v in c.skills.items()
              if not isinstance(k, str) or kit.number(v, 0, self.MAX_SKILL) is None]
        e += [f"unsupported cultural flag {k}" for k in c.cultural_flags if k not in self.CULTURE_WEIGHT]
        return e

    def evaluate(self, c: CandidateProfile, requirements: Optional[Dict[str, Any]] = None,
                 documents: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        err = self.validate(c)
        if requirements is not None and not isinstance(requirements, dict):
            err.append("requirements must be an object with must_have and/or nice_to_have")
            requirements = None
        must = _skill_list((requirements or {}).get("must_have"), "must_have", err)
        nice = _skill_list((requirements or {}).get("nice_to_have"), "nice_to_have", err)
        if documents is not None and (not isinstance(documents, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) or len(v) > MAX_DOC_CHARS
                for k, v in documents.items())):
            err.append(f"documents must map a label to text of at most {MAX_DOC_CHARS} characters")
        if err:
            return kit.failed(err)
        if not must and not nice:
            return kit.needs_data("no role requirements supplied; there is nothing to match the candidate against",
                                  candidate_id=c.candidate_id, decision=None)
        readable: Dict[str, List[str]] = {}
        withheld, warnings = [], []
        for label, body in (documents or {}).items():
            scan = guard.scan(body, source=f"HR_TALENT_ENGINE:{label}")
            if scan.blocked:
                withheld.append(label)
                warnings.append(f"{label}: blocked by the guard and not read ({', '.join(f['rule'] for f in scan.findings)})")
                continue
            if any(f["rule"] == "hidden_characters" for f in scan.findings):
                warnings.append(f"{label}: contains hidden characters; compare with what a reader sees")
            readable[label] = guard.normalise(body).splitlines()
        declared = {k.strip().lower(): v for k, v in c.skills.items()}

        def evidence(skill: str) -> Dict[str, Any]:
            found = []
            if skill.lower() in declared:
                found.append({"where": "declared skills", "detail": f"self-rated {declared[skill.lower()]}/{self.MAX_SKILL}"})
            for label, lines in readable.items():
                hits = [(n, line) for n, line in enumerate(lines, 1) if kit.has_term(skill, line)]
                found += [{"where": f"{label}, line {n}", "quote": line.strip()[:200]}
                          for n, line in hits[:MAX_QUOTES_PER_DOC]]
            return {"skill": skill, "evidenced": bool(found), "evidence": found}

        must_rows, nice_rows = [evidence(s) for s in must], [evidence(s) for s in nice]
        return {
            "status": "ok", "candidate_id": c.candidate_id, "role": c.role,
            "must_have": must_rows, "nice_to_have": nice_rows,
            "not_evidenced": [r["skill"] for r in must_rows + nice_rows if not r["evidenced"]],
            "declared": {"experience_years": c.experience_years, "education_level": c.education_level},
            "documents_read": sorted(readable), "documents_withheld": withheld, "warnings": warnings,
            "decision": None, "human_decision_required": True,
            "note": "Evidence for a reviewer. No score, no ranking and no recommendation is produced; "
                    "'not evidenced' means not found in what was supplied.",
        }


if __name__ == "__main__":
    sample = CandidateProfile("c-001", 4, {"python": 8}, "bachelor", {}, "developer")
    print(json.dumps(HRTalentEngine().evaluate(
        sample, {"must_have": ["Python", "SQL"]}, {"resume": "Built ETL jobs in Python.\nWrote SQL reports."}), indent=2))
