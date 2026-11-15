"""Candidate-facing building blocks that need no login: intake forms as data, a proof-of-work challenge, upload
checks, and hashed expiring tokens. The functions are pure or touch only SCREENING_FORMS' own store; a gateway
exposes them (see PUBLIC_ROUTES). Candidates are never Callers: nothing here is in the identity-authenticated API.

Proof of work (ALTCHA-style idea, original code): the server hands out {salt, bits, expires, signature}; the client
finds n so that SHA-256("salt:n") starts with `bits` zero bits and sends n back. The signature is an HMAC over the
parameters with a server key, so nothing is stored per challenge until it is solved; a solved salt is remembered
until it expires so it cannot be replayed. It slows bulk spam; it is not a bot-proof captcha.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import re
import secrets
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit.hiring_common import DAY, bad, digest, now, sha, store
from velaris.agentkit.recstore import RecordStore
from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir, load_or_create_key

AGENT = "SCREENING_FORMS"
FIELD_TYPES = ("text", "longtext", "email", "phone", "number", "choice", "url", "checkbox", "file")
MAX_FIELDS = 40
MAX_UPLOAD = 5_000_000
POW_BITS, POW_TTL = 18, 600
TOKEN_TTL_DAYS_MAX = 120
SUBMISSION_TTL_DAYS = 30
PURPOSES = ("status", "withdraw")
CANDIDATE_STAGE_TEXT = {"applied": "Received", "screening": "Being reviewed", "interview": "Interviews in progress",
                        "assessment": "Assessment stage", "offer": "Final stage", "hired": "Process complete",
                        "rejected": "Process complete", "withdrawn": "Withdrawn"}
PUBLIC_ROUTES = [
    "GET  /careers/forms/{form_id}            -> public_form(form_id): the fields and the consent notice to show",
    "GET  /careers/challenge/{form_id}        -> public_challenge(form_id)",
    "POST /careers/apply/{form_id}            -> public_submit: JSON {answers, pow_solution, file_name?, file_base64?}",
    "GET  /careers/status/{token}             -> public_status(token)",
    "POST /careers/withdraw/{token}           -> public_withdraw(token)   (withdraws consent; needs no login)",
]  # served by velaris.api.public.create_public_app (a separate app and port, never the identity-authenticated API)
_EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}")
_PHONE = re.compile(r"\+?[0-9][0-9 ()-]{7,18}[0-9]")
_NAME = re.compile(r"[a-z][a-z0-9_]{0,39}")


def _tokens() -> RecordStore:
    return RecordStore(AGENT, "tokens", f"hiring:{AGENT}")        # one sealed file per token, keyed by its SHA-256 (KAN-64)


def _move_tokens(d: Dict[str, Any]) -> Dict[str, Any]:
    """Schema 1 -> 2: tokens left the shared 1 MiB document. Idempotent (the copy is overwritten, never duplicated);
    the old entries disappear from the file at its next save."""
    ts = _tokens()
    for h, rec in (d.get("tokens") or {}).items():
        ts.put(h, rec)
    d["tokens"] = {}
    return d


def _st() -> Any:
    return JsonState(AGENT, "forms.json", {"forms": {}, "submissions": {}, "tokens": {}, "pow_used": {}, "withdrawals": {}, "hourly": {}},
                     encrypted=f"hiring:{AGENT}", version=2, migrations={1: _move_tokens})


# ---- form definitions ----------------------------------------------------------------------------
def validate_form_definition(defn: Any) -> Dict[str, Any]:
    if not isinstance(defn, dict):
        raise bad("form must be an object")
    fields = defn.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        raise bad(f"form needs 1 to {MAX_FIELDS} fields")
    names, clean = set(), []
    for f in fields:
        if not isinstance(f, dict) or f.get("type") not in FIELD_TYPES or not _NAME.fullmatch(str(f.get("name", ""))):
            raise bad(f"each field needs a lowercase name and a type from {list(FIELD_TYPES)}")
        if f["name"] in names or f["name"] in ("consent_given", "talent_pool"):
            raise bad(f"field name '{f['name']}' is duplicated or reserved")
        names.add(f["name"])
        row = {"name": f["name"], "type": f["type"], "label": str(f.get("label", f["name"]))[:160], "required": bool(f.get("required", False))}
        if f["type"] in ("text", "longtext", "url"):
            row["max_length"] = int(f.get("max_length", 200 if f["type"] != "longtext" else 4000))
            if not 1 <= row["max_length"] <= 10_000:
                raise bad("max_length must be 1 to 10000")
        if f["type"] == "number":
            row["min"], row["max"] = f.get("min", 0), f.get("max", 1000)
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (row["min"], row["max"])) or row["min"] > row["max"]:
                raise bad("number fields need numeric min <= max")
        if f["type"] == "choice":
            ch = f.get("choices")
            if not isinstance(ch, list) or not 2 <= len(ch) <= 30 or not all(isinstance(c, str) and c for c in ch):
                raise bad("choice fields need 2 to 30 text choices")
            row["choices"] = ch
        clean.append(row)
    notice = defn.get("consent_text")
    if not isinstance(notice, str) or len(notice.strip()) < 40:
        raise bad("consent_text is required: say what data is collected, why, for how long, and how to withdraw")
    days = defn.get("retention_days", 180)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 730:
        raise bad("retention_days must be 1 to 730")
    rules = defn.get("file_rules") or {"max_bytes": MAX_UPLOAD, "allowed": ["pdf", "docx", "txt"]}
    if not 1 <= int(rules.get("max_bytes", 0)) <= MAX_UPLOAD or not set(rules.get("allowed", [])) <= {"pdf", "docx", "txt"}:
        raise bad(f"file_rules: max_bytes up to {MAX_UPLOAD}, allowed from pdf, docx, txt")
    return {"title": str(defn.get("title", "Job application"))[:160], "fields": clean, "consent_text": notice.strip(),
            "consent_version": digest([notice.strip(), days])[:12], "retention_days": days,
            "file_rules": {"max_bytes": int(rules["max_bytes"]), "allowed": list(rules["allowed"])},
            "talent_pool_offer": bool(defn.get("talent_pool_offer", False))}


def validate_answers(form: Dict[str, Any], answers: Any) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """(clean answers, errors by field). Consent must be an explicit True; unknown fields are errors, not ignored."""
    errors: Dict[str, str] = {}
    if not isinstance(answers, dict):
        return {}, {"_": "answers must be an object"}
    known = {f["name"] for f in form["fields"]} | {"consent_given", "talent_pool", "tracking_code"}
    errors.update({k: "unknown field" for k in answers if k not in known})
    if answers.get("consent_given") is not True:
        errors["consent_given"] = "consent must be given explicitly before anything is stored"
    clean: Dict[str, Any] = {}
    for f in form["fields"]:
        v, name = answers.get(f["name"]), f["name"]
        if f["type"] == "file":
            continue                  # the file travels separately; see sniff_upload
        if v in (None, "", False) and f["type"] != "checkbox":
            if f["required"]:
                errors[name] = "required"
            continue
        t = f["type"]
        if t in ("text", "longtext", "url"):
            if not isinstance(v, str) or len(v.strip()) > f["max_length"]:
                errors[name] = f"text of at most {f['max_length']} characters"
            elif t == "url" and not re.fullmatch(r"https?://[^\s]{3,300}", v.strip()):
                errors[name] = "must be an http(s) link"
            else:
                clean[name] = v.strip()
        elif t == "email":
            if not isinstance(v, str) or not _EMAIL.fullmatch(v.strip()):
                errors[name] = "not an e-mail address"
            else:
                clean[name] = v.strip()
        elif t == "phone":
            if not isinstance(v, str) or not _PHONE.fullmatch(v.strip()):
                errors[name] = "not a phone number"
            else:
                clean[name] = v.strip()
        elif t == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not f["min"] <= v <= f["max"]:
                errors[name] = f"a number from {f['min']} to {f['max']}"
            else:
                clean[name] = v
        elif t == "choice":
            if v not in f["choices"]:
                errors[name] = "pick one of the listed choices"
            else:
                clean[name] = v
        elif t == "checkbox":
            clean[name] = v is True
    clean["talent_pool"] = bool(answers.get("talent_pool")) and form["talent_pool_offer"]
    if isinstance(answers.get("tracking_code"), str) and re.fullmatch(r"t[0-9a-f]{8}", answers["tracking_code"]):
        clean["tracking_code"] = answers["tracking_code"]
    return clean, errors


# ---- uploads ------------------------------------------------------------------------------------------
def sniff_upload(filename: Any, data: Any, allowed: List[str], max_bytes: int) -> Dict[str, Any]:
    """The real type of an upload from its bytes (never the name or declared type), or a refusal."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise bad("the file is empty")
    if len(data) > max_bytes:
        raise bad(f"the file is larger than {max_bytes // 1000} KB")
    head = bytes(data[:8])
    if head.startswith(b"%PDF-"):
        kind = "pdf"
    elif head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(bytes(data))) as z:
                names = z.namelist()
                if len(names) > 2000 or sum(i.file_size for i in z.infolist()) > 100_000_000:
                    raise bad("the archive is too large")
        except zipfile.BadZipFile as e:
            raise bad("not a valid document") from e
        kind = "docx" if any(n.startswith("word/") for n in names) and "[Content_Types].xml" in names else "zip"
    elif head[:2] in (b"MZ",) or head[:4] == b"\x7fELF" or head[:2] == b"#!":
        kind = "executable"
    else:
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            kind = "binary"
        else:
            kind = "txt" if "\x00" not in text and "<script" not in text.lower()[:20000] else "binary"
    if kind not in allowed:
        raise bad(f"files of type {kind} are not accepted (allowed: {', '.join(allowed)})")
    ext = str(filename or "").rsplit(".", 1)[-1].lower() if "." in str(filename or "") else ""
    if ext and ext != kind:
        raise bad(f"the file says .{ext} but its contents are {kind}")
    return {"kind": kind, "bytes": len(data), "sha256": hashlib.sha256(bytes(data)).hexdigest()}


