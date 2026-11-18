"""The /mail HTTP API, mounted by velaris.api.app.create_app through mount_mail().

Authentication is the app's own: every route calls `authed(request)` (signed by the gateway, identity
assertion, deployment organisation) and every call is traced by `record`. Identity is only ever the Caller;
no route reads a user id from the body to act as. Errors are {"error": {"code", "message"}} with messages
written in this package, never exception text. Request bodies are limited by the app (64 KiB), so an
attachment sent in a draft is limited to about 45 KB here; see the report for the larger-upload decision.

Routes (all under /mail; {mb} is a mailbox id):
  GET  mailboxes                         POST mailboxes {address, owner_id?, kind?}            (mail_admin)
  GET  mailboxes/{mb}/folders            POST mailboxes/{mb}/folders {name}
  GET  mailboxes/{mb}/messages?folder&label&unread&flagged&q&limit&offset
  GET|PATCH|DELETE mailboxes/{mb}/messages/{id}        POST .../messages/{id}/restore
  GET  mailboxes/{mb}/threads/{id}       GET .../messages/{id}/attachments/{sha256}   (raw bytes)
  POST mailboxes/{mb}/drafts   PUT|DELETE mailboxes/{mb}/drafts/{id}   POST .../drafts/{id}/submit
  GET  mailboxes/{mb}/submissions        GET submissions/{id}    POST submissions/{id}/cancel
  POST submissions/{id}/decide {approve, payload_hash, note}       GET approvals       POST outbox/process (mail_admin)
  GET|POST mailboxes/{mb}/rules   PUT|DELETE mailboxes/{mb}/rules/{id}   POST mailboxes/{mb}/rules/dry-run
  GET|PUT mailboxes/{mb}/settings {signature, vacation}   PUT mailboxes/{mb}/aliases {address}
  GET|PUT|DELETE mailboxes/{mb}/delegates                 PUT mailboxes/{mb}/quota   PUT mailboxes/{mb}/legal-hold
  GET|POST mailboxes/{mb}/accounts   DELETE mailboxes/{mb}/accounts/{id}   POST mailboxes/{mb}/sync
  POST mailboxes/{mb}/assistant/{summarise|action-items|triage|draft-reply}
  GET|POST domains   POST domains/verify {domain}     (mail_admin: prove ownership by DNS TXT before use)
  GET|PUT settings (PUT: mail_admin)   GET settings/dkim   POST retention/run
  GET  mailboxes/{mb}/export    DELETE mailboxes/{mb}?confirm=erase      (data-principal export and erasure)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from velaris.core.access import Caller
from velaris.mail import assistant as assist, connector, dkim, drafts, rules
from velaris.mail.common import MailError, audit
from velaris.mail.inbound import InboundPipeline, dnspython_resolver
from velaris.mail.outbound import Outbound
from velaris.mail.store import MailStore

logger = logging.getLogger("velaris.mail.api")
_ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")


@dataclass
class MailDeps:
    store: MailStore
    outbound: Outbound
    inbound: InboundPipeline
    imap_factory: Callable[[Any], Any]
    secrets: Callable[[str], Optional[str]]
    llm: Any = None


_OVERRIDE: Optional[MailDeps] = None


def configure(deps: Optional[MailDeps]) -> None:
    """Use these dependencies (fakes in tests, a resolver and relay in a deployment) for apps created after this call."""
    global _OVERRIDE
    _OVERRIDE = deps


def default_deps(settings: Any) -> MailDeps:
    store = MailStore()
    outbound = Outbound(store, relay=connector.relay_from_env(), gate=getattr(settings, "gate", None))
    inbound = InboundPipeline(store, dnspython_resolver(), outbound=outbound)
    outbound.local_delivery = inbound.deliver_local
    return MailDeps(store, outbound, inbound, lambda cfg: connector.ImapLibTransport(cfg.imap_host, cfg.imap_port), connector.vault_secret,
                    getattr(settings, "llm", None))


def _err(e: MailError) -> JSONResponse:
    return JSONResponse({"error": {"code": e.code, "message": e.message}}, status_code=e.status)


def _obj(body: Any) -> Dict[str, Any]:
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise MailError("bad_request", "the body must be a JSON object")
    return body


def _flag(v: Optional[str]) -> bool:
    return (v or "").lower() in ("1", "true", "yes")


def _int(v: Optional[str], default: int) -> int:
    try:
        return int(v) if v else default
    except ValueError:
        raise MailError("bad_request", "a number was expected") from None


def mount_mail(app: FastAPI, settings: Any, authed: Callable, record: Callable, in_thread: Callable, deps: Optional[MailDeps] = None) -> MailDeps:
    d = deps or _OVERRIDE or default_deps(settings)
    st, ob = d.store, d.outbound
    ai = assist.Assistant(st, d.llm)

    def route(method: str, path: str, op: str, fn: Callable[[Caller, Any, Request], Any], *, status: int = 200) -> None:
        """Register one route: authenticate, trace, run `fn(caller, body, request)` off the event loop, translate MailError."""
        async def handler(request: Request) -> Response:
            caller, body = await authed(request)
            ids = {k: v for k, v in request.path_params.items() if _ID.match(str(v))}
            for v in request.path_params.values():
                if not _ID.match(str(v)):
                    return _err(MailError("not_found", "not found", 404))
            record(caller, f"mail.{op}", ids)
            try:
                result = await in_thread(lambda: fn(caller, body, request))
            except MailError as e:
                return _err(e)
            except connector.ConnectorError as e:
                return JSONResponse({"error": {"code": e.code, "message": "the connected mail account could not be read"}}, status_code=502)
            if isinstance(result, Response):
                return result
            return JSONResponse(result, status_code=status)
        app.add_api_route("/mail" + path, handler, methods=[method], name=f"mail_{op}_{method.lower()}")

    P = lambda r, k: r.path_params[k]                                            # noqa: E731
    Q = lambda r, k: r.query_params.get(k)                                       # noqa: E731

    # mailboxes and folders
    route("GET", "/mailboxes", "mailboxes", lambda c, b, r: {"mailboxes": st.mailboxes_for(c)})
    route("POST", "/mailboxes", "mailbox.create", lambda c, b, r: st.create_mailbox(c, str(_obj(b).get("address", "")), owner_id=_obj(b).get("owner_id"),
                                                                                     kind=_obj(b).get("kind", "personal")), status=201)
    route("GET", "/mailboxes/{mb}/folders", "folders", lambda c, b, r: {"folders": st.folders(c, P(r, "mb"))})
    route("POST", "/mailboxes/{mb}/folders", "folder.create", lambda c, b, r: st.create_folder(c, P(r, "mb"), str(_obj(b).get("name", ""))), status=201)

    # messages
    route("GET", "/mailboxes/{mb}/messages", "messages", lambda c, b, r: st.list_messages(
        c, P(r, "mb"), folder=Q(r, "folder") or "", label=Q(r, "label") or "", unread=_flag(Q(r, "unread")), flagged=_flag(Q(r, "flagged")),
        q=Q(r, "q") or "", limit=_int(Q(r, "limit"), 50), offset=_int(Q(r, "offset"), 0)))
    route("GET", "/mailboxes/{mb}/messages/{mid}", "message", lambda c, b, r: st.get_message(c, P(r, "mb"), P(r, "mid")))

    def patch(c: Caller, b: Any, r: Request) -> Any:
        b = _obj(b)
        if set(b) - {"seen", "flagged", "answered", "add_labels", "remove_labels", "folder"}:
            raise MailError("bad_request", "unknown field")
        for k in ("add_labels", "remove_labels"):
            if k in b and not (isinstance(b[k], list) and len(b[k]) <= 30):
                raise MailError("bad_request", f"{k} is a list of at most 30 labels")
        for k in ("seen", "flagged", "answered"):
            if k in b and not isinstance(b[k], bool):
                raise MailError("bad_request", f"{k} is true or false")
        if "folder" in b and not isinstance(b["folder"], str):
            raise MailError("bad_request", "folder is a name or id")
        return st.update_message(c, P(r, "mb"), P(r, "mid"), **b)

    route("PATCH", "/mailboxes/{mb}/messages/{mid}", "message.update", patch)
    route("DELETE", "/mailboxes/{mb}/messages/{mid}", "message.delete", lambda c, b, r: st.delete_message(c, P(r, "mb"), P(r, "mid"), permanent=_flag(Q(r, "permanent"))))
    route("POST", "/mailboxes/{mb}/messages/{mid}/restore", "message.restore", lambda c, b, r: st.restore_message(c, P(r, "mb"), P(r, "mid")))
    route("GET", "/mailboxes/{mb}/threads/{tid}", "thread", lambda c, b, r: st.get_thread(c, P(r, "mb"), P(r, "tid")))

    def attachment(c: Caller, b: Any, r: Request) -> Response:
        meta, data = st.attachment(c, P(r, "mb"), P(r, "mid"), P(r, "sha"))
        name = re.sub(r'[^A-Za-z0-9._ -]', "_", meta["name"])[:120] or "attachment"
        return Response(data, media_type="application/octet-stream", headers={
            "Content-Disposition": f'attachment; filename="{name}"', "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox", "X-Declared-Content-Type": meta["content_type"][:100]})

    route("GET", "/mailboxes/{mb}/messages/{mid}/attachments/{sha}", "attachment", attachment)

    # drafts and sending
    route("POST", "/mailboxes/{mb}/drafts", "draft.create", lambda c, b, r: drafts.create_draft(st, c, P(r, "mb"), _obj(b)), status=201)
    route("PUT", "/mailboxes/{mb}/drafts/{did}", "draft.update", lambda c, b, r: drafts.update_draft(st, c, P(r, "mb"), P(r, "did"), _obj(b)))
    route("DELETE", "/mailboxes/{mb}/drafts/{did}", "draft.delete", lambda c, b, r: drafts.delete_draft(st, c, P(r, "mb"), P(r, "did")))

    def submit(c: Caller, b: Any, r: Request) -> Any:
        res = ob.submit(c, P(r, "mb"), P(r, "did"))
        return res

    route("POST", "/mailboxes/{mb}/drafts/{did}/submit", "submit", submit, status=202)

    def listing(c: Caller, b: Any, r: Request) -> Any:
        mb = P(r, "mb")
        ob.process_due()                                                         # opportunistic: due sends go out when anyone looks
        return {"submissions": ob.list_submissions(c, mb, _int(Q(r, "limit"), 50))}

    route("GET", "/mailboxes/{mb}/submissions", "submissions", listing)
    route("GET", "/submissions/{sid}", "submission", lambda c, b, r: ob.get(c, P(r, "sid")))
    route("POST", "/submissions/{sid}/cancel", "submission.cancel", lambda c, b, r: ob.cancel(c, P(r, "sid")))

    def decide(c: Caller, b: Any, r: Request) -> Any:
        b = _obj(b)
        if not (isinstance(b.get("approve"), bool) and isinstance(b.get("payload_hash"), str) and isinstance(b.get("note", ""), str)):
            raise MailError("bad_request", "send approve (true/false), payload_hash (as shown) and an optional note")
        return ob.decide(c, P(r, "sid"), approve=b["approve"], payload_hash_seen=b["payload_hash"], note=b.get("note", ""))

    route("POST", "/submissions/{sid}/decide", "submission.decide", decide)
    route("GET", "/approvals", "approvals", lambda c, b, r: {"approvals": ob.pending_approvals(c)})

    def process(c: Caller, b: Any, r: Request) -> Any:
        if "mail_admin" not in st._who(c).roles:
            raise MailError("forbidden", "this needs the mail_admin role", 403)
        return {"processed": ob.process_due()}

    route("POST", "/outbox/process", "outbox.process", process)

    # rules and settings
    route("GET", "/mailboxes/{mb}/rules", "rules", lambda c, b, r: {"rules": rules.list_rules(st, c, P(r, "mb"))})
    route("POST", "/mailboxes/{mb}/rules", "rule.create", lambda c, b, r: rules.create_rule(st, c, P(r, "mb"), b), status=201)
    route("POST", "/mailboxes/{mb}/rules/dry-run", "rule.dry_run", lambda c, b, r: rules.dry_run(st, c, P(r, "mb"), b))
    route("PUT", "/mailboxes/{mb}/rules/{rid}", "rule.update", lambda c, b, r: rules.update_rule(st, c, P(r, "mb"), P(r, "rid"), b))
    route("DELETE", "/mailboxes/{mb}/rules/{rid}", "rule.delete", lambda c, b, r: rules.delete_rule(st, c, P(r, "mb"), P(r, "rid")))
    route("GET", "/mailboxes/{mb}/settings", "mailbox.settings", lambda c, b, r: st.get_mailbox_settings(c, P(r, "mb")))
    route("PUT", "/mailboxes/{mb}/settings", "mailbox.settings.set", lambda c, b, r: st.set_mailbox_settings(c, P(r, "mb"), _obj(b)))
    route("PUT", "/mailboxes/{mb}/aliases", "alias.add", lambda c, b, r: {"aliases": st.add_alias(c, P(r, "mb"), str(_obj(b).get("address", "")))})
    route("GET", "/mailboxes/{mb}/delegates", "delegates", lambda c, b, r: {"delegates": st.delegates(c, P(r, "mb"))})
    route("PUT", "/mailboxes/{mb}/delegates", "delegate.set", lambda c, b, r: st.set_delegate(c, P(r, "mb"), str(_obj(b).get("user_id", "")), _obj(b).get("rights")))
    route("DELETE", "/mailboxes/{mb}/delegates", "delegate.remove", lambda c, b, r: st.remove_delegate(c, P(r, "mb"), Q(r, "user_id") or ""))
    route("PUT", "/mailboxes/{mb}/quota", "quota", lambda c, b, r: st.set_quota(c, P(r, "mb"), _obj(b).get("quota_bytes")))
    route("PUT", "/mailboxes/{mb}/legal-hold", "legal_hold", lambda c, b, r: st.set_hold(c, P(r, "mb"), _obj(b).get("on"), _obj(b).get("message_ids")))

    # connector
    route("GET", "/mailboxes/{mb}/accounts", "accounts", lambda c, b, r: {"accounts": connector.list_accounts(st, c, P(r, "mb"))})
    route("POST", "/mailboxes/{mb}/accounts", "account.create", lambda c, b, r: connector.create_account(st, c, P(r, "mb"), b), status=201)
    route("DELETE", "/mailboxes/{mb}/accounts/{aid}", "account.delete", lambda c, b, r: connector.delete_account(st, c, P(r, "mb"), P(r, "aid")))
    route("POST", "/mailboxes/{mb}/sync", "sync", lambda c, b, r: connector.sync_mailbox(st, c, P(r, "mb"), d.imap_factory, d.secrets))

    # assistant
    route("POST", "/mailboxes/{mb}/assistant/summarise", "assistant.summarise", lambda c, b, r: ai.summarise_thread(c, P(r, "mb"), str(_obj(b).get("thread_id", ""))))
    route("POST", "/mailboxes/{mb}/assistant/action-items", "assistant.action_items", lambda c, b, r: ai.action_items(c, P(r, "mb"), str(_obj(b).get("thread_id", ""))))
    route("POST", "/mailboxes/{mb}/assistant/triage", "assistant.triage", lambda c, b, r: ai.triage(c, P(r, "mb"), str(_obj(b).get("message_id", ""))))
    route("POST", "/mailboxes/{mb}/assistant/draft-reply", "assistant.draft_reply", lambda c, b, r: ai.draft_reply(
        c, P(r, "mb"), str(_obj(b).get("message_id", "")), str(_obj(b).get("instruction", ""))), status=201)

    # organisation settings, retention, DKIM
    route("GET", "/settings", "settings", lambda c, b, r: st.org_settings(st._who(c).org))
    route("PUT", "/settings", "settings.set", lambda c, b, r: st.set_org_settings(c, _obj(b)))
    route("GET", "/domains", "domains", lambda c, b, r: {"domains": st.domains(c)})
    route("POST", "/domains", "domain.claim", lambda c, b, r: st.claim_domain(c, _obj(b).get("domain", "")), status=201)
    route("POST", "/domains/verify", "domain.verify", lambda c, b, r: st.verify_domain(c, _obj(b).get("domain", ""), d.inbound.resolver))
    route("POST", "/retention/run", "retention", lambda c, b, r: st.retention_run(c))

    def dkim_info(c: Caller, b: Any, r: Request) -> Any:
        who = st._who(c)
        if "mail_admin" not in who.roles:
            raise MailError("forbidden", "this needs the mail_admin role", 403)
        s = st.org_settings(who.org)
        if not s["dkim_domains"]:
            return {"status": "not_configured", "reason": "set dkim_domains in the mail settings first"}
        try:
            txt = dkim.dns_record(dkim.load_or_create_key(s["dkim_selector"]))
        except (OSError, ValueError):
            raise MailError("dkim_unavailable", "the signing key could not be read or created", 503) from None
        audit("dkim.record.read", who.id, who.org)
        return {"status": "ok", "records": [{"name": f"{s['dkim_selector']}._domainkey.{dom}", "type": "TXT", "value": txt} for dom in s["dkim_domains"]]}

    route("GET", "/settings/dkim", "dkim", dkim_info)

    # DPDP
    route("GET", "/mailboxes/{mb}/export", "export", lambda c, b, r: st.export_mailbox(c, P(r, "mb"), legal_request=Q(r, "legal_request") or ""))
    route("POST", "/mailboxes/{mb}/legal-export", "legal_export.request", lambda c, b, r: st.request_legal_export(c, P(r, "mb"), str(_obj(b).get("reason", ""))))
    route("POST", "/legal-exports/{rid}/decide", "legal_export.decide", lambda c, b, r: st.decide_legal_export(c, P(r, "rid"), _obj(b).get("approve"), _obj(b).get("request_hash", "")))
    route("GET", "/legal-exports", "legal_export.list", lambda c, b, r: {"requests": st.pending_legal_exports(c)})

    def erase(c: Caller, b: Any, r: Request) -> Any:
        if Q(r, "confirm") != "erase":
            raise MailError("confirm_required", "add ?confirm=erase: erasure cannot be undone")
        return st.erase_mailbox(c, P(r, "mb"))

    route("DELETE", "/mailboxes/{mb}", "erase", erase)
    return d
