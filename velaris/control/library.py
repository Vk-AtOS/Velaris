"""The seeded tasks. Each is narrow and scripted: the code computes what the result must be, the
schema lets only the matching actions through, and verify() reads the result back.

  files.organise        sort files in a jailed folder into sub-folders by extension, or lower-case their names
  docs.collect          put the documents of a jailed folder into the document library
  files.export_report   write a CSV report (rows given by the caller) into a jailed folder
  browser.fill_form     fill a web form from structured data; submitting needs a named approver
  terminal.diagnostics  run a bundle of read-only commands
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List
from urllib.parse import urlsplit

from velaris.control.checkpoint import Journal
from velaris.control.core import Action, Element, Surface, sha
from velaris.control.policy import ActionSpec
from velaris.control.tasks import Check, Task, register

_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_. -]{0,78}\Z")
DOC_EXTS = (".txt", ".md", ".csv", ".docx", ".xlsx", ".pptx", ".pdf")
_ANY = frozenset({"file", "directory"})


def _only(params: Dict[str, Any], allowed: Dict[str, Any]) -> None:
    if not isinstance(params, dict) or set(params) - set(allowed):
        raise ValueError(f"parameters may only be: {sorted(allowed)}")


def _folder(params: Dict[str, Any]) -> str:
    f = params.get("folder", ".")
    if not isinstance(f, str) or not f or len(f) > 200:
        raise ValueError("folder must be a relative folder name")
    return f


def _top(listing: Dict[str, str]) -> Dict[str, str]:
    return {p: h for p, h in listing.items() if "/" not in p}


# ── files.organise ───────────────────────────────────────────────────────────
def _org_validate(p: Dict[str, Any]) -> Dict[str, Any]:
    _only(p, {"folder": 0, "rule": 0})
    if p.get("rule") not in ("by_extension", "lowercase"):
        raise ValueError("rule must be by_extension or lowercase")
    return {"folder": _folder(p), "rule": p["rule"]}


def _org_expected(p: Dict[str, Any], s: Surface) -> Dict[str, Any]:
    before = s.listing()                                       # type: ignore[attr-defined]
    moves: Dict[str, str] = {}
    for name in sorted(_top(before)):
        if p["rule"] == "lowercase":
            dst = name.lower()
        else:
            ext = name.rsplit(".", 1)[1].lower() if "." in name.strip(".") else "other"
            dst = f"{ext if re.fullmatch(r'[a-z0-9]{1,10}', ext) else 'other'}/{name}"
        if dst != name:
            moves[name] = dst
    dsts = list(moves.values())
    if len(set(dsts)) != len(dsts) or any(d in before for d in dsts):
        raise ValueError("two files would end up with the same name; nothing was started")
    existing = set(s.dirs())                                   # type: ignore[attr-defined]
    mkdirs = sorted({d.split("/")[0] for d in dsts if "/" in d} - existing)
    final = {moves.get(path, path): h for path, h in before.items()}
    return {"moves": moves, "mkdirs": mkdirs, "final": final}


def _org_verify(p: Dict[str, Any], exp: Any, s: Surface, j: Journal) -> List[Check]:
    now = s.listing()                                          # type: ignore[attr-defined]
    missing, extra = sorted(set(exp["final"]) - set(now)), sorted(set(now) - set(exp["final"]))
    wrong = sorted(k for k in set(now) & set(exp["final"]) if now[k] != exp["final"][k])
    return [Check("every file is where the rule puts it", not missing and not extra,
                  f"missing {missing[:5]}, unexpected {extra[:5]}"),
            Check("every file has its original bytes", not wrong, f"changed {wrong[:5]}")]


register(Task(
    "files.organise", "Organise files by a rule", "files", _org_validate,
    lambda p: f"Organise the files in the folder by rule '{p['rule']}': create each missing sub-folder, then move each "
              f"file to its place. Use only moves and folders the rule needs; reply final when everything is in place.",
    _org_expected,
    {"read": ActionSpec(_ANY),
     "mkdir": ActionSpec(frozenset({"directory"}), check=lambda a, e, x: e.name == "." and a.to in x["mkdirs"]),
     "move": ActionSpec(frozenset({"file"}), check=lambda a, e, x: x["moves"].get(e.name) == a.to)},
    _org_verify, max_steps=40, description="Sort or rename the files in one folder by a fixed rule; undoable."))


# ── docs.collect ─────────────────────────────────────────────────────────────
def _col_validate(p: Dict[str, Any]) -> Dict[str, Any]:
    _only(p, {"folder": 0})
    return {"folder": _folder(p)}


def _col_expected(p: Dict[str, Any], s: Surface) -> Dict[str, Any]:
    return {"files": {n: h for n, h in sorted(_top(s.listing()).items()) if n.lower().endswith(DOC_EXTS)}}   # type: ignore[attr-defined]


def _col_verify(p: Dict[str, Any], exp: Any, s: Surface, j: Journal) -> List[Check]:
    if s.sink is None:                                         # type: ignore[attr-defined]
        return [Check("the library can be read back", False, "no document library is connected")]
    held = {d["name"]: d["sha256"] for d in s.sink.documents()}  # type: ignore[attr-defined]
    bad = sorted(n for n, h in exp["files"].items() if held.get(n) != h)
    return [Check("every document is in the library with its own content hash", not bad, f"not matching: {bad[:5]}")]


register(Task(
    "docs.collect", "Collect documents into the document library", "files", _col_validate,
    lambda p: "Ingest every document file of the folder into the document library, one file at a time. "
              "Reply final when each has been ingested.",
    _col_expected,
    {"read": ActionSpec(_ANY),
     "ingest": ActionSpec(frozenset({"file"}), check=lambda a, e, x: e.name in x["files"])},
    _col_verify, max_steps=40, description="Ingest the documents of one folder into the library; compensatable."))


# ── files.export_report ──────────────────────────────────────────────────────
def _cell(v: Any) -> str:
    t = str(v)
    # a spreadsheet must not run a cell as a formula: guard the first character and the first
    # non-blank one (tab, CR, leading spaces are skipped by some spreadsheet programs)
    first = t.lstrip(" \t\r\n\x0b\x0c")[:1]
    return "'" + t if t[:1] in ("\t", "\r") or first in ("=", "+", "-", "@") else t


def _rep_validate(p: Dict[str, Any]) -> Dict[str, Any]:
    _only(p, {"folder": 0, "name": 0, "header": 0, "rows": 0})
    name, header, rows = p.get("name"), p.get("header"), p.get("rows")
    if not (isinstance(name, str) and _NAME.match(name)):
        raise ValueError("name must be a plain file name")
    if not (isinstance(header, list) and header and isinstance(rows, list) and len(rows) <= 2000
            and all(isinstance(r, list) and len(r) == len(header) for r in rows)):
        raise ValueError("header must be a list and rows a list of lists as long as the header (at most 2000)")
    return {"folder": _folder(p), "name": name, "header": [str(h) for h in header],
            "rows": [[str(c) for c in r] for r in rows]}


def _rep_expected(p: Dict[str, Any], s: Surface) -> Dict[str, Any]:
    if p["name"] in s.listing():                               # type: ignore[attr-defined]
        raise ValueError("a file with that name already exists in the folder")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([_cell(h) for h in p["header"]])
    w.writerows([[_cell(c) for c in r] for r in p["rows"]])
    return {"name": p["name"], "content": buf.getvalue(), "sha": sha(buf.getvalue().encode())}


def _rep_verify(p: Dict[str, Any], exp: Any, s: Surface, j: Journal) -> List[Check]:
    now = s.listing().get(exp["name"])                         # type: ignore[attr-defined]
    return [Check("the report file exists with exactly the expected bytes", now == exp["sha"],
                  "missing" if now is None else "content differs" if now != exp["sha"] else "")]


register(Task(
    "files.export_report", "Export a report to a folder", "files", _rep_validate,
    lambda p: f"Create the report file '{p['name']}' in the folder with exactly the CSV content given by the system "
              f"(it is checked byte for byte); then reply final.",
    _rep_expected,
    {"create": ActionSpec(frozenset({"directory"}),
                          check=lambda a, e, x: e.name == "." and a.to == x["name"] and a.value == x["content"])},
    _rep_verify, max_steps=6, description="Write one CSV report whose content the code computed; undoable."))


# ── browser.fill_form ────────────────────────────────────────────────────────
def _form_validate(p: Dict[str, Any]) -> Dict[str, Any]:
    _only(p, {"url": 0, "fields": 0, "submit": 0})
    url, fields = p.get("url"), p.get("fields")
    u = urlsplit(url) if isinstance(url, str) else None
    if not (u and u.scheme in ("http", "https") and u.hostname):
        raise ValueError("url must be an http(s) address")
    if not (isinstance(fields, dict) and 0 < len(fields) <= 30 and all(
            isinstance(k, str) and 0 < len(k) <= 80 and isinstance(v, str) and len(v) <= 1000 for k, v in fields.items())):
        raise ValueError("fields must map up to 30 field names to text values")
    return {"url": url, "fields": fields, "submit": bool(p.get("submit", False))}


def _form_verify(p: Dict[str, Any], exp: Any, s: Surface, j: Journal) -> List[Check]:
    submitted = any(o["kind"] == "browser.click" for o in j.ops())
    if submitted:                                      # the page has moved on: ask the system of record
        records = getattr(s.driver, "records", None)  # type: ignore[attr-defined]
        if records is None:
            return [Check("the submission can be read back", False, "this browser cannot read the record back")]
        last = (records() or [{}])[-1]
        bad = sorted(k for k, v in exp["fields"].items() if last.get(k) != v)
        return [Check("the stored submission holds the expected values", not bad, f"not matching: {bad}")]
    obs = s.observe()                                  # a SECOND, fresh observation of the page
    bad = sorted(k for k, v in exp["fields"].items()
                 if not any(e.role in ("textbox", "combobox") and e.name == k and e.value == v for e in obs.elements))
    return [Check("the page now shows every expected value", not bad, f"not matching: {bad}")]


_FIELD = lambda a, e, x: x["fields"].get(e.name) == a.value                                        # noqa: E731
register(Task(
    "browser.fill_form", "Fill a web form from structured data", "browser", _form_validate,
    lambda p: "Open the form address, then fill each field with its given value. Do not click anything else. "
              + ("Then submit the form (a person will be asked)." if p["submit"] else "Do NOT submit the form."),
    lambda p, s: {"url": p["url"], "fields": p["fields"], "submit": p["submit"]},
    {"navigate": ActionSpec(frozenset({"page"}), check=lambda a, e, x: a.to == x["url"]),
     "fill": ActionSpec(frozenset({"textbox"}), check=_FIELD),
     "select": ActionSpec(frozenset({"combobox"}), check=_FIELD),
     "submit": ActionSpec(frozenset({"button"}), name_re=r"submit|save|send|register", approval=True,
                          check=lambda a, e, x: x["submit"] is True)},
    _form_verify, hosts=lambda p: [urlsplit(p["url"]).hostname or ""], max_steps=40,
    description="Fill a form up to, but not including, submit. Submitting is a separate step that needs approval."))


# ── terminal.diagnostics ─────────────────────────────────────────────────────
BUNDLES = {"system": ["uname -a", "uptime", "date"], "disk": ["df -h"]}


def _diag_validate(p: Dict[str, Any]) -> Dict[str, Any]:
    _only(p, {"bundle": 0})
    if p.get("bundle") not in BUNDLES:
        raise ValueError(f"bundle must be one of {sorted(BUNDLES)}")
    return {"bundle": p["bundle"]}


def _diag_verify(p: Dict[str, Any], exp: Any, s: Surface, j: Journal) -> List[Check]:
    ran = {" ".join(o["data"]["argv"]) for o in j.ops() if o["kind"] == "terminal.run" and o["data"].get("rc") == 0}
    missing = [c for c in exp["commands"] if c not in ran]
    return [Check("every command of the bundle ran and exited 0", not missing, f"did not complete: {missing}")]


register(Task(
    "terminal.diagnostics", "Run a bundle of read-only diagnostic commands", "terminal", _diag_validate,
    lambda p: f"Run each of these commands once, exactly as written: {', '.join(BUNDLES[p['bundle']])}. Then reply final.",
    lambda p, s: {"commands": BUNDLES[p["bundle"]]},
    {"run": ActionSpec(frozenset({"command"}),
                       check=lambda a, e, x: f"{e.name} {a.value or ''}".strip() in x["commands"])},
    _diag_verify, max_steps=10, description="Run a fixed bundle of read-only commands and confirm each exited 0."))
