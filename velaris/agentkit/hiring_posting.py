"""Pure builders for job publishing: schema.org JobPosting JSON-LD (+ validation), a careers-page fragment, the Google
Indexing API notification body, and a per-board "posting pack".

Why packs: apart from our own careers page (JobPosting markup, pushed with the Indexing API) there is no free
programmatic route to the boards a small Chennai company uses (research 05 section 2). So for every other board the
system prepares the exact text, fields, manual steps, a tracked link and a take-down date; a named person approves it,
a person pastes it, and the system records where and when it went live. Board facts below come from that research and
the ones it marks unverified are marked here too: check the board's page before relying on a limit.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from velaris.agentkit import hiring_skills as sk
from velaris.agentkit.hiring_common import bad

EMPLOYMENT_TYPES = ("FULL_TIME", "PART_TIME", "CONTRACTOR", "TEMPORARY", "INTERN", "VOLUNTEER", "PER_DIEM", "OTHER")
SALARY_UNITS = ("HOUR", "DAY", "WEEK", "MONTH", "YEAR")
INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
MAX_VALID_DAYS = 180

# board -> (display name, default days live, free-limit note, manual steps, verified?)
BOARDS: Dict[str, Dict[str, Any]] = {
    "linkedin": {"name": "LinkedIn", "days": 14, "verified": True,
                 "note": "Free post by a person in the LinkedIn UI: one active at a time, up to 14 days, applications capped. No API for new partners.",
                 "steps": ["Sign in as a company page admin", "Jobs > Post a free job", "Paste title, location, description from this pack",
                           "Set 'Apply on external website' to the tracked link", "Copy the live job URL back into the ATS"]},
    "naukri": {"name": "Naukri", "days": 7, "verified": False,
               "note": "Reported: one free job a month for verified company accounts, live 7 days. Unverified (the board's page was not readable).",
               "steps": ["Sign in to Naukri Recruiter", "Post a job and paste the fields below", "Add the tracked link in the description (no external-apply field is assumed)",
                         "Copy the live URL back into the ATS"]},
    "indeed": {"name": "Indeed", "days": 120, "verified": True,
               "note": "Free posts for India show up to 120 days. A home-built XML feed needs a one-time manual request to Indeed and may be refused; this pack is for manual posting.",
               "steps": ["Sign in to Indeed Employers", "Post a job with the fields below", "Use the tracked link as the apply URL where the form allows",
                         "Copy the live URL back into the ATS"]},
    "foundit": {"name": "foundit", "days": 30, "verified": False,
                "note": "No free route found; sales-quoted. Unverified.", "steps": ["Use only if the company holds a foundit plan", "Paste the fields below", "Record the live URL"]},
    "shine": {"name": "Shine", "days": 30, "verified": False, "note": "Paid; unverified.", "steps": ["Use only with a purchased pack", "Paste the fields below", "Record the live URL"]},
    "apna": {"name": "Apna", "days": 15, "verified": False, "note": "Conflicting reports on a free post; unverified.", "steps": ["Post in the Apna employer app", "Paste the fields below", "Record the live URL"]},
    "internshala": {"name": "Internshala", "days": 30, "verified": False, "note": "Reported free tier of one listing a month; unverified. Fits internships and fresher roles.",
                    "steps": ["Sign in as an employer", "Post as job or internship", "Paste the fields below", "Record the live URL"]},
    "ncs": {"name": "National Career Service (ncs.gov.in)", "days": 30, "verified": True,
            "note": "Free government portal; the employer registers and posts by hand.", "steps": ["Sign in to the employer account on ncs.gov.in", "Post the vacancy with the fields below", "Record the vacancy page URL"]},
    "local": {"name": "Local board or college placement cell", "days": 30, "verified": False, "note": "Anything else, for example a college placement office or a local WhatsApp group.",
              "steps": ["Send the text below to the board's contact", "Record where and when it was posted"]},
}
_FLAG_WORDS = re.compile(r"\b(male only|female only|only (?:males?|females?|men|women)|age (?:below|under|above|between)|"
                         r"(?:unmarried|married) (?:only|candidates?)|caste|religion|fair complexion|good looking|young (?:and )?energetic)\b", re.I)


def slugify(text: str, rid: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "job"
    return f"{base}-{rid.split('-')[-1][:6]}"


def decimal_amount(value: Any, name: str) -> Decimal:
    if isinstance(value, float) or isinstance(value, bool):
        raise bad(f"{name} must be a string or integer amount (money is never a float)")
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation as e:
        raise bad(f"{name} is not an amount") from e
    if not d.is_finite() or d <= 0 or d > Decimal("100000000"):
        raise bad(f"{name} must be a positive amount")
    return d


def wording_flags(text: str) -> List[str]:
    """Advert phrases that discriminate or may be read as discriminating. For the human approving the text."""
    return sorted({m.group(0).lower() for m in _FLAG_WORDS.finditer(text)})


def description_html(req: Dict[str, Any], table: sk.Table) -> str:
    reqs = req["requirements"]

    def items(rows: List[Dict[str, Any]]) -> str:
        return "".join(f"<li>{html.escape(table.label(r['skill_id']))}"
                       + (f" ({r['min_years']:g}+ years)" if r.get("min_years") else "") + "</li>" for r in rows)
    parts = [f"<p>{html.escape(req['title'])} at {html.escape(req['location']['city'])}.</p>"]
    if req.get("description"):
        parts += [f"<p>{html.escape(p)}</p>" for p in req["description"].split("\n\n") if p.strip()]
    parts.append("<h3>You should have</h3><ul>" + items(reqs["must"]) + "</ul>")
    if reqs["nice"]:
        parts.append("<h3>It helps if you have</h3><ul>" + items(reqs["nice"]) + "</ul>")
    if reqs.get("min_total_years"):
        parts.append(f"<p>Total experience: {reqs['min_total_years']:g}+ years.</p>")
    parts.append("<p>We never ask applicants for any fee.</p>")
    return "".join(parts)


def job_posting_jsonld(req: Dict[str, Any], company: Dict[str, str], table: sk.Table, *, job_url: str, date_posted: str,
                       valid_through: str, salary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ld: Dict[str, Any] = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": req["title"],
        "description": description_html(req, table), "datePosted": date_posted, "validThrough": valid_through,
        "employmentType": req["employment_type"], "directApply": True, "identifier": {"@type": "PropertyValue", "name": company["name"], "value": req["id"]},
        "hiringOrganization": {"@type": "Organization", "name": company["name"], "sameAs": company["website"]},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": req["location"]["city"],
                                                       "addressRegion": req["location"]["state"], "addressCountry": req["location"]["country"]}},
        "url": job_url}
    if salary:
        unit = salary.get("unit", "MONTH")
        if unit not in SALARY_UNITS:
            raise bad(f"salary.unit must be one of {list(SALARY_UNITS)}")
        lo, hi = decimal_amount(salary.get("min"), "salary.min"), decimal_amount(salary.get("max"), "salary.max")
        if hi < lo:
            raise bad("salary.max is below salary.min")
        num = lambda d: int(d) if d == d.to_integral_value() else float(d)
        ld["baseSalary"] = {"@type": "MonetaryAmount", "currency": "INR",
                            "value": {"@type": "QuantitativeValue", "minValue": num(lo), "maxValue": num(hi), "unitText": unit}}
    return ld


def validate_jsonld(ld: Dict[str, Any]) -> List[str]:
    """Problems that would make Google reject or ignore the markup. Empty list = the required fields are present and sane."""
    p: List[str] = []
    if ld.get("@type") != "JobPosting" or ld.get("@context") != "https://schema.org":
        p.append("@context/@type must be https://schema.org and JobPosting")
    for f in ("title", "description", "datePosted"):
        if not isinstance(ld.get(f), str) or not ld[f].strip():
            p.append(f"missing required field {f}")
    if len(str(ld.get("description", ""))) < 80:
        p.append("description is too short: it must be the full job, not a teaser")
    org = ld.get("hiringOrganization")
    if not isinstance(org, dict) or not org.get("name"):
        p.append("missing required hiringOrganization.name")
    addr = (ld.get("jobLocation") or {}).get("address") if isinstance(ld.get("jobLocation"), dict) else None
    if not isinstance(addr, dict) or not addr.get("addressCountry"):
        p.append("missing required jobLocation.address.addressCountry")
    dates: Dict[str, Optional[datetime]] = {}
    for f in ("datePosted", "validThrough"):
        if ld.get(f):
            try:
                dt = datetime.fromisoformat(str(ld[f]).replace("Z", "+00:00"))
                dates[f] = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                p.append(f"{f} is not an ISO 8601 date")
    if "datePosted" in dates and "validThrough" in dates and dates["validThrough"] <= dates["datePosted"]:
        p.append("validThrough must be after datePosted")
    if ld.get("employmentType") not in EMPLOYMENT_TYPES:
        p.append(f"employmentType must be one of {list(EMPLOYMENT_TYPES)}")
    if "baseSalary" in ld:
        v = (ld["baseSalary"] or {}).get("value", {})
        if (ld["baseSalary"] or {}).get("currency") != "INR" or v.get("unitText") not in SALARY_UNITS or not (v.get("minValue") or v.get("value")):
            p.append("baseSalary needs currency INR and a value with unitText and amounts")
    return p


def jsonld_script(ld: Dict[str, Any]) -> str:
    body = json.dumps(ld, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{body}\n</script>'


def careers_fragment(ld: Dict[str, Any], apply_url: str) -> str:
    """An HTML fragment for the careers page: the job, an apply link, and the JSON-LD. No login wall, no teaser."""
    a = ld["jobLocation"]["address"]
    return (f'<article class="job-posting">\n<h1>{html.escape(ld["title"])}</h1>\n'
            f'<p class="job-meta">{html.escape(a["addressLocality"])}, {html.escape(a["addressRegion"])} &middot; '
            f'{html.escape(ld["employmentType"].replace("_", " ").title())} &middot; Apply before {html.escape(ld["validThrough"][:10])}</p>\n'
            f'<div class="job-description">{ld["description"]}</div>\n'
            f'<p><a class="apply" href="{html.escape(apply_url, quote=True)}" rel="nofollow">Apply for this job</a></p>\n'
            f'{jsonld_script(ld)}\n</article>')


def indexing_payload(url: str, kind: str) -> Dict[str, Any]:
    if kind not in ("URL_UPDATED", "URL_DELETED"):
        raise bad("type must be URL_UPDATED or URL_DELETED")
    return {"endpoint": INDEXING_ENDPOINT, "method": "POST", "body": {"url": url, "type": kind},
            "needs": "an OAuth access token with scope https://www.googleapis.com/auth/indexing for a service account that is an owner "
                     "of the site in Search Console; stored as the vault secret GOOGLE_INDEXING_ACCESS_TOKEN",
            "quota": "200 publish requests per day per project by default", "sent": False}


def posting_pack(board: str, req: Dict[str, Any], company: Dict[str, str], table: sk.Table, *, tracked_url: str,
                 tracking_code: str, takedown_ts: float) -> Dict[str, Any]:
    spec = BOARDS.get(board)
    if not spec:
        raise bad(f"board must be one of {sorted(BOARDS)}")
    reqs = req["requirements"]
    loc = req["location"]
    must = [table.label(r["skill_id"]) + (f" ({r['min_years']:g}+ yrs)" if r.get("min_years") else "") for r in reqs["must"]]
    nice = [table.label(r["skill_id"]) for r in reqs["nice"]]
    lines = [req["title"], f"{company['name']}, {loc['city']}, {loc['state']}", f"Employment type: {req['employment_type'].replace('_', ' ').title()}",
             f"Openings: {req['openings']}", ""]
    if req.get("description"):
        lines += [req["description"].strip(), ""]
    lines += ["Required: " + ", ".join(must)]
    if nice:
        lines += ["Good to have: " + ", ".join(nice)]
    if reqs.get("min_total_years"):
        lines += [f"Experience: {reqs['min_total_years']:g}+ years"]
    lines += ["", f"Apply: {tracked_url}", "We never ask applicants for any fee."]
    text = "\n".join(lines)
    takedown = datetime.fromtimestamp(takedown_ts, timezone.utc).strftime("%Y-%m-%d")
    return {"board": board, "board_name": spec["name"], "text": text,
            "fields": {"job_title": req["title"], "company": company["name"], "city": loc["city"], "state": loc["state"],
                       "country": loc["country"], "employment_type": req["employment_type"], "openings": req["openings"],
                       "must_have_skills": must, "nice_to_have_skills": nice, "apply_url": tracked_url,
                       "contact_email": company.get("contact_email", "")},
            "manual_steps": list(spec["steps"]), "board_note": spec["note"], "board_facts_verified": spec["verified"],
            "tracking_code": tracking_code, "tracking_url": tracked_url, "takedown_date": takedown,
            "takedown_task": f"Take down the {spec['name']} post for '{req['title']}' on or before {takedown} and mark it taken down in JOB_POSTINGS",
            "wording_flags": wording_flags(text)}
