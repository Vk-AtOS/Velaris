"""The public (candidate-facing) side as plain functions, for a gateway to expose. None of this is in the
identity-authenticated API: a candidate is not a Caller. What a candidate holds is a form id (public), a solved
proof-of-work, and later a token that is hashed at rest and expires.

Nothing here decides anything about a candidate. A submission is stored as `pending` with its own consent record;
a recruiter must accept it (an approved act) before it becomes a candidate in the ATS. Unaccepted submissions
expire (SUBMISSION_TTL_DAYS) and are swept.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from velaris.agentkit import hiring_forms as hf
from velaris.agentkit.hiring_common import DAY, HiringError, application_known, audit, hid, iso, new_id, now
from velaris.agentkit.results import fail, ok
from velaris.intel.paths import agent_dir, private_dir, read_private, write_private

MAX_PER_HOUR = 300


def _form(form_id: Any) -> Dict[str, Any]:
    f = hf._st().load()["forms"].get(str(form_id))
    if not f or f["status"] != "published":
        raise HiringError("not_found", "no such form")
    return f


def public_form(form_id: str) -> Dict[str, Any]:
    try:
        f = _form(form_id)
    except HiringError as e:
        return fail(e.status, e.reason)
    return ok(form_id=f["id"], title=f["title"], fields=f["fields"], consent_text=f["consent_text"], consent_version=f["consent_version"],
              retention_days=f["retention_days"], talent_pool_offer=f["talent_pool_offer"], file_rules=f["file_rules"],
              note="Consent must be given explicitly (consent_given: true). Talent-pool consent is separate and optional.")


def public_challenge(form_id: str) -> Dict[str, Any]:
    try:
        f = _form(form_id)
    except HiringError as e:
        return fail(e.status, e.reason)
    return ok(challenge=hf.new_challenge(f["id"]))


def public_submit(form_id: str, answers: Dict[str, Any], pow_solution: Dict[str, Any], file_name: Optional[str] = None,
                  file_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    try:
        f = _form(form_id)
        org, at = f["org"], now()
        if (why := hf.check_solution(pow_solution, f["id"])):
            raise HiringError("challenge_failed", why)
        hour = iso(at)[:13]

        def count(d: Dict[str, Any]) -> bool:
            d["hourly"] = {k: v for k, v in d["hourly"].items() if k.startswith(hour[:10])}
            key = f"{f['id']}|{hour}"
            d["hourly"][key] = d["hourly"].get(key, 0) + 1
            return d["hourly"][key] <= MAX_PER_HOUR
        if not hf._st().update(count):
            raise HiringError("rate_limited", "too many applications this hour; try again later")
        clean, errors = hf.validate_answers(f, answers)
        has_file_field = any(x["type"] == "file" for x in f["fields"])
        required_file = any(x["type"] == "file" and x["required"] for x in f["fields"])
        if errors:
            return fail("invalid_input", "some answers need fixing", errors=errors)
        file_info = None
        if file_bytes is not None:
            if not has_file_field:
                raise HiringError("invalid_input", "this form takes no file")
            file_info = hf.sniff_upload(file_name, file_bytes, f["file_rules"]["allowed"], f["file_rules"]["max_bytes"])
        elif required_file:
            raise HiringError("invalid_input", "a file is required")
        sid = new_id("sub")
        if file_info:
            path = private_dir(agent_dir(hf.AGENT) / "uploads") / f"{sid}.bin"
            write_private(path, bytes(file_bytes))
            file_info["path"] = str(path)
        consent = {"purpose": f"recruitment: {f['title']}"[:300], "notice_version": f["consent_version"],
                   "retention_until": iso(at + f["retention_days"] * DAY)[:10], "channel": "web_form",
                   "talent_pool": clean.pop("talent_pool")}
        rec = {"id": sid, "org": org, "form_id": f["id"], "requisition_id": f["requisition_id"], "answers": clean, "consent": consent,
               "file": file_info, "received_at": at, "expires_at": at + hf.SUBMISSION_TTL_DAYS * DAY, "status": "pending", "candidate_id": None}
        audit(hf.AGENT, "submission.received", org, None, submission=hid(org, sid), form=hid(org, f["id"]),
              consent=hf.digest(consent), file_sha256=file_info["sha256"] if file_info else None)
        hf._st().update(lambda d: d["submissions"].__setitem__(sid, rec))
        return ok(reference=sid, message="Thank you. Your application was received.")
    except HiringError as e:
        return fail(e.status, e.reason)


def public_status(token: str) -> Dict[str, Any]:
    t = hf.lookup_token(token, "status")
    a = application_known(t["org"], t["application_id"]) if t else None
    if not a:
        return fail("not_found", "this link is not valid or has expired")
    return ok(progress=hf.CANDIDATE_STAGE_TEXT.get(a["stage"], "In progress"), updated=iso(a["stage_since"])[:10])


def public_withdraw(token: str) -> Dict[str, Any]:
    """Records that the candidate withdraws consent. A recruiter processes it (ATS_CORE.withdraw_consent); no login is needed here."""
    t = hf.lookup_token(token, "withdraw")
    if not t:
        return fail("not_found", "this link is not valid or has expired")
    a = application_known(t["org"], t["application_id"])
    if not a:
        return fail("not_found", "this link is not valid or has expired")

    def go(d: Dict[str, Any]) -> None:
        d["withdrawals"][t["application_id"]] = {"org": t["org"], "application_id": t["application_id"], "requested_at": now(), "done": False}
    hf._st().update(go)
    audit(hf.AGENT, "withdrawal.requested", t["org"], None, application=hid(t["org"], t["application_id"]))
    return ok(message="Your request was received. Your data will be erased; we will confirm by e-mail.")


def file_b64(path: str) -> str:
    return base64.b64encode(read_private(path)).decode()
