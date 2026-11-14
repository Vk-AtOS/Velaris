"""ESIGN: signing requests with a ceremony, evidence per signer, a hash-chain seal and a verifier.

Read velaris/agentkit/onboarding_esign.py first: it says what the "signature" is (evidence of click-accept, NOT an
IT Act s.3A signature, needs a lawyer) and how a real PDF signature (pyHanko, Aadhaar eSign) would plug in.

The rule that matters most: NOTHING IS SIGNED WITHOUT THE SIGNER'S OWN TOKEN. At send time each signer gets a random
token by e-mail (through the injected MessageSender, or into an owner-only outbox file when none is configured). The
token is never returned by any method, never stored (only its SHA-256), and an administrator who creates, sends,
voids or seals a request has no way to read it. The signing methods take the token and the signer's e-mail and
ignore the current Caller entirely, so being an administrator gives no power to sign for anyone.

Ceremony per signer: sent -> viewed -> consented -> signed (or declined). Optional one-time code between viewed and
consented. A request is sealed when every signer has signed. Requests expire; reminders rotate the token (the old
link dies). All times come from an injectable clock.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import base64
import functools
import hmac
import logging
import re
import secrets
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from velaris.agentkit import onboarding_dsr as dsr
from velaris.agentkit import onboarding_esign as es
from velaris.agentkit.onboarding_common import (dsr_gate, HR_ADMINS, Refused, Store, clean_text, iso, keyed_hash, new_id, parse_iso, reader,
                                                sha256_hex, utcnow, writer)
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import append_line
from velaris.core.access import Caller, current_caller, deployment_org
from velaris.intel import trace
from velaris.intel.paths import read_private, write_private

logger = logging.getLogger("ESIGN")
_AGENT = "ESIGN"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_DOC = 5 * 1024 * 1024
MAX_FAILS, MAX_OTP_TRIES, OTP_MINUTES, MAX_REMINDERS = 10, 5, 10, 3
_PENDING = ("sent", "viewed", "consented")


def _noticed(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Every result carries LEGAL_NOTICE."""
    @functools.wraps(fn)
    def wrapper(*a: Any, **k: Any) -> Any:
        out = fn(*a, **k)
        if isinstance(out, dict):
            out["legal_notice"] = es.LEGAL_NOTICE
        return out
    return wrapper


