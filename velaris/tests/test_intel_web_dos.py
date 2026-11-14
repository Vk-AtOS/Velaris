"""KAN-167: hostile web input cannot stall or crash the service."""
import time

from velaris.intel import web
from velaris.intel.web_markdown import chunk, html_to_markdown


class _F:
    def __init__(self, text):
        self.text = text
        self.final_url = "https://x.test/"
        self.from_cache = False

    def fetch(self, url, use_cache=True):
        return self


def test_sitemap_with_unclosed_locs_is_linear():
    t = time.time()
    assert web._sitemap_urls(_F("<urlset>" + "<loc>https://x.test/a" * 20000), "https://x.test/s.xml", 100) == []
    assert time.time() - t < 1
    ok = web._sitemap_urls(_F("<loc>https://x.test/1</loc><loc><![CDATA[https://x.test/2]]></loc>"), "u", 10)
    assert ok == ["https://x.test/1", "https://x.test/2"]


def test_chunk_of_text_without_blank_lines_is_linear():
    t = time.time()
    assert chunk("\n".join("line %d" % i for i in range(60000)))
    assert time.time() - t < 2


def test_deeply_nested_html_does_not_raise():
    html = "<html><body>" + "<div>" * 5000 + "deep text" + "</div>" * 5000 + "</body></html>"
    assert "deep text" in html_to_markdown(html)["markdown"]
    assert web.scrape("https://x.test/", f=_F(html), render_js=False).error in (None, "")


def test_self_hosted_searxng_on_a_private_host_is_allowed_only_when_configured(monkeypatch):
    import pytest
    from velaris.intel.web_fetch import FetchError, check_public
    private = lambda h: ["10.0.0.5"]            # noqa: E731
    with pytest.raises(FetchError):
        check_public("http://search.corp/search", private)
    monkeypatch.setenv("SEARXNG_URL", "http://search.corp:8080")
    assert check_public("http://search.corp/search", private) == ["10.0.0.5"]
    with pytest.raises(FetchError):
        check_public("http://other.corp/", private)


def test_cache_is_atomic_corrupt_entry_is_refetched_and_expired_entries_are_swept(tmp_path):
    import os
    import httpx
    from velaris.intel.web_fetch import Fetcher
    f = Fetcher(transport=httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, text="<p>hi</p>")),
                resolver=lambda h: ["93.184.216.34"], min_gap_s=0, cache_ttl_s=3600, obey_robots=False)
    f.fetch("https://a.test/x")
    entry = f._cache_file("https://a.test/x")
    entry.write_text("{half")                                      # a torn / foreign file
    assert f.fetch("https://a.test/x").text == "<p>hi</p>"         # no JSONDecodeError
    old = f._cache_dir / "dead.json"
    old.write_text("{}")
    os.utime(old, (1, 1))
    f._sweep_cache()
    assert not old.exists() and entry.exists() and not list(f._cache_dir.glob(".*.tmp"))


def test_llm_malformed_replies_raise_llmerror(monkeypatch):
    import httpx
    import pytest
    from velaris.intel import llm
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "t")
    for body in (httpx.Response(200, text="<html>oops"), httpx.Response(200, json={"output": {}}), httpx.Response(200, json=[1])):
        monkeypatch.setattr(llm.httpx, "post", lambda *a, _b=body, **k: _b)
        with pytest.raises(llm.LLMError):
            llm.LLM().complete("hi", model="bedrock:m")
