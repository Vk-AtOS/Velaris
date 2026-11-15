"""Résumé text -> structured facts, each with the passage it came from. Deterministic; no model reads it.

Facts: skills (via the reviewed alias table), experience periods (date ranges with the line they were read
from), education lines, and the skill-list phrases the table does not know. Quotes are the résumé's own lines
with e-mail addresses, phone numbers and other identifiers masked (velaris.intel.guard.redact), and contact
details are not kept at all. The résumé text itself is not stored, only its SHA-256.

The text is untrusted data: guard.scan() flags hidden characters and instruction-like text for the human
reviewer. Nothing here ever obeys it (no model sees it), and a flagged résumé is processed like any other,
with the flag shown next to every result.
"""
from __future__ import annotations

import base64
import binascii
import re
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit import hiring_skills as sk
from velaris.agentkit.hiring_common import bad, digest, iso, new_id, now, sha, store
from velaris.intel import docs, guard

MAX_B64 = 14_000_000
MAX_QUOTE = 240
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
HEADINGS = {
    "skills": ("skills", "technical skills", "key skills", "core competencies", "technologies", "tools"),
    "experience": ("experience", "work experience", "employment", "professional experience", "work history"),
    "education": ("education", "academics", "qualifications", "academic qualifications"),
    "projects": ("projects", "project experience"),
    "summary": ("summary", "profile", "objective", "about me"),
    "certifications": ("certifications", "certificates", "courses"),
}
MAX_LINE, MAX_LINES = 2000, 20_000      # a résumé line or file beyond this is cut, not scanned (a candidate controls the text)
_YEARS = re.compile(r"(\d{1,2}(?:\.\d)?)[ \t]{0,8}\+?[ \t]{0,8}(?:years?|yrs?)\b", re.I)
_DATE = r"(?:(?:(?P<{p}m>[A-Za-z]{{3,9}})\.?,?\s+|(?P<{p}n>\d{{1,2}})/)?(?P<{p}y>(?:19|20)\d{{2}}))"
_RANGE = re.compile(_DATE.format(p="s") + r"\s*(?:-|–|—|to)\s*(?:" + _DATE.format(p="e")
                    + r"|(?P<now>present|current|till date|till now|now|ongoing))", re.I)
_EDU = re.compile(r"\b(?P<deg>B\.?E\.?|B\.?Tech|M\.?Tech|M\.?E\.?|B\.?Sc|M\.?Sc|BCA|MCA|B\.?Com|M\.?Com|MBA|Ph\.?D|"
                  r"Diploma|Bachelor|Master)\b")
_LEVEL = {"diploma": "diploma", "bachelor": "bachelor", "master": "master", "phd": "doctorate", "ph.d": "doctorate",
          "mba": "master", "mca": "master", "bca": "bachelor"}
_SPLIT = re.compile(r"[,;|•·●▪•\n]| and |\s-\s")


def read_text(filename: str, text: Optional[str], content_base64: Optional[str]) -> Tuple[str, str]:
    """(text, converter). Text is used as given; a file goes through velaris.intel.docs.convert (size limits there)."""
    if (text is None) == (content_base64 is None):
        raise bad("give exactly one of text or content_base64")
    if text is not None:
        if not isinstance(text, str) or not text.strip() or len(text) > docs.MAX_TEXT_CHARS:
            raise bad("text must be non-empty and within the size limit")
        return text, "text"
    if not isinstance(content_base64, str) or len(content_base64) > MAX_B64:
        raise bad("content_base64 is missing or too large")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise bad("content_base64 is not valid base64") from e
    name = filename if isinstance(filename, str) and 0 < len(filename) <= 200 else "resume.txt"
    try:
        md, kind = docs.convert(name, data)
    except docs.DocError as e:
        raise bad(str(e)[:300]) from e
    return md, kind


def _sections(lines: List[str]) -> List[str]:
    cur, out = "other", []
    for ln in lines:
        s = ln.strip().rstrip(":").strip("#* ").lower()
        if s and len(s) <= 32:
            for name, words in HEADINGS.items():
                if s in words:
                    cur = name
                    break
        out.append(cur)
    return out


def _mask(quote: str) -> str:
    q = " ".join(quote.split())
    q = guard.redact(q)[0]
    return q if len(q) <= MAX_QUOTE else q[:MAX_QUOTE - 1] + "…"


def _month(m: Optional[str], n: Optional[str], default: int) -> int:
    if m and m[:3].lower() in MONTHS:
        return MONTHS[m[:3].lower()]
    if n and 1 <= int(n) <= 12:
        return int(n)
    return default


def _periods(lines: List[str], today: float) -> List[Dict[str, Any]]:
    ty, tm = int(iso(today)[:4]), int(iso(today)[5:7])
    out = []
    for ln in lines:
        for m in _RANGE.finditer(ln):
            sy, sm = int(m["sy"]), _month(m["sm"], m["sn"], 1)
            if m["now"]:
                ey, em = ty, tm
            else:
                ey, em = int(m["ey"]), _month(m["em"], m["en"], 12 if not (m["em"] or m["en"]) else 1)
            a, b = sy * 12 + sm, ey * 12 + em
            if b < a or sy < 1970 or ey > ty + 1:
                continue
            out.append({"start": f"{sy}-{sm:02d}", "end": f"{ey}-{em:02d}", "months": b - a + 1,
                        "quote": _mask(ln), "_span": (a, b)})
    return out