class Esign:
    """Signing requests: create, send, ceremony (token-authenticated), seal, verify. See the module docstring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.store = Store(_AGENT)

    def health_check(self) -> Dict[str, Any]:
        return health(_AGENT, sender=bool(self.config.get("sender")), platform_signature=bool(self.config.get("pdf_signer")),
                      legal_notice=es.LEGAL_NOTICE)

    def _now(self):
        return utcnow(self.config)

    # ---- files ----------------------------------------------------------------------------
    def _doc_path(self, sha: str) -> Path:
        return self.store.files_dir("documents") / f"{sha}.bin"

    def _sealed_path(self, req_id: str, signed: bool = False) -> Path:
        return self.store.files_dir("sealed") / f"{req_id}{'.signed' if signed else ''}.pdf"

    def _read(self, path: Path) -> Optional[bytes]:
        try:
            return read_private(path)
        except FileNotFoundError:
            return None

    # ---- delivery ---------------------------------------------------------------------------
    def _deliver(self, kind: str, to: str, subject: str, body: str, req_id: str, signer_id: str) -> str:
        """"sent" when the injected sender accepted it, else the message is queued in the owner-only outbox file
        (for an operator's mail relay) and the answer is "queued_in_outbox" (never "sent")."""
        sender = self.config.get("sender")
        if sender is not None:
            try:
                if sender.send(to, subject, body) is True:
                    return "sent"
            except Exception as e:      # third-party transport: a failure must not lose the message
                logger.warning("sender failed for %s %s: %s", kind, req_id, e)
        append_line(self.store.files_dir("outbox") / "outbox.jsonl",
                    {"kind": kind, "to": to, "subject": subject, "body": body, "request": req_id, "signer": signer_id,
                     "at": iso(self._now())})
        return "queued_in_outbox"

    def _invite_body(self, req: Dict[str, Any], signer: Dict[str, Any], token: str) -> str:
        base = self.config.get("signing_url_base", "")
        return (f"Hello {signer['name']},\n\nPlease review and accept: {req['title']}.\n"
                f"Document SHA-256: {req['document_sha256']}\n"
                f"Your personal signing code (do not forward it; anyone who has it can act as you): {token}\n"
                f"{('Open: ' + base + '?code=' + token) if base else ''}\n"
                f"The request expires {req['expires_at']}.\n")

    # ---- creation (HR) -------------------------------------------------------------------------
    @_noticed
    def create_request(self, title: str, document_base64: str, signers: List[Dict[str, Any]], valid_days: int = 14,
                       document_ref: str = "") -> Dict[str, Any]:
        """Register a document for signing (HR administrators). signers: [{"name","email","role"?,"otp_required"?,"phone"?}]."""
        who, refusal = writer(_AGENT, "create_request", {"title": str(title)[:60]}, roles=HR_ADMINS)
        if refusal:
            return refusal
        try:
            title = clean_text(title, "title", max_len=150)
            raw = base64.b64decode(document_base64, validate=True)
            if not raw or len(raw) > MAX_DOC:
                raise ValueError(f"the document must be 1 byte to {MAX_DOC} bytes")
            if not 1 <= int(valid_days) <= 90:
                raise ValueError("valid_days must be 1 to 90")
            sg = self._signers(signers)
        except (ValueError, TypeError) as e:
            return invalid(str(e))
        sha = sha256_hex(raw)
        write_private(self._doc_path(sha), raw)
        req = {"id": new_id("sig"), "org": who.org, "title": title, "document_ref": str(document_ref)[:80] or None,
               "document_sha256": sha, "document_size": len(raw), "status": "draft", "created_by": who.id,
               "created_at": iso(self._now()), "valid_days": int(valid_days), "expires_at": None, "signers": sg,
               "signed_order": [], "seal": None, "platform_signature": None}
        self.store.put("requests", req)
        trace.append(_AGENT, "request.created", {"request": req["id"], "org": who.org, "by": who.id, "sha256": sha})
        return ok(request=self._view(req))

    @staticmethod
    def _signers(signers: Any) -> List[Dict[str, Any]]:
        if not isinstance(signers, list) or not 1 <= len(signers) <= 10:
            raise ValueError("signers must be a list of 1 to 10 people")
        out, seen = [], set()
        for n, s in enumerate(signers, start=1):
            if not isinstance(s, dict):
                raise ValueError("each signer must be an object")
            email = clean_text(s.get("email"), "signer email", max_len=160).lower()
            if not _EMAIL.match(email) or email in seen:
                raise ValueError(f"signer {n}: email is invalid or repeated")
            seen.add(email)
            out.append({"id": f"s{n}", "name": clean_text(s.get("name"), "signer name", max_len=120), "email": email,
                        "role": clean_text(s.get("role") or "signer", "signer role", max_len=60),
                        "phone": clean_text(s.get("phone"), "phone", max_len=20, required=False) or None,
                        "otp_required": bool(s.get("otp_required", False)), "state": "created", "token_sha256": None,
                        "failed": 0, "reminders": 0, "last_notified_at": None, "delivery": None, "otp": None,
                        "viewed_at": None, "consent_at": None, "signed_at": None, "declined": None, "evidence": None})
        return out

    @_noticed
    def send_request(self, request_id: str) -> Dict[str, Any]:
        """Issue each signer's personal token and deliver it. Tokens are not returned to you; they go to the signers."""
        who, refusal = writer(_AGENT, "send_request", {"request": str(request_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        now = self._now()
        tokens: Dict[str, str] = {}

        def _do(r: Dict[str, Any]) -> Dict[str, Any]:
            if r["status"] != "draft":
                raise Refused(fail("conflict", f"request is {r['status']}"))
            r["status"], r["expires_at"] = "sent", iso(now + timedelta(days=r["valid_days"]))
            for s in r["signers"]:
                tokens[s["id"]] = secrets.token_urlsafe(32)
                s.update(state="sent", token_sha256=sha256_hex(tokens[s["id"]].encode()), last_notified_at=iso(now))
            return ok()

        out = self.store.update("requests", request_id, who.org, _do)
        if out.get("status") != "ok":
            return out
        req = self.store.get("requests", request_id, who.org)
        delivery = {}
        for s in req["signers"]:
            delivery[s["id"]] = self._deliver("invite", s["email"], f"Please review and accept: {req['title']}",
                                              self._invite_body(req, s, tokens[s["id"]]), req["id"], s["id"])
        self.store.update("requests", request_id, who.org, lambda r: [x.update(delivery=delivery[x["id"]]) for x in r["signers"]])
        trace.append(_AGENT, "request.sent", {"request": request_id, "org": who.org, "by": who.id})
        return ok(request=self._view(self.store.get("requests", request_id, who.org)), delivery=delivery,
                  note="tokens were delivered to the signers (or queued in the outbox); they are not returned here")

    @_noticed
    def send_reminders(self) -> Dict[str, Any]:
        """Re-send to signers who have not finished (HR administrators). Each reminder issues a NEW token; the old link dies."""
        who, refusal = writer(_AGENT, "send_reminders", {}, roles=HR_ADMINS)
        if refusal:
            return refusal
        now, hours = self._now(), int(self.config.get("reminder_after_hours", 48))
        sent = []
        for r in self.store.all("requests", who.org):
            if r["status"] != "sent" or now > parse_iso(r["expires_at"]):
                continue
            for s in r["signers"]:
                if s["state"] not in _PENDING or s["reminders"] >= MAX_REMINDERS or \
                        now - parse_iso(s["last_notified_at"]) < timedelta(hours=hours):
                    continue
                token = secrets.token_urlsafe(32)
                self.store.update("requests", r["id"], who.org, lambda x, sid=s["id"], t=token: [
                    y.update(token_sha256=sha256_hex(t.encode()), last_notified_at=iso(now), reminders=y["reminders"] + 1)
                    for y in x["signers"] if y["id"] == sid])
                d = self._deliver("reminder", s["email"], f"Reminder: {r['title']}", self._invite_body(r, s, token), r["id"], s["id"])
                sent.append({"request": r["id"], "signer": s["id"], "delivery": d})
        return ok(reminders=sent)

    @_noticed
    def process_due(self) -> Dict[str, Any]:
        """Expire requests whose time has passed (HR administrators). Their tokens stop working."""
        who, refusal = writer(_AGENT, "process_due", {}, roles=HR_ADMINS)
        if refusal:
            return refusal
        now, expired = self._now(), []
        for r in self.store.all("requests", who.org):
            if r["status"] == "sent" and now > parse_iso(r["expires_at"]):
                self.store.update("requests", r["id"], who.org, self._close("expired", "expired by time"))
                expired.append(r["id"])
        return ok(expired=expired)

    @staticmethod
    def _close(status: str, why: str) -> Callable[[Dict[str, Any]], Any]:
        def _do(r: Dict[str, Any]) -> Dict[str, Any]:
            r["status"], r["closed_reason"] = status, why
            for s in r["signers"]:
                s["token_sha256"] = None
                if s["state"] in _PENDING or s["state"] == "created":
                    s["state"] = status
            return ok()
        return _do

    @_noticed
    def void_request(self, request_id: str, reason: str) -> Dict[str, Any]:
        """Cancel a request that is not yet sealed (its drafter or an HR administrator). Sealed documents are never voided."""
        rec = self._peek(request_id)
        who, refusal = writer(_AGENT, "void_request", {"request": str(request_id)}, roles=HR_ADMINS,
                              also=rec["created_by"] if rec else None)
        if refusal:
            return refusal
        if rec is None or rec["org"] != who.org:
            return fail("not_found", "no such request")
        if rec["status"] not in ("draft", "sent", "completed"):
            return fail("conflict", f"request is {rec['status']}; a sealed or closed request is not voided (supersede it with a new one)")
        out = self.store.update("requests", request_id, who.org, self._close("voided", str(reason)[:300]))
        trace.append(_AGENT, "request.voided", {"request": request_id, "org": who.org, "by": who.id})
        return out

    def _peek(self, request_id: str) -> Optional[Dict[str, Any]]:
        """The request as seen by the current caller's organisation (used to learn its drafter before the role check)."""
        who = current_caller()
        return self.store.get("requests", request_id, who.org) if who is not None else None

    # ---- the signer's ceremony (token-authenticated; the Caller plays no part) ----------------
    def _by_token(self, token: Any) -> Optional[Tuple[str, str, str]]:
        """(request id, signer id, org) for a token, or None. Looks the token up by its hash across this deployment's requests."""
        if not isinstance(token, str) or not 20 <= len(token) <= 100:
            return None
        sha = sha256_hex(token.encode())
        dep = deployment_org()
        for r in self.store.load().get("records", {}).get("requests", {}).values():
            if dep is not None and r.get("org") != dep:
                continue
            for s in r["signers"]:
                if s["token_sha256"] and hmac.compare_digest(s["token_sha256"], sha):
                    return r["id"], s["id"], r["org"]
        return None

    def _ceremony(self, token: Any, email: Any, ip: Any, user_agent: Any, step: Callable[..., Any],
                  need: Tuple[str, ...]) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
        """Run one ceremony step for the holder of `token`. Returns (result, (request id, org) when a request was found)."""
        found = self._by_token(token)
        if found is None:
            return fail("invalid_token", "this signing code is not valid (it may have expired or been replaced)"), None
        req_id, sid, org = found
        try:
            ctx = {"ip": clean_text(ip, "ip", max_len=64), "ua": clean_text(user_agent, "user_agent", max_len=300),
                   "now": self._now()}
        except ValueError as e:
            return invalid(str(e)), None

        def _do(r: Dict[str, Any]) -> Dict[str, Any]:
            s = next(x for x in r["signers"] if x["id"] == sid)
            if r["status"] != "sent" or ctx["now"] > parse_iso(r["expires_at"]):
                raise Refused(fail("not_open", f"the request is {r['status']}" if r["status"] != "sent" else "the request has expired"))
            if s["failed"] >= MAX_FAILS:
                raise Refused(fail("locked", "too many wrong attempts; ask for a new signing code"))
            if not isinstance(email, str) or not hmac.compare_digest(email.strip().lower(), s["email"]):
                s["failed"] += 1                       # returned (not raised) so the counter is saved
                self._trace_step(req_id, sid, org, "identity_mismatch", s["state"], must=False)
                return fail("identity_mismatch", "the e-mail does not belong to this signing code")
            if s["state"] not in need:
                raise Refused(fail("out_of_order", f"you are at step '{s['state']}'; this step needs {' or '.join(need)}"))
            out = step(r, s, ctx)
            self._trace_step(req_id, sid, org, out.get("status", "?"), s["state"])     # before the change is saved: no trace, no step
            return out

        return self.store.update("requests", req_id, org, _do), (req_id, org)

    @staticmethod
    def _trace_step(req_id: str, signer_id: str, org: str, result: str, state: str, must: bool = True) -> None:
        """One ledger entry per ceremony step (opaque ids only: no name, e-mail, IP or token)."""
        try:
            trace.append(_AGENT, "signer.step", {"request": req_id, "signer": signer_id, "org": org, "result": result, "state": state})
        except (OSError, ValueError, TypeError) as e:
            logger.warning("signing step of %s not traced: %s", req_id, type(e).__name__)
            if must:
                raise Refused(fail("audit_failed", "the step could not be recorded, so it was not made"))

    def _step(self, token: Any, email: Any, ip: Any, ua: Any, step: Callable[..., Any], need: Tuple[str, ...]) -> Dict[str, Any]:
        return self._ceremony(token, email, ip, ua, step, need)[0]

    @_noticed
    def open_signing(self, token: str, email: str, ip: str, user_agent: str) -> Dict[str, Any]:
        """The signer opens the request: records "viewed" and shows the document hash and the consent text."""
        def step(r: Dict[str, Any], s: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
            if s["state"] == "sent":
                s["state"], s["viewed_at"] = "viewed", iso(ctx["now"])
            return ok(title=r["title"], signer=s["name"], document_sha256=r["document_sha256"], otp_required=s["otp_required"],
                      consent_text=es.CONSENT_TEXTS[es.CURRENT_CONSENT], consent_text_version=es.CURRENT_CONSENT,
                      intent_statement=es.intent_statement(es.CURRENT_INTENT, s["name"], r["document_sha256"]),
                      expires_at=r["expires_at"])
        return self._step(token, email, ip, user_agent, step, ("sent", "viewed"))

    @_noticed
    def request_otp(self, token: str, email: str, ip: str, user_agent: str) -> Dict[str, Any]:
        """Draft a one-time code to the signer's phone (or e-mail). Delivery is through the injected sender or the outbox."""
        box: Dict[str, str] = {}

        def step(r: Dict[str, Any], s: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
            if not s["otp_required"]:
                raise Refused(invalid("this signer does not use a one-time code"))
            if s["otp"] and s["otp"]["issued"] >= 5:
                raise Refused(fail("locked", "too many codes requested"))
            code, salt = f"{secrets.randbelow(10 ** 6):06d}", secrets.token_hex(8)
            s["otp"] = {"salt": salt, "hash": sha256_hex((salt + code).encode()),
                        "expires_at": iso(ctx["now"] + timedelta(minutes=OTP_MINUTES)), "tries": 0, "verified": False,
                        "issued": (s["otp"]["issued"] if s["otp"] else 0) + 1}
            box.update(code=code, to=s["phone"] or s["email"], rid=r["id"], sid=s["id"])
            return ok()

        out = self._step(token, email, ip, user_agent, step, ("viewed",))
        if out.get("status") != "ok":
            return out
        d = self._deliver("otp", box["to"], "Your one-time code", f"Your one-time code is {box['code']}. It expires in {OTP_MINUTES} minutes.",
                          box["rid"], box["sid"])
        return ok(delivery=d, expires_in_minutes=OTP_MINUTES)

    @_noticed
    def verify_otp(self, token: str, email: str, code: str, ip: str, user_agent: str) -> Dict[str, Any]:
        """Check the one-time code. Five wrong tries lock the code."""
        def step(r: Dict[str, Any], s: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
            o = s["otp"]
            if not o or o["verified"] or o["tries"] >= MAX_OTP_TRIES or ctx["now"] > parse_iso(o["expires_at"]):
                return fail("otp_unavailable", "no usable code: request a new one")
            o["tries"] += 1
            if not isinstance(code, str) or not hmac.compare_digest(sha256_hex((o["salt"] + code.strip()).encode()), o["hash"]):
                return fail("otp_wrong", "wrong code")
            o["verified"] = True
            return ok()
        return self._step(token, email, ip, user_agent, step, ("viewed",))

    @_noticed
    def give_consent(self, token: str, email: str, ip: str, user_agent: str, consent_text_version: str) -> Dict[str, Any]:
        """The signer accepts the consent text (by its version). Needs the one-time code first when the signer uses one."""
        def step(r: Dict[str, Any], s: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
            if consent_text_version != es.CURRENT_CONSENT:
                raise Refused(invalid(f"the current consent text is version {es.CURRENT_CONSENT}"))
            if s["otp_required"] and not (s["otp"] and s["otp"]["verified"]):
                raise Refused(fail("otp_required", "verify the one-time code first"))
            s["state"], s["consent_at"], s["consent_version"] = "consented", iso(ctx["now"]), consent_text_version
            return ok()
        return self._step(token, email, ip, user_agent, step, ("viewed",))

    @_noticed
    def sign_document(self, token: str, email: str, typed_name: str, ip: str, user_agent: str) -> Dict[str, Any]:
        """The signer states their intent by typing their name. Builds the evidence record; the last signer triggers the seal."""
        def step(r: Dict[str, Any], s: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(typed_name, str) or es.norm_name(typed_name) != es.norm_name(s["name"]):
                raise Refused(fail("name_mismatch", "type your name exactly as it appears on the request"))
            ver, name = es.CURRENT_INTENT, typed_name.strip()
            s["state"], s["signed_at"] = "signed", iso(ctx["now"])
            s["evidence"] = {
                "signer_id": s["id"], "name": s["name"], "email": s["email"], "role": s["role"],
                "document_sha256": r["document_sha256"], "consent_text_version": s["consent_version"],
                "consent_text_sha256": sha256_hex(es.CONSENT_TEXTS[s["consent_version"]].encode()),
                "viewed_at": s["viewed_at"], "consent_at": s["consent_at"], "signed_at": s["signed_at"],
                "auth_methods": ["email_token"] + (["one_time_code"] if s["otp_required"] else []),
                "ip_hash": keyed_hash("esign_ip", ctx["ip"]), "user_agent_hash": keyed_hash("esign_ua", ctx["ua"]),
                "intent_version": ver, "typed_name": name, "intent_statement": es.intent_statement(ver, name, r["document_sha256"])}
            r["signed_order"].append(s["id"])
            s["token_sha256"] = None                     # a token is good for one signature
            if all(x["state"] == "signed" for x in r["signers"]):
                r["status"] = "completed"
            return ok(signer_state="signed", request_status=r["status"])

        out, where = self._ceremony(token, email, ip, user_agent, step, ("consented",))
        if out.get("status") == "ok" and out.get("request_status") == "completed" and where:
            out["seal"] = self._seal(*where)
        return out

    @_noticed
    def decline_signing(self, token: str, email: str, reason: str, ip: str, user_agent: str) -> Dict[str, Any]:
        """The signer declines; the whole request is closed as declined and no other token works."""
        def step(r: Dict[str, Any], s: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
            self._close("declined", f"declined by {s['id']}")(r)
            s["state"] = "declined"
            s["declined"] = {"at": iso(ctx["now"]), "reason": str(reason)[:300], "ip_hash": keyed_hash("esign_ip", ctx["ip"])}
            return ok(request_status="declined")
        return self._step(token, email, ip, user_agent, step, ("sent", "viewed", "consented"))

    # ---- sealing and verification ------------------------------------------------------------------
    def _seal(self, req_id: str, org: str) -> Dict[str, Any]:
        """Seal a completed request: evidence page, hash chain, trace anchor, optional platform signature."""
        req = self.store.get("requests", req_id, org)
        if req is None or req["status"] != "completed":
            return fail("conflict", "only a completed request can be sealed")
        original = self._read(self._doc_path(req["document_sha256"]))
        if original is None:
            return fail("integrity", "the stored document is missing; cannot seal")
        evidence = [next(s["evidence"] for s in req["signers"] if s["id"] == sid) for sid in req["signed_order"]]
        now = iso(self._now())
        res = es.seal(original, req["title"], evidence, req["created_at"], now)
        sig = es.platform_signature(res["sealed_pdf"], res["seal_hash"], self.config.get("pdf_signer"))
        try:
            write_private(self._sealed_path(req_id), res["sealed_pdf"])
            if sig.get("signed_pdf"):
                write_private(self._sealed_path(req_id, True), sig["signed_pdf"])
            trace.append("esign", "esign.sealed", {"request": req_id, "org": org, "seal_hash": res["seal_hash"],
                                                   "document_sha256": res["document_sha256"], "sealed_sha256": res["sealed_sha256"]})
        except (OSError, ValueError) as e:
            logger.warning("sealing %s failed: %s", req_id, e)
            return fail("seal_failed", f"could not write the sealed file or the trace entry ({type(e).__name__}); the request stays completed")
        seal_rec = {k: v for k, v in res.items() if k != "sealed_pdf"}
        public_sig = {k: v for k, v in sig.items() if k != "signed_pdf"}

        def _do(r: Dict[str, Any]) -> Dict[str, Any]:
            r["status"], r["seal"], r["platform_signature"] = "sealed", seal_rec, public_sig
            return ok()

        self.store.update("requests", req_id, org, _do)
        return ok(seal_hash=res["seal_hash"], sealed_sha256=res["sealed_sha256"], evidence_page=res["evidence_page"],
                  platform_signature=public_sig)

    @_noticed
    def seal_request(self, request_id: str) -> Dict[str, Any]:
        """Retry sealing a request that completed but could not be sealed (HR administrators)."""
        who, refusal = writer(_AGENT, "seal_request", {"request": str(request_id)}, roles=HR_ADMINS)
        if refusal:
            return refusal
        return self._seal(request_id, who.org)

    def _anchored(self, req_id: str, seal_hash: str) -> bool:
        return any(e["action"] == "esign.sealed" and e["payload"].get("request") == req_id and e["payload"].get("seal_hash") == seal_hash
                   for e in trace.entries())

    @_noticed
    def verify(self, request_id: str) -> Dict[str, Any]:
        """Recompute the document hash, every evidence hash, the seal chain, the sealed PDF and the trace anchor."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        req = self.store.get("requests", request_id, who.org)
        if not self._visible(who, req):          # same rule as get_request: drafter or HR, else "not found"
            return fail("not_found", "no such request")
        if req["status"] != "sealed" or not req["seal"]:
            return fail("not_sealed", f"request is {req['status']}; only a sealed request can be verified")
        evidence = [next(s["evidence"] for s in req["signers"] if s["id"] == sid) for sid in req["signed_order"]]
        checks = es.verify_seal(self._read(self._doc_path(req["document_sha256"])), req["document_sha256"], evidence, req["seal"],
                                self._read(self._sealed_path(request_id)), self._anchored(request_id, req["seal"]["seal_hash"]))
        return ok(valid=all(c["ok"] for c in checks), checks=checks, platform_signature=req["platform_signature"],
                  signers=[{"name": e["name"], "email": e["email"], "signed_at": e["signed_at"], "auth_methods": e["auth_methods"]} for e in evidence])

    # ---- reads ---------------------------------------------------------------------------------------
    def request_info(self, request_id: str, org: str) -> Optional[Dict[str, Any]]:
        """Status and document_ref of a request of `org` for another agent (OFFER_LETTERS); not an HTTP method. No names, no tokens."""
        req = self.store.get("requests", request_id, org)
        return {"status": req["status"], "document_ref": req["document_ref"]} if req else None

    # ---- data-subject support (called by EMPLOYEE_RECORDS; not an HTTP method) ----------------------
    def dsr_export(self, org: str, subject_id: str, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dsr_gate("ESIGN", org, subject_id, erase=False)
        return {"esign_requests": dsr.esign_export(self.store, org, links or {})}

    def dsr_erase(self, org: str, subject_id: str, on: Optional[date] = None, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Anonymise the subject's signer data on requests that were never sealed; sealed evidence is held as the registry says."""
        dsr_gate("ESIGN", org, subject_id, erase=True)
        return dsr.esign_erase(self.store, org, links or {}, on or self._now().date(), self._now())

    def _visible(self, who: Caller, req: Optional[Dict[str, Any]]) -> bool:
        return req is not None and bool(who.roles & HR_ADMINS or who.id == req["created_by"])

    @staticmethod
    def _view(r: Dict[str, Any]) -> Dict[str, Any]:
        """The request without tokens, token hashes or one-time-code material."""
        signers = [{k: s[k] for k in ("id", "name", "email", "role", "state", "otp_required", "delivery", "viewed_at", "consent_at",
                                      "signed_at", "reminders")} for s in r["signers"]]
        return {"id": r["id"], "org": r["org"], "title": r["title"], "document_ref": r["document_ref"], "status": r["status"],
                "document_sha256": r["document_sha256"], "created_by": r["created_by"], "created_at": r["created_at"],
                "expires_at": r["expires_at"], "signers": signers,
                "seal_hash": (r["seal"] or {}).get("seal_hash"), "platform_signature": r["platform_signature"]}

    @_noticed
    def get_request(self, request_id: str) -> Dict[str, Any]:
        """Status of a request (its drafter and HR administrators). No tokens are ever included."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        req = self.store.get("requests", request_id, who.org)
        return ok(request=self._view(req)) if self._visible(who, req) else fail("not_found", "no such request")

    @_noticed
    def list_requests(self, status: str = "") -> Dict[str, Any]:
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        return ok(requests=[self._view(r) for r in self.store.all("requests", who.org)
                            if self._visible(who, r) and (not status or r["status"] == status)])

    @_noticed
    def get_sealed_document(self, request_id: str) -> Dict[str, Any]:
        """The sealed PDF (base64) of a sealed request, and the platform-signed one when a signer was configured."""
        who, refusal = reader(_AGENT)
        if refusal:
            return refusal
        req = self.store.get("requests", request_id, who.org)
        if not self._visible(who, req) or req["status"] != "sealed":
            return fail("not_found", "no sealed document for this request")
        data = self._read(self._sealed_path(request_id))
        if data is None:
            return fail("integrity", "the sealed file is missing")
        signed = self._read(self._sealed_path(request_id, True))
        return ok(sealed_pdf_base64=base64.b64encode(data).decode(), sealed_sha256=sha256_hex(data),
                  platform_signed_pdf_base64=base64.b64encode(signed).decode() if signed else None)