# ---- proof of work ----------------------------------------------------------------------------------
def _key() -> bytes:
    return load_or_create_key(agent_dir(AGENT) / "pow.key", 32)


def _sig(salt: str, bits: int, expires: int, scope: str) -> str:
    return hmac.new(_key(), f"{salt}|{bits}|{expires}|{scope}".encode(), hashlib.sha256).hexdigest()


def new_challenge(scope: str, bits: Optional[int] = None, ttl: int = POW_TTL) -> Dict[str, Any]:
    bits = POW_BITS if bits is None else bits
    salt, expires = secrets.token_hex(12), int(now()) + ttl
    return {"algorithm": "sha256-leading-zero-bits", "salt": salt, "bits": bits, "expires": expires, "signature": _sig(salt, bits, expires, scope),
            "how": "find an integer n such that SHA-256(salt + ':' + n) in binary starts with `bits` zero bits; send {salt, bits, expires, signature, n}"}


def leading_zero_bits(h: bytes) -> int:
    n = 0
    for b in h:
        if b == 0:
            n += 8
            continue
        return n + (8 - b.bit_length())
    return n


def solve(challenge: Dict[str, Any], limit: int = 50_000_000) -> int:
    """What the client does (also used by tests and by a kiosk script)."""
    for n in range(limit):
        if leading_zero_bits(hashlib.sha256(f"{challenge['salt']}:{n}".encode()).digest()) >= challenge["bits"]:
            return n
    raise ValueError("no solution within the limit")