def union_months(periods: List[Dict[str, Any]]) -> int:
    """Months covered by the periods, overlaps counted once."""
    total, end = 0, -1
    for a, b in sorted(p["_span"] for p in periods):
        if a > end:
            total, end = total + (b - a + 1), b
        elif b > end:
            total, end = total + (b - end), b
    return total


def _years_for_hits(line: str, hits: List[sk.Hit]) -> Dict[int, float]:
    """Assign each 'N years' in the line to the nearest skill mention within 30 characters."""
    out: Dict[int, float] = {}
    for ym in _YEARS.finditer(line):
        best = min(((min(abs(ym.start() - h.end), abs(h.start - ym.end())), i) for i, h in enumerate(hits)), default=None)
        if best and best[0] <= 30:
            out[best[1]] = max(out.get(best[1], 0.0), float(ym.group(1)))
    return out


def _unknown_phrases(line: str, hits: List[sk.Hit]) -> List[str]:
    for h in sorted(hits, key=lambda h: -h.start):
        line = line[:h.start] + "," + line[h.end:]
    if ":" in line and len(line.split(":", 1)[0].split()) <= 3:
        line = line.split(":", 1)[1]
    out = []
    for piece in _SPLIT.split(line):
        p = piece.strip(" .()-:/\t")
        if 1 < len(p) <= 40 and len(p.split()) <= 4 and not re.fullmatch(r"[\d\W]+", p) and "@" not in p:
            out.append(p)
    return out


def parse(org: str, text: str, table: Optional[sk.Table] = None, today: Optional[float] = None) -> Dict[str, Any]:
    table = table or sk.load_table(org)
    today = today if today is not None else now()
    lines = [ln[:MAX_LINE] for ln in text.splitlines()[:MAX_LINES]]       # every regex below runs per line: bound its input
    secs = _sections(lines)
    skills: Dict[str, Dict[str, Any]] = {}
    unknown: List[str] = []
    for ln, sec in zip(lines, secs):
        if not ln.strip():
            continue
        hits = table.find(ln)
        yrs = _years_for_hits(ln, hits)
        for i, h in enumerate(hits):
            e = skills.setdefault(h.skill_id, {"skill_id": h.skill_id, "label": table.label(h.skill_id), "mentions": []})
            e["mentions"].append({"section": sec, "quote": _mask(ln), "matched_text": h.surface, "matched_via": h.via,
                                  "years": yrs.get(i)})
        if sec == "skills" and ln.strip().rstrip(":").strip("#* ").lower() not in HEADINGS["skills"]:
            unknown += _unknown_phrases(ln, hits)
    for e in skills.values():
        stated = [m["years"] for m in e["mentions"] if m["years"] is not None]
        e["years_stated"] = max(stated) if stated else None
        e["mention_count"] = len(e["mentions"])
    periods = _periods(lines, today)
    education, seen = [], set()
    for ln, sec in zip(lines, secs):
        if (m := _EDU.search(ln)) and (sec == "education" or len(ln) < 160):
            lvl = _LEVEL.get(m["deg"].lower().replace(" ", ""), "bachelor" if m["deg"].lower().startswith("b") else "master")
            q = _mask(ln)
            if q not in seen:
                seen.add(q)
                education.append({"level": lvl, "quote": q})
    scan = guard.scan(text, source="hiring.resume")
    flags = [{"rule": f["rule"], "evidence": f["evidence"]} for f in scan.findings]
    flags += [{"rule": "keyword_repetition", "evidence": f"{e['label']} appears {e['mention_count']} times"}
              for e in skills.values() if e["mention_count"] >= 8]
    return {"text_sha256": sha(text), "characters": len(text), "skills": sorted(skills.values(), key=lambda s: s["skill_id"]),
            "experience_periods": [{k: v for k, v in p.items() if k != "_span"} for p in periods],
            "experience_months_union": union_months(periods), "education": education,
            "unknown_skill_phrases": sorted(set(unknown)),
            "screening": {"level": scan.level, "flags": flags,
                          "note": "For the human reviewer. The text was never given to a model and nothing in it was acted on."}}


# ---- stored evidence, per candidate (erasable) ----------------------------------------------------
def _state() -> Any:
    return store("RESUME_EVIDENCE", "evidence.json", {"items": {}, "erased": {}})


def save(org: str, candidate_id: str, filename: str, parsed: Dict[str, Any], by: str) -> Dict[str, Any]:
    ev_id = new_id("ev")
    rec = {"id": ev_id, "org": org, "candidate_id": candidate_id, "filename": filename[:120], "parsed": parsed,
           "created_at": now(), "created_by": by, "parsed_sha256": digest(parsed)}
    _state().update(lambda d: d["items"].__setitem__(ev_id, rec))
    return rec


def get(org: str, ev_id: str) -> Optional[Dict[str, Any]]:
    r = _state().load()["items"].get(str(ev_id))
    return r if r and r["org"] == org else None


def for_candidate(org: str, candidate_id: str) -> List[Dict[str, Any]]:
    return [r for r in _state().load()["items"].values() if r["org"] == org and r["candidate_id"] == candidate_id]


def export_candidate(org: str, candidate_id: str) -> Dict[str, Any]:
    return {"resume_evidence": for_candidate(org, candidate_id)}


def purge_candidate(org: str, candidate_id: str) -> int:
    def go(d: Dict[str, Any]) -> int:
        gone = [k for k, r in d["items"].items() if r["org"] == org and r["candidate_id"] == candidate_id]
        for k in gone:
            del d["items"][k]
        d["erased"][org] = d["erased"].get(org, 0) + len(gone)
        return len(gone)
    return _state().update(go)
