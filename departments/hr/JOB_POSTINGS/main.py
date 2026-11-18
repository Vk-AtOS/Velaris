"""JOB_POSTINGS: publish a requisition without paying anyone.

  careers page   schema.org JobPosting JSON-LD (validated against the required fields), an HTML fragment, and the
                 Google Indexing API notification body. Building them sends nothing. send_indexing_notification is the
                 only method that goes out, and it is an `act`, refuses to run outside an approved flow step, takes its
                 token from SECRETS_VAULT (GOOGLE_INDEXING_ACCESS_TOKEN) and uses the same checked, pinned connection
                 as the Atlassian connectors (public addresses only, no redirects, only indexing.googleapis.com).
  posting packs  for every other board: text, fields, manual steps, a tracked link, a take-down date and task.
  approvals      a pack or posting is approved by someone other than whoever prepared it, and only an approved one can
                 be marked posted/live.
  tracking       each pack has a tracking code; resolve_tracking(code) gives the ATS `source` and requisition.

State under agent_dir("JOB_POSTINGS"); every record stamped with `org`; ledger entries hold hashes only.
"""
import logging
import secrets
from typing import Any, Dict, Optional
from urllib.parse import quote, urlsplit

import httpx

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_posting as hp
from velaris.agentkit import hiring_skills as sk
from velaris.agentkit.hiring_common import DAY, DECIDERS, HIRING, RECRUITING, HiringError, acts, audit, bad, hid, mine, now, reads
from velaris.agentkit import hiring_forms as hf
from velaris.agentkit.results import ok, fail
from velaris.agents.SECRETS_VAULT.main import SecretsVault
from velaris.agents.JIRA.atlassian import refuse_unless_approved
from velaris.intel.web_fetch import FetchError, _resolve, check_public, pinned

logger = logging.getLogger("JOB_POSTINGS")
AGENT = "JOB_POSTINGS"
TOKEN_SECRET = "GOOGLE_INDEXING_ACCESS_TOKEN"
INDEXING_HOST = "indexing.googleapis.com"


def _st() -> Any:
    return hc.store(AGENT, "postings.json", {"company": {}, "postings": {}, "packs": {}})


def _company(d: Dict[str, Any], org: str) -> Dict[str, str]:
    c = d["company"].get(org)
    if not c:
        raise HiringError("not_configured", "set_company_profile first (company name, website, careers page base URL)")
    return c


def _posting(d: Dict[str, Any], org: str, pid: Any) -> Dict[str, Any]:
    p = d["postings"].get(str(pid))
    if not p or p["org"] != org:
        raise HiringError("not_found", "no such posting")
    return p


def _https(url: str, name: str) -> str:
    u = urlsplit(str(url).strip())
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise bad(f"{name} must be an https URL")
    return str(url).strip().rstrip("/")


