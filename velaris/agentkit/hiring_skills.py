"""Skill normalisation through a reviewed alias table.

Surface forms ("reactjs", "K8s") become skill ids by exact phrase lookup, longest phrase first, over tokens
that both the table and the résumé go through the same tokeniser. There is no fuzzy or model guess: a phrase
that is not in the table is reported as unknown, and a person adds it (proposal -> review). Only `reviewed`
rows are used for matching. The shipped seed (departments/hr/RESUME_EVIDENCE/skills_seed.json) is reviewed by
whoever ships it; its `esco_id` fields are null until an admin fills them from an ESCO release (not bundled:
no network at build time, and a made-up id would be worse than none).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit.hiring_common import HiringError, bad, new_id, now, need_text, store

SEED_PATH = Path(__file__).resolve().parents[2] / "departments" / "hr" / "RESUME_EVIDENCE" / "skills_seed.json"
TOKEN = re.compile(r"\.net|[a-z0-9]+(?:\+\+|#)?", re.I)
MAX_PHRASE = 5
Key = Tuple[str, ...]


def tokens(text: str) -> List[Tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def key_of(surface: str) -> Key:
    return tuple(t for t, _, _ in tokens(surface))


@dataclass(frozen=True)
class Hit:
    skill_id: str
    start: int
    end: int
    surface: str
    via: str            # seed | reviewed


class Table:
    def __init__(self, skills: Dict[str, Dict[str, Any]], index: Dict[Key, Tuple[str, str]]) -> None:
        self.skills, self.index = skills, index

    def label(self, skill_id: str) -> str:
        return self.skills.get(skill_id, {}).get("label", skill_id)

    def lookup(self, surface: str) -> Optional[str]:
        """Skill id for an id, label or reviewed alias; None when unknown."""
        if surface in self.skills:
            return surface
        hit = self.index.get(key_of(surface))
        return hit[0] if hit else None

    def find(self, text: str) -> List[Hit]:
        """Every table phrase in `text`, longest first, a token used by at most one hit."""
        toks = tokens(text)
        hits: List[Hit] = []
        i = 0
        while i < len(toks):
            for n in range(min(MAX_PHRASE, len(toks) - i), 0, -1):
                k = tuple(t for t, _, _ in toks[i:i + n])
                if k in self.index:
                    sid, via = self.index[k]
                    hits.append(Hit(sid, toks[i][1], toks[i + n - 1][2], text[toks[i][1]:toks[i + n - 1][2]], via))
                    i += n
                    break
            else:
                i += 1
        return hits


def _seed() -> Dict[str, Any]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _state() -> Any:
    return store("RESUME_EVIDENCE", "aliases.json", {"rows": {}, "unknown": {}})


def load_table(org: str) -> Table:
    skills: Dict[str, Dict[str, Any]] = {}
    index: Dict[Key, Tuple[str, str]] = {}
    for s in _seed()["skills"]:
        skills[s["id"]] = {"label": s["label"], "esco_id": s.get("esco_id"), "source": "seed"}
        for surface in [s["label"], s["id"], *s.get("aliases", [])]:
            if (k := key_of(surface)):
                index.setdefault(k, (s["id"], "seed"))
    rows = _state().load().get("rows", {})
    for r in rows.values():
        if r.get("org") == org and r.get("status") == "reviewed" and r.get("new_skill"):
            skills[r["skill_id"]] = {"label": r["new_skill"], "esco_id": r.get("esco_id"), "source": "reviewed"}
    for r in rows.values():
        if r.get("org") == org and r.get("status") == "reviewed" and r["skill_id"] in skills:
            index.setdefault(tuple(r["key"]), (r["skill_id"], "reviewed"))
    return Table(skills, index)


def propose(org: str, by: str, surface: str, skill_id: Optional[str] = None, new_skill: Optional[str] = None) -> Dict[str, Any]:
    """Queue an alias for review. Either an existing skill id, or a label for a skill the table lacks."""
    surface = need_text(surface, "surface", 80)
    k = key_of(surface)
    if not k or len(k) > MAX_PHRASE:
        raise bad(f"surface must have 1 to {MAX_PHRASE} words")
    table = load_table(org)
    if (existing := table.lookup(surface)):
        raise HiringError("exists", f"'{surface}' already maps to {existing}")
    if (skill_id is None) == (new_skill is None):
        raise bad("give exactly one of skill_id (an existing skill) or new_skill (a label for a new one)")
    if skill_id is not None:
        if skill_id not in table.skills:
            raise bad(f"skill_id {skill_id} is not in the table")
        sid, label = skill_id, None
    else:
        label = need_text(new_skill, "new_skill", 80)
        sid = "local:" + (re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "skill")
        if sid in table.skills:
            raise bad(f"{sid} exists; use skill_id")
    row_id = new_id("alias")
    row = {"id": row_id, "org": org, "surface": surface, "key": list(k), "skill_id": sid, "new_skill": label,
           "status": "proposed", "proposed_by": by, "proposed_at": now(), "reviewed_by": None}

    def add(d: Dict[str, Any]) -> None:
        if any(r["org"] == org and r["status"] == "proposed" and r["key"] == list(k) for r in d["rows"].values()):
            raise HiringError("exists", "that phrase is already waiting for review")
        d["rows"][row_id] = row
        d["unknown"].get(org, {}).pop(" ".join(k), None)
    _state().update(add)
    return row


def review(org: str, by: str, row_id: str, approve: bool, esco_id: Optional[str] = None) -> Dict[str, Any]:
    """Approve or reject a proposal. The reviewer must differ from the proposer."""
    def apply(d: Dict[str, Any]) -> Dict[str, Any]:
        r = d["rows"].get(row_id)
        if not r or r["org"] != org:
            raise HiringError("not_found", "no such alias proposal")
        if r["status"] != "proposed":
            raise HiringError("conflict", f"already {r['status']}")
        if r["proposed_by"] == by:
            raise HiringError("denied", "a proposal is reviewed by someone other than its proposer")
        r.update(status="reviewed" if approve else "rejected", reviewed_by=by, reviewed_at=now())
        if approve and esco_id:
            r["esco_id"] = need_text(esco_id, "esco_id", 200)
        return dict(r)
    return _state().update(apply)


def proposals(org: str, status: str = "proposed") -> List[Dict[str, Any]]:
    return [r for r in _state().load().get("rows", {}).values() if r["org"] == org and r["status"] == status]


def note_unknown(org: str, phrases: List[str]) -> None:
    """Count skill-list phrases the table does not know, for the review queue (phrases, never people)."""
    if not phrases:
        return

    def add(d: Dict[str, Any]) -> None:
        bucket = d["unknown"].setdefault(org, {})
        for p in phrases:
            k = " ".join(key_of(p))
            if k and len(bucket) < 2000:
                e = bucket.setdefault(k, {"phrase": p[:60], "count": 0})
                e["count"] += 1
    _state().update(add)


def unknown(org: str) -> List[Dict[str, Any]]:
    b = _state().load().get("unknown", {}).get(org, {})
    return sorted(b.values(), key=lambda e: (-e["count"], e["phrase"]))


def resolve_requirement(org: str, surface: Any) -> str:
    """A requisition's skill as a table id; unknown skills are refused, never guessed."""
    sid = load_table(org).lookup(need_text(surface, "skill", 80))
    if sid is None:
        raise bad(f"unknown skill '{str(surface)[:40]}': propose it for review (propose_alias) before using it in a requisition")
    return sid

