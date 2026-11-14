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
