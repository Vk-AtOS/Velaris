"""Data-subject export and erasure for the paperwork agents that are not keyed by employee id (OFFER_LETTERS, ESIGN).

EMPLOYEE_RECORDS hands every participant `links`: {"email", "application_id", "offer_id"} taken from the employee record
before it is erased. A record belongs to the subject when it carries one of those. What happens to it is decided by the
retention registry (velaris.agentkit.onboarding_retention), never here:

  signed or live contract papers (offer accepted/sent, sealed e-sign request)  class employment_contract: HELD while the
                                  registry says so (today: statutory period unverified, so needs_review), erased once it allows
  anything that never became a contract (draft, declined, withdrawn, expired, voided)  anonymised now

Both functions return {"erased": [...], "held": [...]} in the shape every participant uses.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit.onboarding_common import Store, iso

logger = logging.getLogger("velaris.onboarding_dsr")
LIVE_OFFER = ("sent", "accepted")
LIVE_ESIGN = ("sent", "completed", "sealed")


def _offer_mine(o: Dict[str, Any], links: Dict[str, Any]) -> bool:
    c = o.get("candidate") or {}
    return bool((links.get("offer_id") and o["id"] == links["offer_id"])
                or (links.get("application_id") and c.get("application_id") == links["application_id"])
                or (links.get("email") and str(c.get("email", "")).lower() == str(links["email"]).lower()))


def offers_export(store: Store, org: str, links: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"id": o["id"], "status": o["status"], "role_title": o["terms"]["role_title"], "join_date": o["terms"]["join_date"],
             "candidate_name": o["candidate"]["name"], "sent_at": o["sent_at"], "response": o["response"]}
            for o in store.all("offers", org) if _offer_mine(o, links)]


def offers_erase(store: Store, org: str, links: Dict[str, Any], on: date, now: Any) -> Dict[str, Any]:
    erased: List[str] = []
    held: List[Dict[str, Any]] = []
    contract = retention.decide("employment_contract", None, on)
    for o in store.all("offers", org):
        if not _offer_mine(o, links) or o["candidate"].get("erased"):
            continue
        if o["status"] in LIVE_OFFER and contract["action"] != "erase":
            held.append({"what": f"offer:{o['id']}", **contract})
            continue

        def _do(r: Dict[str, Any]) -> None:
            r["candidate"] = {"name": "erased", "email": "erased", "application_id": None, "consent": None, "erased": True}
            r["terms"]["manager_name"], r["erased_at"] = "", iso(now)

        store.update("offers", o["id"], org, _do)
        erased.append(f"offer:{o['id']}:candidate name and e-mail")
    return {"erased": erased, "held": held}


def _esign_mine(r: Dict[str, Any], links: Dict[str, Any]) -> bool:
    email = str(links.get("email") or "").lower()
    return bool(email and any(s["email"] == email for s in r["signers"])) or bool(
        links.get("offer_id") and r.get("document_ref") == links["offer_id"])


def esign_export(store: Store, org: str, links: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"id": r["id"], "title": r["title"], "status": r["status"], "document_sha256": r["document_sha256"],
             "signers": [{"name": s["name"], "email": s["email"], "state": s["state"], "signed_at": s.get("signed_at")} for s in r["signers"]]}
            for r in store.all("requests", org) if _esign_mine(r, links)]


def esign_erase(store: Store, org: str, links: Dict[str, Any], on: date, now: Any) -> Dict[str, Any]:
    erased: List[str] = []
    held: List[Dict[str, Any]] = []
    contract = retention.decide("employment_contract", None, on)
    email = str(links.get("email") or "").lower()
    for r in store.all("requests", org):
        if not _esign_mine(r, links) or r.get("erased_at"):
            continue
        if r["status"] in LIVE_ESIGN and contract["action"] != "erase":
            held.append({"what": f"esign:{r['id']}", **contract})       # signed evidence stays whole: altering it would void the seal
            continue

        def _do(x: Dict[str, Any]) -> None:
            for s in x["signers"]:
                if s["email"] == email or not email:
                    s.update(name="erased", email="erased", phone=None, evidence=None, token_sha256=None)
            x["erased_at"] = iso(now)

        store.update("requests", r["id"], org, _do)
        erased.append(f"esign:{r['id']}:signer name and e-mail")
    return {"erased": erased, "held": held}
