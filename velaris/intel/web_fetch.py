"""Safe, polite HTTP fetching for the web tools.

Every fetch goes through the same gates, in this order:
  1. scheme and address check   only http/https; the host must resolve to public
                                addresses (no loopback, private, link-local or
                                cloud-metadata ranges). The connection is then made
                                to one of the addresses that were checked, not to
                                the name, so a DNS answer that changes afterwards
                                has no effect. Redirects are followed by hand so
                                each hop is resolved, checked and pinned again.
  2. robots.txt                 fetched once per host and cached; disallowed
                                paths are not fetched.
  3. per-host rate limit        a minimum gap between requests to one host.
  4. size and type limits       the body is read in a stream and cut off at a cap.
  5. disk cache                 keyed by URL, with a time-to-live.

The server process must never be usable to reach internal services, so gate 1
is not optional and has no override.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import threading
import time
from dataclasses import dataclass
from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Callable, Dict, List, Optional, Tuple
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx

from velaris.intel import trace
from velaris.intel.paths import data_dir

USER_AGENT = "VelarisBot/1.0 (+company operations assistant; respects robots.txt)"
MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT_S = 20.0
MIN_GAP_S = 1.0          # between two requests to the same host
CACHE_TTL_S = 24 * 3600
TEXT_TYPES = ("text/", "application/xhtml", "application/xml", "application/json", "application/rss",
              "application/atom")


class FetchError(RuntimeError):
    """A fetch was refused or failed. `reason` is a short machine-readable code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass
class Fetched:
    url: str            # the URL asked for
    final_url: str      # after redirects
    status: int
    content_type: str
    text: str
    from_cache: bool = False


Resolver = Callable[[str], list]


