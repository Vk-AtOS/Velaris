"""KAN-72: the REAL Playwright driver against a local test web app (marker `browser`; skipped without Playwright and Chromium).

The browser has no network of its own: every request is answered by the SSRF-safe Fetcher, here wired to an in-process app through
httpx.MockTransport (host app.test -> a public-looking address, so the same checks as production run). The app has a form that POSTs,
a records endpoint (the system of record) and a switch that makes it ACCEPT a submission but store a wrong value (a false success).
"""
import json
import urllib.parse

import httpx
import pytest

from velaris.control.browser import PlaywrightDriver
from velaris.control.checkpoint import CheckpointStore
from velaris.control.service import ControlService
from velaris.control.testing import FINAL, FakeRunner, FakeSink, env, step
from velaris.core.access import Caller
from velaris.intel.web_fetch import Fetcher

pytestmark = pytest.mark.browser
U1 = Caller("u1", "acme")
BOSS = Caller("boss", "acme", frozenset({"flow_approver"}))
FORM = "https://app.test/new"

PAGE = """<html><body><h1>New hire</h1><form method="post" action="/save">
<label for="n">Full name</label><input id="n" name="n" type="text">
<label for="e">Email</label><input id="e" name="e" type="text">
<button type="submit">Submit</button></form></body></html>"""


class App:
    def __init__(self, corrupt: bool = False) -> None:
        self.records, self.corrupt, self.posts, self.cross_site_hits = [], corrupt, [], []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/new":
            return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
        if request.method == "GET" and path == "/records":
            return httpx.Response(200, json=self.records)
        if request.method == "POST" and path == "/save":
            form = dict(urllib.parse.parse_qsl(request.content.decode()))
            self.posts.append(form)
            name, email = form.get("n", ""), form.get("e", "")
            self.records.append({"Full name": name.upper() if self.corrupt else name, "Email": email})     # a false success when corrupt
            return httpx.Response(303, headers={"location": "https://app.test/done"})
        if path == "/done":
            return httpx.Response(200, text="<html><body>Saved. Thank you!</body></html>", headers={"content-type": "text/html"})
        return httpx.Response(404, text="no")


def real_env(tmp_path, monkeypatch, app, *replies):
    e = env(tmp_path, monkeypatch, *replies)
    fetcher = Fetcher(transport=httpx.MockTransport(app.handle), resolver=lambda host: ["93.184.216.34"], min_gap_s=0, obey_robots=False)
    drivers = []

    def make():
        d = PlaywrightDriver(fetcher=fetcher, post_hosts=["app.test"], readback_url="https://app.test/records")
        drivers.append(d)
        return d
    e.svc.driver_factory = make
    return e, drivers


def run_or_skip(fn):
    try:
        return fn()
    except Exception as ex:
        if type(ex).__name__ in ("Refused", "Error") and ("playwright" in str(ex).lower() or "executable" in str(ex).lower()):
            pytest.skip(f"no usable Playwright/Chromium here: {str(ex)[:120]}")
        raise


PARAMS = {"url": FORM, "fields": {"Full name": "Asha Rao", "Email": "asha@acme.test"}, "submit": True,
          "readback_url": "https://app.test/records"}
STEPS = [step("navigate", "about:blank", to=FORM), step("fill", "Full name", "Asha Rao"), step("fill", "Email", "asha@acme.test"),
         step("submit", "Submit"), FINAL]


def test_navigate_fill_submit_a_real_post_and_the_read_back_confirms_it(tmp_path, monkeypatch):
    app = App()
    e, drivers = real_env(tmp_path, monkeypatch, app, *STEPS)
    try:
        r = run_or_skip(lambda: e.svc.start(U1, "browser.fill_form", PARAMS))
        assert r["status"] == "waiting_approval" and app.posts == []                       # nothing is posted before a person approves
        done = e.svc.decide(BOSS, r["task_id"], r["pending"]["call_hash"], True, "ok")
        assert app.posts == [{"n": "Asha Rao", "e": "asha@acme.test"}]                     # a real form POST reached the app, once
        assert done["status"] == "succeeded" and done["verification"]["ok"] is True
        assert app.records == [{"Full name": "Asha Rao", "Email": "asha@acme.test"}]
    finally:
        [d.close() for d in drivers]


def test_a_save_that_stores_the_wrong_value_is_a_failed_verification_not_a_success(tmp_path, monkeypatch):
    app = App(corrupt=True)
    e, drivers = real_env(tmp_path, monkeypatch, app, *STEPS)
    try:
        r = run_or_skip(lambda: e.svc.start(U1, "browser.fill_form", PARAMS))
        done = e.svc.decide(BOSS, r["task_id"], r["pending"]["call_hash"], True, "ok")
        assert app.posts and done["claim"].startswith("All done")                           # the page and the model both say success
        assert done["status"] == "failed_verification" and "Full name" in done["verification"]["checks"][0]["detail"]
    finally:
        [d.close() for d in drivers]


def test_a_cross_site_form_cannot_post_into_an_allowed_host(tmp_path, monkeypatch):
    """The page that submits must be on the allow-list too, and a driver without post_hosts refuses every POST."""
    from velaris.intel import web

    class Req:
        def __init__(self, url, origin):
            self.url, self.method, self.headers, self.post_data_buffer = url, "POST", {"origin": origin, "content-type": "application/x-www-form-urlencoded"}, b"a=b"

    class Route:
        def __init__(self, request):
            self.request, self.out = request, None

        def fulfill(self, **kw):
            self.out = ("fulfilled", kw["status"])

        def abort(self):
            self.out = ("aborted",)
    app = App()
    f = Fetcher(transport=httpx.MockTransport(app.handle), resolver=lambda host: ["93.184.216.34"], min_gap_s=0, obey_robots=False)
    for url, origin, hosts, expect in [("https://app.test/save", "https://evil.test", ["app.test"], "aborted"),
                                       ("https://app.test/save", "https://app.test", [], "aborted"),
                                       ("https://other.test/save", "https://app.test", ["app.test"], "aborted"),
                                       ("https://app.test/save", "https://app.test", ["app.test"], "fulfilled")]:
        route = Route(Req(url, origin))
        web._serve_browser_request(route, f, [10], hosts)
        assert route.out[0] == expect, (url, origin, hosts)
    assert len(app.posts) == 1