def check_solution(sol: Any, scope: str) -> Optional[str]:
    """None when the solution is valid and fresh, else the reason. Marks the salt used (replay)."""
    try:
        salt, bits, expires, sig, n = str(sol["salt"]), int(sol["bits"]), int(sol["expires"]), str(sol["signature"]), int(sol["n"])
    except (KeyError, TypeError, ValueError):
        return "malformed solution"
    if not hmac.compare_digest(sig, _sig(salt, bits, expires, scope)) or bits < POW_BITS:
        return "bad signature"
    if expires < now():
        return "challenge expired"
    if leading_zero_bits(hashlib.sha256(f"{salt}:{n}".encode()).digest()) < bits:
        return "wrong answer"

    def use(d: Dict[str, Any]) -> bool:
        d["pow_used"] = {s: e for s, e in d["pow_used"].items() if e >= now()}
        if salt in d["pow_used"]:
            return False
        d["pow_used"][salt] = expires
        return True
    return None if _st().update(use) else "already used"


# ---- tokens ----------------------------------------------------------------------------------------
def issue_token(org: str, application_id: str, purpose: str, days: int) -> str:
    """A random token returned ONCE; only its SHA-256 is stored. Purpose-bound and expiring."""
    if purpose not in PURPOSES or isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= TOKEN_TTL_DAYS_MAX:
        raise bad(f"purpose must be one of {list(PURPOSES)} and days 1 to {TOKEN_TTL_DAYS_MAX}")
    raw = secrets.token_urlsafe(24)
    _tokens().put(sha(raw), {"org": org, "application_id": application_id, "purpose": purpose,
                             "expires": now() + days * DAY, "created_at": now()})
    return raw