def _resolve(host: str) -> list:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def check_public(url: str, resolver: Resolver = _resolve) -> List[str]:
    """Raise FetchError unless the URL is http(s) and its host resolves only to public addresses.

    Returns the addresses that were checked. A caller that goes on to connect must connect to
    one of these (see `pinned`), never resolve the name a second time.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("blocked_scheme", parts.scheme or "none")
    try:
        addresses = resolver(parts.hostname)
    except OSError as e:
        raise FetchError("dns_failed", parts.hostname) from e
    if not addresses:
        raise FetchError("dns_failed", parts.hostname)
    for addr in addresses:
        ip = ipaddress.ip_address(addr.split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not ip.is_global:      # private, loopback, link-local (incl. 169.254.169.254), reserved, multicast
            raise FetchError("blocked_address", f"{parts.hostname} resolves to a non-public address")
    return list(dict.fromkeys(addresses))


def pinned(url: str, address: str) -> Tuple[httpx.URL, Dict[str, str], Dict[str, str]]:
    """The same request aimed at one already-checked address: (url, headers, extensions).

    The URL's host becomes the address, so nothing between here and the socket looks the name
    up again. The Host header keeps the original name, and for https so does the TLS server
    name, which is what both SNI and the certificate check use.
    """
    original = httpx.URL(url)
    extensions = {"sni_hostname": original.raw_host.decode("ascii")} if original.scheme == "https" else {}
    return original.copy_with(host=address), {"Host": original.netloc.decode("ascii")}, extensions


class Fetcher:
    """One instance per process is enough; it holds the robots cache and rate-limit clocks."""

    def __init__(self, *, transport: Optional[httpx.BaseTransport] = None, resolver: Resolver = _resolve,
                 min_gap_s: float = MIN_GAP_S, cache_ttl_s: float = CACHE_TTL_S, obey_robots: bool = True) -> None:
        # Requests are addressed by IP (see `pinned`), so the client must keep nothing that it
        # files under the URL's host: two sites on one address would otherwise share a kept-alive
        # TLS connection and each other's cookies. No keep-alive, and a cookie jar that accepts none.
        self._client = httpx.Client(transport=transport, follow_redirects=False, timeout=TIMEOUT_S,
                                    limits=httpx.Limits(max_keepalive_connections=0),
                                    cookies=CookieJar(DefaultCookiePolicy(allowed_domains=[])),
                                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
        self._resolver = resolver
        self._min_gap = min_gap_s
        self._ttl = cache_ttl_s
        self._obey_robots = obey_robots
        self._robots: Dict[str, Optional[robotparser.RobotFileParser]] = {}
        self._last_hit: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._cache_dir = data_dir() / "web_cache"
        self._cache_dir.mkdir(exist_ok=True)

    # ── gates ────────────────────────────────────────────────────────────────
    def _wait_turn(self, host: str) -> None:
        with self._lock:
            wait = self._last_hit.get(host, 0.0) + self._min_gap - time.monotonic()
            self._last_hit[host] = time.monotonic() + max(wait, 0.0)
        if wait > 0:
            time.sleep(wait)

    def _raw_get(self, url: str, polite: bool = True) -> httpx.Response:
        """One request, no redirects, body capped at MAX_BYTES.

        The host is resolved once, here; every address in the answer is checked, and the
        connection goes to one of those addresses. `response.url` therefore holds the address.
        """
        addresses = check_public(url, self._resolver)
        if polite:
            self._wait_turn(urlsplit(url).hostname or "")
        unreachable: Optional[httpx.HTTPError] = None
        for address in addresses:
            target, headers, extensions = pinned(url, address)
            try:
                with self._client.stream("GET", target, headers=headers, extensions=extensions) as r:
                    body = bytearray()
                    for part in r.iter_bytes():
                        body.extend(part)
                        if len(body) > MAX_BYTES:
                            break
                    r._content = bytes(body[:MAX_BYTES])  # noqa: SLF001  keep the capped body on the response
                    return r
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                unreachable = e          # e.g. an IPv6 address on an IPv4-only machine: try the next checked one
            except httpx.HTTPError as e:
                raise FetchError("network", type(e).__name__) from e
        raise FetchError("network", type(unreachable).__name__) from unreachable

    def get_pinned(self, url: str) -> Tuple[httpx.Response, str]:
        """GET for the headless browser: (response, final URL), redirects followed.

        The browser has no network access of its own (see web._render_with_browser); every
        request it makes is answered from here, so each one is resolved once, checked, and
        connected to the checked address exactly like a normal fetch. No robots check (the
        page itself already passed it; these are its scripts, styles and data) and no
        per-host pause (a page loads its parts together).
        """
        return self._get_following(url, polite=False)

    def _get_following(self, url: str, polite: bool = True) -> Tuple[httpx.Response, str]:
        """(response, the URL it finally came from). Every hop goes through _raw_get."""
        for _ in range(MAX_REDIRECTS + 1):
            r = self._raw_get(url, polite)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])      # resolved, checked and pinned on the next loop
                continue
            return r, url
        raise FetchError("too_many_redirects", url)

    def allowed_by_robots(self, url: str) -> bool:
        if not self._obey_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: Optional[robotparser.RobotFileParser] = robotparser.RobotFileParser()
            try:
                r, _ = self._get_following(origin + "/robots.txt")
                if r.status_code == 200:
                    parser.parse(r.text.splitlines())
                elif r.status_code in (401, 403):
                    parser.parse(["User-agent: *", "Disallow: /"])     # the site says keep out
                else:
                    parser = None                                      # no robots file: everything allowed
            except FetchError:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)

    def sitemaps(self, origin: str) -> list:
        self.allowed_by_robots(origin + "/")
        parser = self._robots.get(origin)
        return list(parser.site_maps() or []) if parser else []

    # ── cache ────────────────────────────────────────────────────────────────
    def _cache_file(self, url: str):
        return self._cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def _cache_get(self, url: str) -> Optional[Fetched]:
        f = self._cache_file(url)
        if f.exists() and time.time() - f.stat().st_mtime < self._ttl:
            return Fetched(**json.loads(f.read_text()), from_cache=True)
        return None

    # ── public ───────────────────────────────────────────────────────────────
    def fetch(self, url: str, *, use_cache: bool = True, is_api: bool = False) -> Fetched:
        """Fetch one text resource. Raises FetchError with a reason code when refused or failed.

        `is_api=True` is for a documented public API that is meant to be called by
        programs: robots.txt governs crawling of pages, not API use, so that gate is
        skipped. The address check, rate limit and size cap still apply.
        """
        if use_cache and (hit := self._cache_get(url)):
            return hit
        check_public(url, self._resolver)
        target = url
        if is_api:
            # API URLs can carry a key in the path or query: record the host only.
            parts = urlsplit(target)  # hostname, not netloc: netloc can hold user:password@
            url = f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "")
        if not is_api and not self.allowed_by_robots(url):
            trace.append("web", "fetch.refused", {"url": url, "reason": "robots"})
            raise FetchError("robots_disallowed", url)
        try:
            r, final_url = self._get_following(target)
        except FetchError as e:
            trace.append("web", "fetch.refused", {"url": url, "reason": e.reason})
            if is_api:
                raise FetchError(e.reason, url) from None  # the original detail can quote the full URL
            raise
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if r.status_code >= 400:
            trace.append("web", "fetch.failed", {"url": url, "status": r.status_code})
            raise FetchError("http_status", str(r.status_code))
        if ctype and not ctype.startswith(TEXT_TYPES):
            raise FetchError("not_text", ctype)
        out = Fetched(url=target, final_url=str(httpx.URL(final_url)), status=r.status_code, content_type=ctype, text=r.text)
        if not is_api:
            self._cache_file(target).write_text(json.dumps(
                {"url": out.url, "final_url": out.final_url, "status": out.status,
                 "content_type": out.content_type, "text": out.text}))
        trace.append("web", "fetch", {"url": url, "final_url": url if is_api else out.final_url,
                                       "status": out.status, "bytes": len(out.text)})
        return out


def demo() -> None:
    public = lambda host: ["93.184.216.34"]                       # noqa: E731
    for bad in ("http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/",
                "file:///etc/passwd", "ftp://example.com/", "http://[::1]/"):
        try:
            check_public(bad)
            raise AssertionError(f"{bad} was allowed")
        except FetchError:
            pass
    try:                                                           # public name, private address (DNS rebinding)
        check_public("http://intranet.example.com/", lambda h: ["192.168.1.10"])
        raise AssertionError("rebinding allowed")
    except FetchError as e:
        assert e.reason == "blocked_address"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\nSitemap: https://site.test/sitemap.xml")
        if path == "/hop":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/secret"})
        if path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>hello</p>")

    def resolver(host: str) -> list:
        return ["169.254.169.254"] if host == "169.254.169.254" else ["93.184.216.34"]

    f = Fetcher(transport=httpx.MockTransport(handler), resolver=resolver, min_gap_s=0, cache_ttl_s=0)
    assert f.fetch("https://site.test/page").text == "<p>hello</p>"
    for url, reason in (("https://site.test/private/x", "robots_disallowed"),
                        ("https://site.test/hop", "blocked_address"),      # redirect into metadata range
                        ("https://site.test/pdf", "not_text")):
        try:
            f.fetch(url)
            raise AssertionError(f"{url} was fetched")
        except FetchError as e:
            assert e.reason == reason, (url, e.reason)
    assert f.sitemaps("https://site.test") == ["https://site.test/sitemap.xml"]
    assert public("x")
    print("web_fetch ok")


if __name__ == "__main__":
    demo()
