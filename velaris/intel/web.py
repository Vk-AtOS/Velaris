"""Web tools: search, scrape, map, crawl and structured extraction.

  search(query)        results from public search APIs, or a self-hosted
                       SearXNG if SEARXNG_URL is set
  scrape(url)          one page as clean markdown, with metadata and links
  map_site(url)        the URLs of a site, from its sitemaps, else from links
  crawl(url)           breadth-first over one site, de-duplicated by URL and content
  extract(page, ...)   named fields pulled out by a model, each one checked
                       against the page text so invented values are dropped

Every page is screened by the guard before it is returned; a page that looks
like an attack on the model is returned with its text withheld.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote_plus, urlsplit

from velaris.intel import guard, trace
from velaris.intel.llm import LLM, LLMError, extract_json
from velaris.intel.web_fetch import Fetcher, FetchError
from velaris.intel.web_markdown import clean_url, html_to_markdown

logger = logging.getLogger("velaris.intel.web")

_fetcher: Optional[Fetcher] = None


def fetcher() -> Fetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = Fetcher()
    return _fetcher


@dataclass
class Page:
    url: str
    final_url: str = ""
    title: str = ""
    markdown: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    links: List[Dict[str, str]] = field(default_factory=list)
    risk: str = "none"               # guard level for the page text
    risk_findings: List[Dict[str, str]] = field(default_factory=list)
    needs_js: bool = False
    from_cache: bool = False
    error: str = ""                  # reason code when the page could not be read
    fetched_at: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.error

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


MAX_RENDER_REQUESTS = 200       # per page: main document plus its scripts, styles, data
_DROP_HEADERS = {"content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive",
                 "set-cookie", "set-cookie2", "strict-transport-security", "alt-svc"}


def browser_args(dead_port: int) -> List[str]:
    """Chromium flags that leave the browser with no way to reach the network by itself.

    It cannot resolve names, and every connection it opens on its own initiative (including
    to localhost, and including WebSocket or WebRTC traffic that request routing never sees)
    is sent to a proxy address where nothing listens.
    """
    return ["--host-resolver-rules=MAP * ~NOTFOUND",
            f"--proxy-server=http://127.0.0.1:{dead_port}",
            "--proxy-bypass-list=<-loopback>",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]


def _serve_browser_request(route: Any, f: Fetcher, budget: List[int]) -> None:
    """Answer one browser request (navigation, redirect, script, image, XHR) from this process.

    The request is never handed back to the browser's own network stack. `Fetcher.get_pinned`
    resolves the host once, checks every address, and connects to a checked address, so a name
    that answers with a public address when checked and a private one afterwards (DNS
    rebinding) never gets a second lookup: each new request for it is resolved and checked
    again, and is refused the moment the answer is not public.
    """
    request = route.request
    host = urlsplit(request.url).hostname or ""
    refused = ""
    if request.method != "GET":
        refused = "method_not_allowed"          # rendering reads pages; it does not submit anything
    elif budget[0] <= 0:
        refused = "too_many_requests"
    else:
        budget[0] -= 1
        try:
            r, _ = f.get_pinned(request.url)
        except FetchError as e:
            refused = e.reason
        except Exception as e:      # anything unexpected is a refusal too (recorded below), never a pass-through
            refused = f"error_{type(e).__name__}"
    if refused:
        trace.append("web", "render.blocked_request", {"host": host, "reason": refused})
        route.abort()
        return
    route.fulfill(status=r.status_code, body=r.content,
                  headers={k: v for k, v in r.headers.items() if k.lower() not in _DROP_HEADERS})


def _render_with_browser(url: str, f: Fetcher) -> Optional[str]:
    """Rendered HTML for pages built in the browser. None if no browser is installed.

    Limits: GET only, no cookies, at most MAX_RENDER_REQUESTS requests and the fetcher's size
    cap per response, so a page that needs a login or posts data renders partly or not at all.
    """
    try:
        from playwright.sync_api import sync_playwright   # optional dependency, imported only when needed
    except ImportError:
        return None
    # A bound socket that never listens: connections to it are refused, and nobody else can
    # take the port while the browser runs. It is the "proxy" in browser_args.
    with socket.socket() as nowhere:
        nowhere.bind(("127.0.0.1", 0))
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(args=browser_args(nowhere.getsockname()[1]))
                try:
                    # Service workers fetch outside request routing, so they are blocked; the
                    # page-level socket APIs are removed as well, though with the flags above
                    # neither could reach anything.
                    ctx = browser.new_context(service_workers="block")
                    ctx.add_init_script("for (const k of ['WebSocket', 'RTCPeerConnection', "
                                        "'webkitRTCPeerConnection', 'WebTransport']) delete window[k];")
                    budget = [MAX_RENDER_REQUESTS]
                    ctx.route("**/*", lambda route: _serve_browser_request(route, f, budget))
                    page = ctx.new_page()
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    return page.content()
                finally:
                    browser.close()
        except Exception as e:  # the browser is best-effort; the caller keeps the static result
            trace.append("web", "render.failed", {"url": url, "error": type(e).__name__})
            return None


def scrape(url: str, *, use_cache: bool = True, render_js: bool = True, f: Optional[Fetcher] = None) -> Page:
    """One page as markdown. Never raises for a bad page: check `page.ok` and `page.error`."""
    f = f or fetcher()
    try:
        got = f.fetch(url, use_cache=use_cache)
    except FetchError as e:
        return Page(url=url, error=e.reason, fetched_at=time.time())
    try:
        out = html_to_markdown(got.text, got.final_url)
        if out["needs_js"] and render_js:
            rendered = _render_with_browser(got.final_url, f)
            if rendered:
                out = html_to_markdown(rendered, got.final_url)
    except (RecursionError, ValueError, MemoryError) as e:      # hostile markup must not escape a function that never raises
        logger.warning("could not convert %s: %s", url, type(e).__name__)
        return Page(url=url, final_url=got.final_url, error="unparseable_page", fetched_at=time.time())
    scan = guard.scan(str(out["markdown"]), source=got.final_url)
    page = Page(url=url, final_url=got.final_url, title=str(out["metadata"]["title"]),          # type: ignore[index]
                markdown=str(out["markdown"]), metadata=dict(out["metadata"]),                  # type: ignore[arg-type]
                links=list(out["links"]), risk=scan.level, risk_findings=scan.findings,        # type: ignore[arg-type]
                needs_js=bool(out["needs_js"]), from_cache=got.from_cache, fetched_at=time.time())
    if scan.blocked:      # keep the evidence, withhold the text from any model
        page.markdown, page.error = "", "blocked_by_guard"
    trace.append("web", "scrape", {"url": url, "chars": len(page.markdown), "risk": page.risk,
                                    "sha256": hashlib.sha256(page.markdown.encode()).hexdigest()})
    return page


def _same_site(a: str, b: str) -> bool:
    strip = lambda h: (h or "").lower().removeprefix("www.")      # noqa: E731
    return strip(urlsplit(a).hostname) == strip(urlsplit(b).hostname)


MAX_SITEMAP_CHARS = 5_000_000


def _locs(xml: str, cap: int) -> List[str]:
    """The <loc> values of a sitemap in ONE linear pass (str.find, no backtracking), at most `cap` of them.

    Sitemaps come from untrusted sites, so they are not given to an XML parser (no entity expansion, no
    external entities) and not to a lazy regex (quadratic on unclosed tags). Only the first 5 MB is read; an
    unclosed <loc> ends the scan; a value that contains another tag is skipped.
    """
    xml, out, pos = xml[:MAX_SITEMAP_CHARS], [], 0
    while len(out) < cap:
        start = xml.find("<loc>", pos)
        if start < 0:
            break
        start += 5
        end = xml.find("</loc>", start)
        if end < 0:
            break
        pos = end + 6
        v = xml[start:end].strip()
        if v.startswith("<![CDATA["):
            v = v[9:].removesuffix("]]>").strip()
        if v and "<" not in v:
            out.append(v)
    return out


def _sitemap_urls(f: Fetcher, sitemap_url: str, limit: int, depth: int = 0) -> List[str]:
    if depth > 2:
        return []
    try:
        xml = f.fetch(sitemap_url).text
    except FetchError:
        return []
    locs = _locs(xml, max(limit, 0) if "<sitemapindex" not in xml else 50)
    if "<sitemapindex" in xml:
        urls: List[str] = []
        for child in locs:
            urls.extend(_sitemap_urls(f, child, limit - len(urls), depth + 1))
            if len(urls) >= limit:
                break
        return urls
    return locs[:limit]


def map_site(url: str, *, limit: int = 200, f: Optional[Fetcher] = None) -> List[str]:
    """URLs that belong to the site: sitemaps first, then links on the page itself."""
    f = f or fetcher()
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    found: List[str] = []
    for sm in (f.sitemaps(origin) or [origin + "/sitemap.xml"]):
        found.extend(_sitemap_urls(f, sm, limit - len(found)))
        if len(found) >= limit:
            break
    if len(found) < limit:
        found.extend(l["url"] for l in scrape(url, f=f).links)
    seen, out = set(), []
    for u in found:
        u = clean_url(u, origin) or ""
        if u and u not in seen and _same_site(u, url):
            seen.add(u)
            out.append(u)
    trace.append("web", "map", {"url": url, "count": len(out[:limit])})
    return out[:limit]


def crawl(url: str, *, limit: int = 20, max_depth: int = 2, include: Optional[str] = None,
          exclude: Optional[str] = None, f: Optional[Fetcher] = None) -> List[Page]:
    """Breadth-first crawl of one site. Pages with identical text are returned once."""
    f = f or fetcher()
    inc, exc = (re.compile(p) if p else None for p in (include, exclude))
    start = clean_url(url, url) or url
    queue, seen_urls, seen_text, pages = deque([(start, 0)]), {start}, set(), []
    while queue and len(pages) < limit:
        current, depth = queue.popleft()
        page = scrape(current, f=f)
        if not page.ok:
            continue
        # ponytail: exact-text de-duplication; near-duplicates (same article, different
        # footer) still pass. Use shingle similarity if crawls show repeated pages.
        digest = hashlib.sha256(re.sub(r"\s+", " ", page.markdown).encode()).hexdigest()
        if digest in seen_text:
            continue
        seen_text.add(digest)
        pages.append(page)
        if depth >= max_depth:
            continue
        for link in page.links:
            u = link["url"]
            if u in seen_urls or not _same_site(u, start):
                continue
            if (inc and not inc.search(u)) or (exc and exc.search(u)):
                continue
            seen_urls.add(u)
            queue.append((u, depth + 1))
    trace.append("web", "crawl", {"url": url, "pages": len(pages), "visited": len(seen_urls)})
    return pages


def _provider_searxng(f: Fetcher, base: str, query: str, limit: int) -> List[Dict[str, str]]:
    data = json.loads(f.fetch(f"{base}/search?q={quote_plus(query)}&format=json", use_cache=False, is_api=True).text)
    return [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("content", "")}
            for r in data.get("results", [])][:limit]


def _provider_marginalia(f: Fetcher, query: str, limit: int) -> List[Dict[str, str]]:
    """Marginalia: an independent index with a free public API (shared key, rate-limited)."""
    key = os.environ.get("MARGINALIA_KEY", "public")
    data = json.loads(f.fetch(f"https://api.marginalia.nu/{key}/search/{quote_plus(query)}?count={limit}",
                              use_cache=False, is_api=True).text)
    return [{"url": r["url"], "title": r.get("title", ""), "snippet": r.get("description", "")}
            for r in data.get("results", [])][:limit]


def _provider_wikipedia(f: Fetcher, query: str, limit: int) -> List[Dict[str, str]]:
    data = json.loads(f.fetch("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
                              f"&srlimit={limit}&srsearch={quote_plus(query)}", use_cache=False, is_api=True).text)
    return [{"url": "https://en.wikipedia.org/wiki/" + quote_plus(r["title"].replace(" ", "_"), safe="_()"),
             "title": r["title"], "snippet": re.sub(r"<[^>]+>", "", r.get("snippet", ""))}
            for r in data.get("query", {}).get("search", [])][:limit]


def search(query: str, *, limit: int = 8, f: Optional[Fetcher] = None) -> List[Dict[str, str]]:
    """Web search through documented public APIs only; no search-result pages are scraped.

    With SEARXNG_URL set, a self-hosted SearXNG answers (best coverage, free).
    Otherwise Marginalia and Wikipedia are merged: independent and free, but far
    narrower than a commercial index, so expect gaps on recent or local topics.
    Titles and snippets are screened; a result that fails the guard is dropped.
    """
    f = f or fetcher()
    searx = os.environ.get("SEARXNG_URL", "").rstrip("/")
    providers = ([("searxng", lambda: _provider_searxng(f, searx, query, limit))] if searx else
                 [("marginalia", lambda: _provider_marginalia(f, query, limit)),
                  ("wikipedia", lambda: _provider_wikipedia(f, query, max(2, limit // 3)))])
    results: List[Dict[str, str]] = []
    used: List[str] = []
    for name, call in providers:
        try:
            got = call()
        except (FetchError, ValueError, KeyError) as e:
            trace.append("web", "search.provider_failed", {"provider": name, "error": str(e)[:120]})
            continue
        used.append(name)
        results.extend(r for r in got if r["url"] not in {x["url"] for x in results})
    safe = [r for r in results if not guard.scan(f"{r['title']} {r['snippet']}", source=r["url"]).blocked][:limit]
    trace.append("web", "search", {"query": query, "providers": used, "results": len(safe),
                                    "dropped": len(results[:limit]) - len(safe)})
    return safe


def _grounded(value: Any, source: str) -> bool:
    """True if a value can be found in the page: numbers by digits, text by its words."""
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        digits = re.sub(r"\D", "", str(value).rstrip("0").rstrip(".")) or "0"
        return digits in re.sub(r"[^\d]", "", source)
    if isinstance(value, list):
        return all(_grounded(v, source) for v in value)
    if isinstance(value, dict):
        return all(_grounded(v, source) for v in value.values())
    words = re.findall(r"[a-z0-9]+", str(value).lower())
    haystack = set(re.findall(r"[a-z0-9]+", source.lower()))
    return bool(words) and sum(w in haystack for w in words) / len(words) >= 0.8


def extract(page: Page, fields: Dict[str, str], *, llm: Optional[LLM] = None,
            model: Optional[str] = None) -> Dict[str, Any]:
    """Pull named fields out of a page with a model.

    `fields` maps a field name to a plain description. Returns
    {"data": {...}, "ungrounded": [...], "error": ""}. A value the page text does
    not support is set to None and listed in "ungrounded": the model may read
    the page, but it may not add to it.
    """
    if not page.ok or not page.markdown:
        return {"data": {k: None for k in fields}, "ungrounded": [], "error": page.error or "empty_page"}
    llm = llm or LLM()
    preamble, block = guard.wrap(page.markdown[:24000], label=f"the text of the web page {page.final_url}")
    spec = "\n".join(f'- "{k}": {v}' for k, v in fields.items())
    prompt = (f"{preamble}\n\n{block}\n\nFrom that page, return one JSON object with exactly these keys:\n{spec}\n\n"
              "Use null for anything the page does not state. Copy values as written; do not infer or compute. "
              "Reply with the JSON object only.")
    try:
        raw = extract_json(llm.complete(prompt, model=model, max_tokens=800, temperature=0.0,
                                        purpose="web.extract").text)
    except LLMError as e:
        return {"data": {k: None for k in fields}, "ungrounded": [], "error": str(e)}
    if not isinstance(raw, dict):
        return {"data": {k: None for k in fields}, "ungrounded": [], "error": "model did not return an object"}
    data, ungrounded = {}, []
    for k in fields:
        v = raw.get(k)
        if v is not None and not _grounded(v, page.markdown):
            ungrounded.append(k)
            v = None
        data[k] = v
    trace.append("web", "extract", {"url": page.final_url, "fields": list(fields), "ungrounded": ungrounded})
    return {"data": data, "ungrounded": ungrounded, "error": ""}


def scrape_many(urls: Iterable[str], *, f: Optional[Fetcher] = None) -> List[Page]:
    return [scrape(u, f=f) for u in urls]