def lookup_token(raw: Any, purpose: str) -> Optional[Dict[str, Any]]:
    """The token record, or None for anything unknown, expired or of another purpose (the same answer for all)."""
    if not isinstance(raw, str) or not 20 <= len(raw) <= 80:
        return None
    _legacy_tokens()
    rec = _tokens().get(sha(raw))
    return rec if rec and rec["purpose"] == purpose and rec["expires"] > now() else None


_migrated_dir = ""


def _legacy_tokens() -> None:
    """Tokens still in an un-migrated forms.json are moved on first use (load() runs the migration hook; the save clears them)."""
    global _migrated_dir
    here = str(_st().path)
    if _migrated_dir != here and _st().path.exists():
        _st().update(lambda d: None)                                # load() ran the 1 -> 2 hook, save() writes version 2
    _migrated_dir = here


def revoke_tokens(org: str, application_ids: List[str]) -> int:
    _legacy_tokens()
    ts = _tokens()
    gone = [h for h, t in ts.scan(lambda t: t["org"] == org and t["application_id"] in application_ids)]
    return sum(ts.delete(h) for h in gone)


# ---- candidate data held here (erasable) -----------------------------------------------------------------
def export_candidate(org: str, candidate_id: str) -> Dict[str, Any]:
    d = _st().load()
    return {"intake_submissions": [s for s in d["submissions"].values() if s["org"] == org and s.get("candidate_id") == candidate_id]}


def purge_candidate(org: str, candidate_id: str) -> int:
    ev = store("ATS_CORE", "evaluation.json", {}).load()
    apps = [a["id"] for a in ev.get("applications", {}).values() if a.get("org") == org and a.get("candidate_id") == candidate_id]

    def go(d: Dict[str, Any]) -> int:
        gone = [k for k, s in d["submissions"].items() if s["org"] == org and s.get("candidate_id") == candidate_id]
        for k in gone:
            del d["submissions"][k]
        return len(gone)
    n = _st().update(go)
    ts = _tokens()
    for h in [h for h, _ in ts.scan(lambda t: t["org"] == org and t["application_id"] in apps)]:
        ts.delete(h)
    return n
