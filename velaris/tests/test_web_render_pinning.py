"""The headless browser never resolves or connects by itself: every request it makes is
answered through the pinned fetcher, so a name that is public when checked and private
afterwards (DNS rebinding) is refused. The first tests use a fake route; the last one
drives a real Chromium, offline, and is skipped when no browser is installed."""
import socket
import threading
import types

import httpx
import pytest

from velaris.intel import trace, web
from velaris.intel.web_fetch import Fetcher

PUBLIC, PRIVATE = "93.184.216.34", "10.0.0.5"


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


class Route:
    """What Playwright hands the handler. It has no continue_(): handing a request back to
    the browser's own network stack would be an AttributeError here."""

    def __init__(self, url, method="GET"):
        self.request = types.SimpleNamespace(url=url, method=method)
        self.outcome = None

    def abort(self):
        self.outcome = ("abort",)

    def fulfill(self, status, body, headers):
        self.outcome = ("fulfill", status, body, headers)


def make(site, resolver):
    seen = []

    def transport(request):
        seen.append(request.url.host)
        return site(request)

    return Fetcher(transport=httpx.MockTransport(transport), resolver=resolver, min_gap_s=0,
                   cache_ttl_s=0, obey_robots=False), seen


def flip(host_answers):
    """Per host: the list of answers to give in turn (the last one repeats)."""
    calls = {}

    def resolver(host):
        n = calls[host] = calls.get(host, 0) + 1
        replies = host_answers.get(host) or [host]            # an address literal resolves to itself
        return [replies[min(n, len(replies)) - 1]]
    return resolver


def page(text="<p>ok</p>", **headers):
    return lambda request: httpx.Response(200, headers={"content-type": "text/html", **headers}, text=text)


def test_public_then_private_name_is_refused_and_never_handed_to_the_browser():
    f, connected = make(page(), flip({"rebind.test": [PUBLIC, PRIVATE]}))
    budget = [10]
    first, second = Route("http://rebind.test/a"), Route("http://rebind.test/b")
    web._serve_browser_request(first, f, budget)
    web._serve_browser_request(second, f, budget)
    assert first.outcome[:3] == ("fulfill", 200, b"<p>ok</p>")
    assert second.outcome == ("abort",)                       # second lookup said private: refused
    assert connected == [PUBLIC]                              # the only address ever connected to
    blocked = [e["payload"] for e in trace.entries() if e["action"] == "render.blocked_request"]
    assert blocked == [{"host": "rebind.test", "reason": "blocked_address"}]


def test_each_request_connects_to_the_address_that_was_checked_for_it():
    f, connected = make(page(), flip({"cdn.test": [PUBLIC, "93.184.216.99"]}))
    for _ in range(2):
        web._serve_browser_request(Route("https://cdn.test/app.js"), f, [10])
    assert connected == [PUBLIC, "93.184.216.99"]            # never the name, always a checked address


def test_redirect_to_internal_address_post_and_request_flood_are_refused():
    def site(request):
        if request.url.path == "/hop":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, text="x")
    f, connected = make(site, lambda host: [host if host[0].isdigit() else PUBLIC])
    hop, post, literal = Route("http://a.test/hop"), Route("http://a.test/x", "POST"), Route("http://127.0.0.1:8080/")
    budget = [3]
    for r in (hop, post, literal):
        web._serve_browser_request(r, f, budget)
    assert [r.outcome for r in (hop, post, literal)] == [("abort",)] * 3
    assert connected == [PUBLIC]                              # only the first hop, to the public site
    spent, extra = Route("http://a.test/1"), Route("http://a.test/2")
    web._serve_browser_request(spent, f, budget)              # budget: 3 - hop - literal = 1 left
    web._serve_browser_request(extra, f, budget)
    assert spent.outcome[0] == "fulfill" and extra.outcome == ("abort",)


def test_cookies_and_encoding_headers_do_not_reach_the_browser():
    f, _ = make(page(**{"set-cookie": "s=1", "access-control-allow-origin": "*"}), lambda host: [PUBLIC])
    route = Route("http://a.test/")
    web._serve_browser_request(route, f, [5])
    headers = {k.lower() for k in route.outcome[3]}
    assert "access-control-allow-origin" in headers and "content-type" in headers
    assert not headers & {"set-cookie", "content-length", "content-encoding"}


def test_browser_is_launched_without_dns_and_with_a_dead_proxy():
    args = web.browser_args(4321)
    assert "--host-resolver-rules=MAP * ~NOTFOUND" in args
    assert "--proxy-server=http://127.0.0.1:4321" in args and "--proxy-bypass-list=<-loopback>" in args


def test_real_browser_cannot_reach_a_rebinding_name_or_localhost():
    pytest.importorskip("playwright.sync_api")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    listener.settimeout(0.2)
    port = listener.getsockname()[1]
    reached = []
    stop = threading.Event()

    def accept():
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except OSError:
                continue
            reached.append(conn.recv(200))
            conn.close()

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    html = f"""<html><body><p id=out>loading</p><script>
      (async () => {{
        const out = [];
        for (const url of ['http://rebind.test/data', 'http://rebind.test/data', 'http://127.0.0.1:{port}/x']) {{
          try {{ out.push(await (await fetch(url)).text()); }} catch (e) {{ out.push('REFUSED'); }}
        }}
        const w = new Worker('/worker.js');
        w.onmessage = (m) => {{ out.push('socket-' + m.data); document.getElementById('out').textContent = out.join('|'); }};
      }})();
    </script></body></html>"""
    worker = (f"try {{ const s = new WebSocket('ws://127.0.0.1:{port}/'); s.onopen = () => postMessage('open');"
              " s.onerror = () => postMessage('failed'); } catch (e) { postMessage('failed'); }")

    def site(request):
        if request.url.path == "/worker.js":
            return httpx.Response(200, headers={"content-type": "text/javascript"}, text=worker)
        if request.headers["host"] == "rebind.test":
            return httpx.Response(200, headers={"access-control-allow-origin": "*"}, text="PUBLIC-DATA")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=html)

    f, connected = make(site, flip({"page.test": [PUBLIC], "rebind.test": [PUBLIC, PRIVATE]}))
    try:
        rendered = web._render_with_browser("http://page.test/", f)
        if rendered is None:
            failures = [e["payload"] for e in trace.entries() if e["action"] == "render.failed"]
            pytest.skip(f"no usable Chromium on this machine: {failures}")
        stop.wait(0.5)                                         # time for a stray connection to arrive
    finally:
        stop.set()
        thread.join()
        listener.close()
    assert "PUBLIC-DATA|REFUSED|REFUSED|socket-failed" in rendered
    assert reached == []                                       # nothing from the browser reached localhost
    assert set(connected) == {PUBLIC}                          # and Python only ever connected to public
