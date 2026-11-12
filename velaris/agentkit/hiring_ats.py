"""Rules of the ATS that need no storage: stages and their allowed moves, consent, duplicate detection,
contact normalisation, retention. ATS_CORE (departments/hr/ATS_CORE) stores and gates; this decides.

Duplicate detection is a Fellegi-Sunter-shaped sum with hand-set weights (no trained model): agreement on a
field adds its weight, a missing field adds nothing. Matches go to a review list; nothing merges by itself.
A contact detail shared by three or more candidates (an agency, a family phone) stops counting as a key.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit import hiring_skills as sk
from velaris.agentkit.hiring_common import DAY, bad, iso, need_text, parse_date

STAGES = ("applied", "screening", "interview", "assessment", "offer", "hired", "rejected", "withdrawn")
TERMINAL = frozenset({"hired", "rejected", "withdrawn"})
TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "applied": ("screening", "rejected", "withdrawn"),
    "screening": ("interview", "rejected", "withdrawn"),
    "interview": ("assessment", "offer", "rejected", "withdrawn"),
    "assessment": ("interview", "offer", "rejected", "withdrawn"),
    "offer": ("hired", "rejected", "withdrawn"),
    "hired": (), "rejected": (), "withdrawn": (),
}
DECIDER_STAGES = frozenset({"offer", "hired"})        # moving here needs hiring_manager / hr_admin
REJECT_REASONS = ("must_have_not_evidenced", "interview_evaluation", "work_sample_evaluation", "position_closed",
                  "candidate_declined", "no_response", "other_documented")
REQ_STATES = ("draft", "approved", "open", "closed")
RETENTION_MAX_DAYS = 730
CHANNELS = ("web_form", "email", "in_person_recorded", "recruiter_recorded")
W_EMAIL, W_PHONE, W_PROFILE, W_NAME_HIGH, W_NAME_MID = 10.0, 8.0, 6.0, 3.0, 1.5
REVIEW_AT = 6.0
SHARED_KEY_LIMIT = 3
SOURCE = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")


def validate_consent(consent: Any, at: float) -> Dict[str, Any]:
    """The consent record, or a refusal. Purpose, notice version and a future retention date are all required."""
    if not isinstance(consent, dict):
        raise bad("consent is required before any candidate data is stored")
    purpose = need_text(consent.get("purpose"), "consent.purpose", 300)
    notice = need_text(consent.get("notice_version"), "consent.notice_version", 60)
    until = parse_date(consent.get("retention_until"), "consent.retention_until")
    if until <= at:
        raise bad("consent.retention_until must be in the future")
    if until > at + RETENTION_MAX_DAYS * DAY:
        raise bad(f"consent.retention_until is more than {RETENTION_MAX_DAYS} days away; keep personal data no longer than the purpose needs")
    channel = consent.get("channel", "web_form")
    if channel not in CHANNELS:
        raise bad(f"consent.channel must be one of {list(CHANNELS)}")
    return {"purpose": purpose, "notice_version": notice, "retention_until": iso(until)[:10], "retention_ts": until,
            "channel": channel, "talent_pool": bool(consent.get("talent_pool", False)), "given_at": at, "withdrawn_at": None}


def clean_source(source: Any) -> str:
    s = str(source or "").strip().lower()
    if not SOURCE.fullmatch(s):
        raise bad("source must be a short lowercase tag such as careers_page, linkedin, naukri, referral")
    return s


def email_key(email: Any) -> Optional[str]:
    e = str(email or "").strip().lower()
    return e if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e) and len(e) <= 254 else None


def phone_key(phone: Any) -> Optional[str]:
    d = re.sub(r"\D", "", str(phone or ""))
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 12 and d.startswith("91") or len(d) == 11 and d.startswith("0"):
        d = d[-10:]
    if len(d) == 10 and d[0] in "6789":
        return "+91" + d
    return "+" + d if 8 <= len(d) <= 15 and str(phone or "").strip().startswith(("+", "00")) else None


def profile_slug(url: Any) -> Optional[str]:
    m = re.match(r"(?:https?://)?(?:www\.)?([a-z0-9.-]+)/(?:in|u|profile|users?)/([a-z0-9_.-]+)/?", str(url or "").strip().lower())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def name_key(name: Any) -> str:
    return " ".join(sorted(re.findall(r"[a-z]+", str(name or "").lower())))


def person_keys(name: str, email: Any, phone: Any, profile: Any) -> Dict[str, Any]:
    return {"name_key": name_key(name), "email_key": email_key(email), "phone_key": phone_key(phone),
            "profile_key": profile_slug(profile)}


def duplicate_candidates(new: Dict[str, Any], people: Dict[str, Dict[str, Any]], org: str) -> List[Dict[str, Any]]:
    """Existing candidates of `org` that may be the same person as `new` (keys from person_keys), with the reasons."""
    mine = {cid: p for cid, p in people.items() if p.get("org") == org}
    shared = {f: {v for v in {p.get(f) for p in mine.values()} if v and sum(1 for q in mine.values() if q.get(f) == v) >= SHARED_KEY_LIMIT}
              for f in ("email_key", "phone_key", "profile_key")}
    out = []
    for cid, p in mine.items():
        score, reasons = 0.0, []
        for f, w, label in (("email_key", W_EMAIL, "same e-mail"), ("phone_key", W_PHONE, "same phone"),
                            ("profile_key", W_PROFILE, "same profile link")):
            if new.get(f) and new[f] == p.get(f) and new[f] not in shared[f]:
                score += w
                reasons.append(label)
        if new.get("name_key") and p.get("name_key"):
            r = SequenceMatcher(None, new["name_key"], p["name_key"]).ratio()
            if r >= 0.9:
                score, reasons = score + W_NAME_HIGH, reasons + [f"name very close ({r:.2f})"]
            elif r >= 0.75:
                score, reasons = score + W_NAME_MID, reasons + [f"name similar ({r:.2f})"]
        if score >= REVIEW_AT:
            out.append({"candidate_id": cid, "weight": score, "reasons": reasons})
    return sorted(out, key=lambda x: (-x["weight"], x["candidate_id"]))


def resolve_requirements(org: str, requirements: Any) -> Dict[str, Any]:
    """{"must": [{"skill": ..., "min_years": n}], "nice": [...], "min_total_years": n} with skills as table ids.
    Unknown skills are refused (propose them for review first)."""
    if not isinstance(requirements, dict) or not requirements.get("must"):
        raise bad("requirements needs a non-empty 'must' list of skills")
    out: Dict[str, Any] = {"must": [], "nice": []}
    seen = set()
    for kind in ("must", "nice"):
        for item in requirements.get(kind, []) or []:
            row = item if isinstance(item, dict) else {"skill": item}
            sid = sk.resolve_requirement(org, row.get("skill"))
            if sid in seen:
                raise bad(f"{sid} is listed twice")
            seen.add(sid)
            entry: Dict[str, Any] = {"skill_id": sid}
            if row.get("min_years") is not None:
                y = row["min_years"]
                if isinstance(y, bool) or not isinstance(y, (int, float)) or not 0 < y <= 40:
                    raise bad("min_years must be a number between 0 and 40")
                entry["min_years"] = float(y)
            out[kind].append(entry)
    if (t := requirements.get("min_total_years")) is not None:
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 <= t <= 50:
            raise bad("min_total_years must be a number between 0 and 50")
        out["min_total_years"] = float(t)
    return out


def due_for_deletion(candidates: Dict[str, Dict[str, Any]], org: str, at: float) -> List[Dict[str, Any]]:
    """Candidates whose consent has expired or was withdrawn. Ids and the reason only; deleting needs a person's approval."""
    due = []
    for cid, c in candidates.items():
        if c.get("org") != org or c.get("status") == "erased":
            continue
        consent = c["consent"]
        if consent.get("withdrawn_at"):
            due.append({"candidate_id": cid, "why": "consent_withdrawn", "since": iso(consent["withdrawn_at"])})
        elif consent["retention_ts"] <= at:
            due.append({"candidate_id": cid, "why": "retention_date_passed", "since": consent["retention_until"]})
    return sorted(due, key=lambda d: d["candidate_id"])
