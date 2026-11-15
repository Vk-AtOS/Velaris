"""Public job pages and the sitemap, read from the JOB_POSTINGS store (KAN-127).

A slug names one live posting. public_job() answers ONLY when exactly one live, unexpired posting carries the slug: when two
organisations (or two postings) ended up with the same slug, showing "the first" would put one organisation's job under the
other's address, so the slug then answers "not available" and the clash is logged. New slugs cannot clash in practice
(velaris.agentkit.hiring_posting.slugify ends in the whole 48-bit requisition id); older ones carried 24 bits.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from velaris.agentkit import hiring_forms as hf
from velaris.agentkit.hiring_common import iso, now, store
from velaris.agentkit.results import fail, ok

logger = logging.getLogger("velaris.hiring_public_jobs")
MAX_SITEMAP_URLS = 50_000          # the sitemap protocol limit


def live_postings() -> List[Dict[str, Any]]:
    """Every live posting that has not passed its validThrough date."""
    today = iso(now())[:10]
    d = store("JOB_POSTINGS", "postings.json", {"company": {}, "postings": {}, "packs": {}}).load()
    return [p for p in d["postings"].values() if p["status"] == "live" and p["valid_through"] >= today]


def clashing_slugs(posts: List[Dict[str, Any]]) -> set:
    return {s for s, n in Counter(p["slug"] for p in posts).items() if n > 1}


def public_job(slug: str) -> Dict[str, Any]:
    """Same answer as JOB_POSTINGS.public_job, but never the first of several postings sharing a slug."""
    posts = [p for p in live_postings() if p["slug"] == slug] if isinstance(slug, str) else []
    if len(posts) > 1:
        logger.warning("slug %s is carried by %d live postings; not served", slug, len(posts))
    if len(posts) != 1:
        return fail("not_found", "this job is not available")
    p = posts[0]
    form = next((f["id"] for f in hf._st().load()["forms"].values()
                 if f["org"] == p["org"] and f["requisition_id"] == p["requisition_id"] and f["status"] == "published"), None)
    return ok(title=p["jsonld"]["title"], fragment_html=p["fragment_html"], jsonld=p["jsonld"], form_id=form)


def sitemap_entries() -> List[Dict[str, str]]:
    """[{loc, lastmod}] for every live posting whose slug is unambiguous, newest first, at most MAX_SITEMAP_URLS."""
    posts = live_postings()
    bad = clashing_slugs(posts)
    out = [{"loc": p["job_url"], "lastmod": iso(p.get("prepared_at") or 0)[:10], "_t": p.get("prepared_at") or 0}
           for p in posts if p["slug"] not in bad and str(p["job_url"]).startswith("https://")]
    out.sort(key=lambda e: -e["_t"])
    return [{"loc": e["loc"], "lastmod": e["lastmod"]} for e in out[:MAX_SITEMAP_URLS]]
