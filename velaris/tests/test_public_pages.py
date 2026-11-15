"""The public HTML pages (KAN-123..127): shells, strict CSP, static allowlist, /jobs/<slug>, CSRF origin guard, abuse cases, the browser PoW."""
import base64
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from velaris.agentkit import hiring_forms as hf
from velaris.agentkit.hiring_testkit import as_, tiny_pdf
from velaris.agents.JOB_POSTINGS import main as jp
from velaris.agents.JOB_POSTINGS.main import JobPostings
from velaris.api.public import CSP, PublicSettings, RouteLimit, create_public_app
from velaris.tests.test_api_public import TOKEN, esign_world, fast_pow, solved, tick, world, err, client  # noqa: F401  (fixtures)
from velaris.tests.test_hiring_postings import valid_through

PAGES = ["/apply/{f}", "/status/" + TOKEN, "/withdraw/" + TOKEN, "/schedule/" + TOKEN, "/sign/" + TOKEN, "/interview/" + TOKEN]
STATIC = Path(__file__).parents[1] / "api" / "public_static"


def live_posting(world):
    post, c = JobPostings(), world["c"]
    with as_(c["rec"]):
        pid = post.prepare_careers_posting(requisition_id=world["rid"], valid_through=valid_through())["posting"]["id"]
    with as_(c["mgr"]):
        post.approve_posting(posting_id=pid)
    with as_(c["rec"]):
        return post, pid, post.mark_posting_live(posting_id=pid)["posting"]


def test_every_page_is_an_inline_free_shell_under_the_csp(client, world):
    for path in PAGES:
        r = client.get(path.format(f=world["fid"]))
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html"), path
        assert r.headers["content-security-policy"] == CSP and "unsafe" not in CSP and "frame-ancestors 'none'" in CSP
        assert "set-cookie" not in r.headers and r.headers["referrer-policy"] == "no-referrer" and r.headers["cache-control"] == "no-store"
        body = r.text
        assert re.findall(r"<script[^>]*>", body) == ['<script src="/static/public.js" defer>'], path       # no inline script
        assert not re.search(r"\sstyle=|\son[a-z]+=", body), path
        assert '<html lang="en">' in body and "<title>" in body and 'name="viewport"' in body and "<noscript>" in body and 'class="skip"' in body
        assert 'noindex' in body


def test_static_files_are_an_allowlist(client):
    for name in ("public.js", "pow-worker.js", "public.css"):
        r = client.get(f"/static/{name}")
        assert r.status_code == 200 and "max-age" in r.headers["cache-control"]
    for bad in ("secret", "public.js.map", "..%2Fpublic.py", "%2e%2e%2f%2e%2e%2fmain.py", "public.py"):
        assert client.get(f"/static/{bad}").status_code == 404


def test_the_scripts_never_touch_innerhtml_cookies_storage_or_the_console():
    for n in ("public.js", "pow-worker.js"):
        src = (STATIC / n).read_text()
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "document.cookie", "localStorage", "sessionStorage", "console.", "Authorization"):
            assert banned not in src, (n, banned)


def test_malformed_unknown_and_oversize_identifiers_get_one_generic_404_page(client):
    for bad in ("short", "x" * 101, "a b" * 10, "%3Cscript%3E" * 4):
        for route in ("status", "withdraw", "schedule", "sign", "interview"):
            r = client.get(f"/{route}/{bad}")
            assert r.status_code == 404 and "not valid or has expired" in r.text and bad not in r.text
    assert client.get("/apply/" + "f" * 81).status_code == 404