class JobPostings:
    """Job publishing: markup, indexing notice, posting packs, approvals, tracked links."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "boards": sorted(hp.BOARDS)}

    @acts(AGENT, RECRUITING)
    def set_company_profile(self, caller, name: str, website: str, careers_base_url: str, contact_email: str = "") -> Dict[str, Any]:
        """The hiring organisation as it appears in job markup. careers_base_url is where /jobs/<slug> pages are served."""
        rec = {"name": hc.need_text(name, "name", 120), "website": _https(website, "website"),
               "careers_base_url": _https(careers_base_url, "careers_base_url"), "contact_email": str(contact_email)[:254]}

        def go(d: Dict[str, Any]) -> None:
            audit(AGENT, "company.set", caller.org, caller, digest=hc.digest(rec))
            d["company"][caller.org] = rec
        _st().update(go)
        return ok(company=rec)

    @reads(AGENT, HIRING)
    def get_company_profile(self, caller) -> Dict[str, Any]:
        return ok(company=_st().load()["company"].get(caller.org))

    # ---- careers page -----------------------------------------------------------------------------
    @acts(AGENT, RECRUITING)
    def prepare_careers_posting(self, caller, requisition_id: str, valid_through: str, salary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build and validate the JobPosting JSON-LD, the careers fragment and the indexing body for an approved or open
        requisition. salary: {"min": "40000", "max": "60000", "unit": "MONTH"} (INR, as strings). Sends nothing."""
        org, at = caller.org, now()
        req = hc.load_requisition(org, requisition_id)
        if not req or req["state"] not in ("approved", "open"):
            raise HiringError("conflict", "the requisition must exist and be approved (or open) before it is posted")
        vt = hc.parse_date(valid_through, "valid_through")
        if not at < vt <= at + hp.MAX_VALID_DAYS * DAY:
            raise bad(f"valid_through must be in the future and within {hp.MAX_VALID_DAYS} days")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            company = _company(d, org)
            if any(p["requisition_id"] == requisition_id and p["org"] == org and p["status"] in ("draft", "approved", "live") for p in d["postings"].values()):
                raise HiringError("conflict", "this requisition already has an active posting; take it down first")
            slug = hp.slugify(req["title"], req["id"])
            job_url = f"{company['careers_base_url']}/jobs/{slug}"
            ld = hp.job_posting_jsonld(req, company, sk.load_table(org), job_url=job_url, date_posted=hc.iso(at)[:10],
                                       valid_through=hc.iso(vt)[:10], salary=salary)
            problems = hp.validate_jsonld(ld)
            if problems:
                raise HiringError("invalid_input", "JobPosting markup is not valid: " + "; ".join(problems))
            pid = hc.new_id("post")
            rec = {"id": pid, "org": org, "requisition_id": req["id"], "slug": slug, "job_url": job_url, "status": "draft",
                   "valid_through": hc.iso(vt)[:10], "jsonld": ld, "fragment_html": hp.careers_fragment(ld, f"{job_url}/apply?src=careers_page"),
                   "wording_flags": hp.wording_flags(ld["description"]), "prepared_by": caller.id, "prepared_at": at,
                   "approved_by": None, "indexing_sent": []}
            audit(AGENT, "posting.prepared", org, caller, posting=hid(org, pid), requisition=hid(org, req["id"]), digest=hc.digest(ld))
            d["postings"][pid] = rec
            return rec
        rec = _st().update(go)
        return ok(posting=rec, indexing_payload=hp.indexing_payload(rec["job_url"], "URL_UPDATED"))

    @reads(AGENT, HIRING)
    def get_posting(self, caller, posting_id: str) -> Dict[str, Any]:
        p = _posting(_st().load(), caller.org, posting_id)
        return ok(posting=p, indexing_payload=hp.indexing_payload(p["job_url"], "URL_UPDATED"),
                  takedown_payload=hp.indexing_payload(p["job_url"], "URL_DELETED"))

    def _post_move(self, caller, posting_id: str, frm: tuple, to: str, action: str) -> Dict[str, Any]:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            p = _posting(d, caller.org, posting_id)
            if p["status"] not in frm:
                raise HiringError("conflict", f"posting is {p['status']}; needs {list(frm)}")
            if to == "approved":
                if p["prepared_by"] == caller.id:
                    raise HiringError("denied", "a posting is approved by someone other than whoever prepared it")
                p["approved_by"] = caller.id
            audit(AGENT, action, caller.org, caller, posting=hid(caller.org, posting_id))
            p["status"] = to
            return p
        return ok(posting=_st().update(go))

    @acts(AGENT, DECIDERS)
    def approve_posting(self, caller, posting_id: str) -> Dict[str, Any]:
        """Approve the markup and text (not by whoever prepared it). Required before it can go live."""
        return self._post_move(caller, posting_id, ("draft",), "approved", "posting.approved")

    @acts(AGENT, RECRUITING)
    def mark_posting_live(self, caller, posting_id: str) -> Dict[str, Any]:
        """Record that the approved page is now published on the careers site."""
        return self._post_move(caller, posting_id, ("approved",), "live", "posting.live")

    @acts(AGENT, RECRUITING)
    def take_down_posting(self, caller, posting_id: str) -> Dict[str, Any]:
        """Record that the page was removed (or its validThrough set in the past); then send URL_DELETED."""
        return self._post_move(caller, posting_id, ("live", "approved", "draft"), "taken_down", "posting.taken_down")

    @acts(AGENT, RECRUITING)
    def send_indexing_notification(self, caller, posting_id: str, kind: str = "URL_UPDATED") -> Dict[str, Any]:
        """Tell Google a job page changed (URL_UPDATED, needs a live posting) or was removed (URL_DELETED, needs a taken-down
        one). The only method here that goes out. Runs only as an approved step; token from SECRETS_VAULT."""
        if (refused := refuse_unless_approved(AGENT, "send_indexing_notification", {"posting": hid(caller.org, posting_id)})):
            return refused
        d = _st().load()
        p = _posting(d, caller.org, posting_id)
        need = "live" if kind == "URL_UPDATED" else "taken_down"
        if kind not in ("URL_UPDATED", "URL_DELETED") or p["status"] != need:
            raise HiringError("conflict", f"{kind} needs a posting that is {need} (this one is {p['status']})")
        body = hp.indexing_payload(p["job_url"], kind)["body"]
        token = self._token()
        if not token:
            raise HiringError("not_configured", f"the vault secret {TOKEN_SECRET} is not set")
        audit(AGENT, "indexing.sending", caller.org, caller, posting=hid(caller.org, posting_id), kind=kind)
        status = self._post(hp.INDEXING_ENDPOINT, body, token)

        def mark(d2: Dict[str, Any]) -> None:
            d2["postings"][p["id"]]["indexing_sent"].append({"kind": kind, "at": now(), "http_status": status})
        _st().update(mark)
        return ok(sent=kind, http_status=status, accepted=200 <= status < 300)

    def _token(self) -> Optional[str]:
        if self.config.get("access_token"):
            return str(self.config["access_token"])
        vault = self.config.get("vault")
        if vault is None:
            vault = SecretsVault()
        try:
            v = vault.get_secret(TOKEN_SECRET)
        except (ValueError, OSError) as e:
            logger.warning("vault secret unavailable: %s", type(e).__name__)
            return None
        return v.strip() if v and v.strip() else None

    def _post(self, url: str, body: Dict[str, Any], token: str) -> int:
        if urlsplit(url).hostname != INDEXING_HOST:
            raise HiringError("denied", "only the Google Indexing API host may be called")
        try:
            addresses = check_public(url, self.config.get("resolver", _resolve))
        except FetchError as e:
            raise HiringError("blocked", e.reason) from None
        with httpx.Client(transport=self.config.get("transport"), follow_redirects=False, timeout=20.0,
                          limits=httpx.Limits(max_keepalive_connections=0)) as client:
            for address in addresses:
                target, headers, ext = pinned(url, address)
                try:
                    r = client.post(target, json=body, extensions=ext,
                                    headers={**headers, "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
                    return r.status_code
                except httpx.ConnectError:
                    continue
                except httpx.HTTPError as e:
                    raise HiringError("network", type(e).__name__) from None
        raise HiringError("network", "could not connect")

    # ---- posting packs for other boards ----------------------------------------------------------------
    @acts(AGENT, RECRUITING)
    def prepare_pack(self, caller, posting_id: str, board: str) -> Dict[str, Any]:
        """A pack for one board (text, fields, manual steps, tracked link, take-down date and task). Nothing is posted."""
        org, at = caller.org, now()

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            p = _posting(d, org, posting_id)
            if p["status"] in ("taken_down",):
                raise HiringError("conflict", "the posting was taken down")
            if any(k["posting_id"] == p["id"] and k["board"] == board and k["status"] in ("prepared", "approved", "posted") for k in d["packs"].values()):
                raise HiringError("conflict", f"there is already an open pack for {board}")
            req = hc.load_requisition(org, p["requisition_id"])
            if not req:
                raise HiringError("not_found", "the requisition is gone")
            code = "t" + secrets.token_hex(4)
            url = f"{p['job_url']}/apply?src={quote(board)}&t={code}"
            days = hp.BOARDS.get(board, {}).get("days", 30)
            pack = hp.posting_pack(board, req, _company(d, org), sk.load_table(org), tracked_url=url, tracking_code=code,
                                   takedown_ts=min(at + days * DAY, hc.parse_date(p["valid_through"], "valid_through")))
            pid = hc.new_id("pack")
            pack.update(id=pid, org=org, posting_id=p["id"], requisition_id=p["requisition_id"], status="prepared",
                        prepared_by=caller.id, prepared_at=at, approved_by=None, posted_by=None, posted_at=None, live_url=None)
            audit(AGENT, "pack.prepared", org, caller, pack=hid(org, pid), board=board, digest=hc.digest(pack["text"]))
            d["packs"][pid] = pack
            return pack
        return ok(pack=_st().update(go))

    def _pack_move(self, caller, pack_id: str, frm: str, to: str, action: str, **extra: Any) -> Dict[str, Any]:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            k = d["packs"].get(str(pack_id))
            if not k or k["org"] != caller.org:
                raise HiringError("not_found", "no such pack")
            if k["status"] != frm:
                raise HiringError("conflict", f"pack is {k['status']}; needs {frm}")
            if to == "approved":
                if k["prepared_by"] == caller.id:
                    raise HiringError("denied", "a pack is approved by someone other than whoever prepared it")
                k["approved_by"] = caller.id
            if to == "posted":
                k.update(posted_by=caller.id, posted_at=now(), live_url=extra["live_url"])
            audit(AGENT, action, caller.org, caller, pack=hid(caller.org, pack_id), board=k["board"])
            k["status"] = to
            return k
        return ok(pack=_st().update(go))

    @acts(AGENT, DECIDERS)
    def approve_pack(self, caller, pack_id: str) -> Dict[str, Any]:
        """Approve a pack's text for pasting (not by whoever prepared it)."""
        return self._pack_move(caller, pack_id, "prepared", "approved", "pack.approved")

    @acts(AGENT, RECRUITING)
    def mark_pack_posted(self, caller, pack_id: str, live_url: str = "") -> Dict[str, Any]:
        """A person says they pasted the approved pack on the board. Refused for a pack nobody approved."""
        url = _https(live_url, "live_url") if live_url else ""
        return self._pack_move(caller, pack_id, "approved", "posted", "pack.posted", live_url=url)

    @acts(AGENT, RECRUITING)
    def mark_pack_taken_down(self, caller, pack_id: str) -> Dict[str, Any]:
        return self._pack_move(caller, pack_id, "posted", "taken_down", "pack.taken_down")

    @reads(AGENT, HIRING)
    def list_packs(self, caller, posting_id: str = "") -> Dict[str, Any]:
        return ok(packs=[k for k in mine(_st().load()["packs"].values(), caller.org) if not posting_id or k["posting_id"] == posting_id])

    @reads(AGENT, HIRING)
    def takedown_due(self, caller, within_days: int = 3) -> Dict[str, Any]:
        """Posted packs whose take-down date is today, past, or within `within_days`: the tasks to do."""
        if isinstance(within_days, bool) or not isinstance(within_days, int) or not 0 <= within_days <= 60:
            raise bad("within_days must be 0 to 60")
        limit = hc.iso(now() + within_days * DAY)[:10]
        return ok(tasks=[{"pack_id": k["id"], "board": k["board_name"], "takedown_date": k["takedown_date"], "task": k["takedown_task"],
                          "live_url": k["live_url"], "overdue": k["takedown_date"] < hc.iso(now())[:10]}
                         for k in mine(_st().load()["packs"].values(), caller.org) if k["status"] == "posted" and k["takedown_date"] <= limit])

    @reads(AGENT, HIRING)
    def resolve_tracking(self, caller, code: str) -> Dict[str, Any]:
        """The source (board) and requisition behind a tracking code: what to pass to ATS_CORE as `source` when an application
        arrives through that link. Unknown codes resolve to nothing; the source is then plain 'careers_page'."""
        for k in mine(_st().load()["packs"].values(), caller.org):
            if k["tracking_code"] == code:
                return ok(source=k["board"], requisition_id=k["requisition_id"], tracking_code=code)
        return ok(source="careers_page", requisition_id=None, tracking_code=None)


def public_job(slug: str) -> Dict[str, Any]:
    """Public, token-less read for GET /jobs/<slug>: only a LIVE posting that has not passed its validThrough date. Returns the stored
    JSON-LD and fragment (built and validated when prepared) and the published application form of the same requisition, if any.
    Anything else is the one generic not_found, so a draft, a taken-down or an expired job cannot be told apart from an unknown slug."""
    d = _st().load()
    p = next((p for p in d["postings"].values() if p["slug"] == slug and p["status"] == "live"), None)
    if not isinstance(slug, str) or not p or p["valid_through"] < hc.iso(now())[:10]:
        return fail("not_found", "this job is not available")
    form = next((f["id"] for f in hf._st().load()["forms"].values()
                 if f["org"] == p["org"] and f["requisition_id"] == p["requisition_id"] and f["status"] == "published"), None)
    return ok(title=p["jsonld"]["title"], fragment_html=p["fragment_html"], jsonld=p["jsonld"], form_id=form)