def test_page_requests_are_rate_limited_per_ip(esign_world, tick):
    c = TestClient(create_public_app(PublicSettings(esign=esign_world[0], clock=tick, limits={"page": RouteLimit(1024, 100, 3)})), raise_server_exceptions=False)
    codes = [c.get("/status/" + TOKEN).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert "too many" in c.get("/status/" + TOKEN).text


def test_tokens_in_page_paths_never_reach_the_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    client.get("/status/" + TOKEN)
    client.post("/careers/withdraw/" + TOKEN, json={})
    server = [r.getMessage() for r in caplog.records if not r.name.startswith(("httpx", "asyncio"))]      # the test client's own log is not the server's
    assert not any(TOKEN in m for m in server)


# ---- CSRF ------------------------------------------------------------------------------------------------------------------
def test_a_cross_site_post_is_refused_before_the_token_is_even_looked_at(client, world):
    sched = world["sched"]
    for headers in ({"origin": "https://evil.example"}, {"origin": "null"}, {"sec-fetch-site": "cross-site"}):
        err(client.post(f"/schedule/{sched}/cancel", json={}, headers=headers), 403, "denied")
    # same-origin and non-browser posts still work
    assert client.post(f"/schedule/{sched}/cancel", json={}, headers={"origin": "http://testserver"}).status_code == 404       # nothing booked: generic refusal, not 403
    assert client.post(f"/schedule/{sched}/cancel", json={}).status_code == 404


def test_a_listed_cors_origin_may_post(esign_world, tick):
    c = TestClient(create_public_app(PublicSettings(esign=esign_world[0], clock=tick, cors_origins=("https://careers.example.com",))), raise_server_exceptions=False)
    assert c.post(f"/careers/withdraw/{TOKEN}", json={}, headers={"origin": "https://careers.example.com"}).status_code == 404
    assert c.post(f"/careers/withdraw/{TOKEN}", json={}, headers={"origin": "https://evil.example"}).status_code == 403


# ---- /jobs/<slug> ----------------------------------------------------------------------------------------------------------
def test_a_live_job_page_carries_the_json_ld_and_nothing_else_is_public(client, world):
    post, pid, p = live_posting(world)
    slug = p["slug"]
    r = client.get(f"/jobs/{slug}")
    assert r.status_code == 200 and 'content="index,follow"' in r.text and "Apply for this job" in r.text
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.S).group(1))
    assert ld == p["jsonld"] and ld["@type"] == "JobPosting" and r.headers["content-security-policy"] == CSP
    assert "<h1>" in r.text and "set-cookie" not in r.headers
    go = client.get(f"/jobs/{slug}/apply", follow_redirects=False)
    assert go.status_code == 303 and go.headers["location"] == f"/apply/{world['fid']}"
    with as_(world["c"]["rec"]):
        post.take_down_posting(posting_id=pid)
    for path in (f"/jobs/{slug}", f"/jobs/{slug}/apply"):
        assert client.get(path).status_code == 404                                       # taken down == unknown


def test_draft_expired_unknown_and_hostile_slugs_are_the_same_404(client, world):
    post, c = JobPostings(), world["c"]
    with as_(c["rec"]):
        draft = post.prepare_careers_posting(requisition_id=world["rid"], valid_through=valid_through())["posting"]
    assert client.get(f"/jobs/{draft['slug']}").status_code == 404                        # prepared, not live
    bodies = {client.get(f"/jobs/{s}").text for s in (draft["slug"], "no-such-job", "%3Cscript%3Ealert(1)%3C", "A" * 200)}
    assert len(bodies) == 1 and "Not available" in bodies.pop()
    with as_(c["mgr"]):
        post.approve_posting(posting_id=draft["id"])
    with as_(c["rec"]):
        post.mark_posting_live(posting_id=draft["id"])
    assert client.get(f"/jobs/{draft['slug']}").status_code == 200

    def expire(d):
        d["postings"][draft["id"]]["valid_through"] = "2001-01-01"
    jp._st().update(expire)
    assert client.get(f"/jobs/{draft['slug']}").status_code == 404                        # validThrough has passed


def test_a_job_page_without_a_published_form_has_no_apply_redirect(client, world):
    _post, _pid, p = live_posting(world)

    hf._st().update(lambda d: [f.update(status="draft") for f in d["forms"].values()])
    assert client.get(f"/jobs/{p['slug']}").status_code == 200
    assert client.get(f"/jobs/{p['slug']}/apply", follow_redirects=False).status_code == 404


# ---- what the pages call: abuse cases through the page's own request shapes ----------------------------------------------------
def test_apply_page_calls_reject_replay_oversize_and_a_stale_token(client, world):
    fid = world["fid"]
    from velaris.tests.test_hiring_forms import ANSWERS
    body = {"answers": ANSWERS, "pow_solution": solved(client, fid), "file_name": "cv.pdf",
            "file_base64": base64.b64encode(tiny_pdf("Skills: Python and SQL, 4 years")).decode()}
    first = client.post(f"/careers/apply/{fid}", json=body)
    assert first.status_code == 200, first.text
    assert client.post(f"/careers/apply/{fid}", json=body).status_code == 400                    # replayed proof
    err(client.post(f"/careers/apply/{fid}", content=b"{" + b" " * (2 * 1024 * 1024 + 10) + b"}", headers={"content-type": "application/json"}), 413, "too_large")
    err(client.post(f"/careers/apply/{fid}", content=b"a=1", headers={"content-type": "application/x-www-form-urlencoded"}), 415, "unsupported_media_type")
    assert client.get("/careers/status/" + "z" * 40).status_code == 404


# ---- the browser's proof of work must agree with the server ------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed (UNVERIFIED here)")
def test_the_browser_pow_solver_finds_what_the_server_accepts(client, world):
    fid = world["fid"]
    ch = client.get(f"/careers/challenge/{fid}").json()["result"]["challenge"]
    js = (f"const {{sha256,zeroBits}}=require({json.dumps(str(STATIC / 'pow-worker.js'))});const e=new TextEncoder();"
          f"const salt={json.dumps(ch['salt'])},bits={ch['bits']};for(let n=0;;n++){{if(zeroBits(sha256(e.encode(salt+':'+n)))>=bits){{console.log(n);break}}}}")
    n = int(subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60, check=True).stdout)
    assert hf.check_solution({**ch, "n": n}, fid) is None
