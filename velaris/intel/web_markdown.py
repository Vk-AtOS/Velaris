"""HTML to clean, model-ready markdown.

Pipeline (standard library only):
  1. parse     html.parser builds a small element tree; scripts, styles and
               other non-content tags are dropped while parsing.
  2. prune     navigation, footers, cookie banners, share bars and similar
               boilerplate are removed by tag, ARIA role and class/id name.
  3. select    the main content is <main>/<article> if one clearly dominates,
               otherwise the subtree with the best text score: long paragraphs
               and punctuation count for a node, link-heavy text counts against
               it, and each paragraph also credits its parent and grandparent.
  4. render    the chosen subtree becomes markdown: headings, paragraphs, nested
               lists, links (made absolute), images, code fences with language,
               block quotes and tables.

The same tree yields page metadata and the list of links.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas", "iframe", "object",
             "embed", "select", "button", "input", "textarea", "dialog"}
VOID_TAGS = {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "area", "base", "col", "track"}
BOILERPLATE_TAGS = {"nav", "footer", "aside", "form", "header"}
BOILERPLATE_ROLES = {"navigation", "banner", "contentinfo", "complementary", "search", "dialog", "alert"}
BOILERPLATE_NAME = re.compile(
    r"(^|[-_ ])(nav|navbar|menu|breadcrumbs?|footer|sidebar|side-bar|cookie|consent|gdpr|banner|popup|modal|"
    r"newsletter|subscribe|share|social|related|recommend|promo|advert|ads?|sponsor|comments?|disqus|"
    r"pagination|pager|toolbar|skip-link|widget|masthead)([-_ ]|$)", re.I)
CONTENT_NAME = re.compile(r"(^|[-_ ])(article|content|post|entry|main|body|story|text|markdown|prose|doc)([-_ ]|$)", re.I)
BLOCK_TAGS = {"p", "div", "section", "article", "main", "ul", "ol", "li", "table", "tr", "blockquote",
              "pre", "h1", "h2", "h3", "h4", "h5", "h6", "figure", "figcaption", "dl", "dt", "dd",
              "details", "summary", "header", "body", "html", "td", "th", "thead", "tbody"}
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_eid$|mc_cid$|ref$|ref_src$|igshid$|msclkid$|yclid$)", re.I)


@dataclass
class Node:
    tag: str
    attrs: Dict[str, str] = field(default_factory=dict)
    children: List["Node | str"] = field(default_factory=list)
    parent: Optional["Node"] = None
    score: float = 0.0
    depth: int = 0

    def text(self) -> str:
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def find_all(self, *tags: str) -> List["Node"]:
        out: List[Node] = []
        for c in self.children:
            if isinstance(c, Node):
                if c.tag in tags:
                    out.append(c)
                out.extend(c.find_all(*tags))
        return out


MAX_DEPTH = 100      # deeper nesting is flattened into its ancestor: a hostile page cannot overflow the recursive walkers


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("html")
        self.cur = self.root
        self.skip_depth = 0
        self.meta: Dict[str, str] = {}
        self._in_title = False
        self.flat = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"].strip())
            return
        if tag == "link" and "canonical" in a.get("rel", "").lower() and a.get("href"):
            self.meta.setdefault("canonical", a["href"])
            return
        if tag == "html" and a.get("lang"):
            self.meta.setdefault("lang", a["lang"])
        if tag == "title":
            self._in_title = True
        if self.skip_depth or tag in SKIP_TAGS:
            if tag not in VOID_TAGS:
                self.skip_depth += 1
            return
        if tag not in VOID_TAGS and (self.flat or self.cur.depth >= MAX_DEPTH):
            self.flat += 1
            return
        node = Node(tag, a, parent=self.cur, depth=self.cur.depth + 1)
        self.cur.children.append(node)
        if tag not in VOID_TAGS:
            self.cur = node

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if self.skip_depth:
            if tag not in VOID_TAGS:
                self.skip_depth -= 1
            return
        if self.flat and tag not in VOID_TAGS:
            self.flat -= 1
            return
        n: Optional[Node] = self.cur     # close the nearest open element with this tag
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.meta["title"] = (self.meta.get("title", "") + data).strip()
            return
        if not self.skip_depth and data:
            self.cur.children.append(data)


def parse(html: str) -> tuple[Node, Dict[str, str]]:
    b = _TreeBuilder()
    b.feed(html)
    b.close()
    return b.root, b.meta


def _is_boilerplate(n: Node) -> bool:
    if n.tag in BOILERPLATE_TAGS and not (n.tag == "header" and n.parent and n.parent.tag in ("article", "main")):
        return True
    if n.attrs.get("role", "").lower() in BOILERPLATE_ROLES or n.attrs.get("aria-hidden") == "true":
        return True
    if "hidden" in n.attrs or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", n.attrs.get("style", ""), re.I):
        return True
    name = f"{n.attrs.get('class', '')} {n.attrs.get('id', '')}"
    return bool(BOILERPLATE_NAME.search(name)) and not CONTENT_NAME.search(name) and n.tag not in ("body", "html", "main", "article")


def prune(n: Node) -> None:
    kept: List[Node | str] = []
    for c in n.children:
        if isinstance(c, Node):
            if _is_boilerplate(c):
                continue
            prune(c)
        kept.append(c)
    n.children = kept


def _link_density(n: Node) -> float:
    total = len(n.text().strip()) or 1
    return sum(len(a.text().strip()) for a in n.find_all("a")) / total


def select_main(root: Node) -> Node:
    """The subtree that holds the page's real content."""
    body = next(iter(root.find_all("body")), root)
    body_len = len(body.text().strip()) or 1
    for tag in ("main", "article"):
        found = [c for c in body.find_all(tag) if len(c.text().strip()) > 0.5 * body_len]
        if len(found) == 1:      # one element holds most of the text: trust the author
            return found[0]
    best, best_score = body, 0.0
    for p in body.find_all("p", "pre", "td", "li", "blockquote"):
        t = p.text().strip()
        if len(t) < 25:
            continue
        s = 1 + t.count(",") + t.count("，") + min(len(t) / 100, 3)
        for depth, anc in enumerate((p.parent, p.parent.parent if p.parent else None)):
            if anc is not None:
                anc.score += s / (depth + 1)
    for cand in body.find_all("div", "section", "article", "main", "td", "body"):
        if cand.score <= 0:
            continue
        s = cand.score * (1 - _link_density(cand))
        if CONTENT_NAME.search(f"{cand.attrs.get('class', '')} {cand.attrs.get('id', '')}"):
            s *= 1.25
        if s > best_score:
            best, best_score = cand, s
    # A winner holding very little of the page means the page has no dominant block
    # (an index or listing): keep the whole pruned body rather than a fragment.
    return best if len(best.text().strip()) >= 0.25 * body_len else body


def clean_url(href: str, base: str) -> Optional[str]:
    """Absolute http(s) URL without fragment or tracking parameters; None for anything else."""
    href = (href or "").strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return None
    parts = urlsplit(urljoin(base, href))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not TRACKING_PARAMS.match(k)])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", query, ""))


def _inline(n: Node | str, base: str) -> str:
    if isinstance(n, str):
        return re.sub(r"\s+", " ", n)
    inner = "".join(_inline(c, base) for c in n.children)
    t = n.tag
    if t in ("strong", "b") and inner.strip():
        return f"**{inner.strip()}**"
    if t in ("em", "i") and inner.strip():
        return f"*{inner.strip()}*"
    if t in ("code", "kbd", "samp") and inner.strip():
        return f"`{inner.strip()}`"
    if t == "a":
        url = clean_url(n.attrs.get("href", ""), base)
        label = inner.strip()
        return f"[{label}]({url})" if url and label else label
    if t == "img":
        url = clean_url(n.attrs.get("src") or n.attrs.get("data-src", ""), base)
        alt = n.attrs.get("alt", "").strip()
        return f"![{alt}]({url})" if url and alt else ""
    if t == "br":
        return "\n"
    return inner


def _table(n: Node, base: str) -> str:
    rows = [[re.sub(r"\s+", " ", _inline(c, base)).strip().replace("|", "\\|")
             for c in r.children if isinstance(c, Node) and c.tag in ("td", "th")]
            for r in n.find_all("tr")]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _block(n: Node | str, base: str, depth: int = 0) -> str:
    if isinstance(n, str):
        return re.sub(r"\s+", " ", n)
    t = n.tag
    if re.fullmatch(r"h[1-6]", t):
        text = re.sub(r"\s+", " ", _inline(n, base)).strip()
        return f"\n\n{'#' * int(t[1])} {text}\n\n" if text else ""
    if t == "pre":
        code = n.text().strip("\n")
        lang = re.search(r"(?:language|lang)-([\w+#-]+)", " ".join(
            c.attrs.get("class", "") for c in [n] + n.find_all("code")))
        return f"\n\n```{lang.group(1) if lang else ''}\n{code}\n```\n\n" if code.strip() else ""
    if t == "table":
        return f"\n\n{_table(n, base)}\n\n"
    if t in ("ul", "ol"):
        items = []
        for i, li in enumerate((c for c in n.children if isinstance(c, Node) and c.tag == "li"), start=1):
            body = "".join(_block(c, base, depth + 1) for c in li.children).strip()
            body = re.sub(r"\n{2,}", "\n", body)
            marker = f"{i}." if t == "ol" else "-"
            items.append("  " * depth + f"{marker} " + body.replace("\n", "\n" + "  " * (depth + 1)))
        return "\n\n" + "\n".join(items) + "\n\n" if items else ""
    if t == "blockquote":
        inner = "".join(_block(c, base, depth) for c in n.children).strip()
        return "\n\n" + "\n".join("> " + line for line in inner.splitlines()) + "\n\n" if inner else ""
    if t == "hr":
        return "\n\n---\n\n"
    if t in BLOCK_TAGS:
        inner = "".join(_block(c, base, depth) for c in n.children)
        return f"\n\n{inner}\n\n" if t != "li" else inner
    return _inline(n, base)


def render(n: Node, base: str) -> str:
    md = _block(n, base)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = "\n".join(line if line.startswith(("  ", "```", "|", ">")) else line.strip() for line in md.split("\n"))
    return md.strip()


def links(root: Node, base: str) -> List[Dict[str, str]]:
    seen, out = set(), []
    for a in root.find_all("a"):
        url = clean_url(a.attrs.get("href", ""), base)
        if url and url not in seen:
            seen.add(url)
            out.append({"url": url, "text": re.sub(r"\s+", " ", a.text()).strip()[:120]})
    return out


def html_to_markdown(html: str, base_url: str = "") -> Dict[str, object]:
    """Full conversion. Returns markdown, metadata, links (from the whole page) and counts."""
    root, meta = parse(html)
    all_links = links(root, base_url)
    script_count = html.lower().count("<script")
    prune(root)
    main = select_main(root)
    markdown = render(main, base_url)
    title = meta.get("og:title") or meta.get("title") or ""
    if title and not re.match(r"\s*# ", markdown):
        markdown = f"# {title.strip()}\n\n{markdown}"
    return {
        "markdown": markdown,
        "links": all_links,
        "metadata": {
            "title": title.strip(),
            "description": meta.get("og:description") or meta.get("description", ""),
            "canonical": clean_url(meta.get("canonical", ""), base_url) or "",
            "lang": meta.get("lang", ""),
            "published": meta.get("article:published_time") or meta.get("date", ""),
            "site_name": meta.get("og:site_name", ""),
        },
        # Little text from a script-heavy page means the content is rendered in the browser.
        "needs_js": len(main.text().strip()) < 200 and script_count >= 3,
    }


def chunk(markdown: str, max_chars: int = 2000) -> List[Dict[str, str]]:
    """Split on headings, keeping each chunk's heading trail so it stands on its own."""
    chunks: List[Dict[str, str]] = []
    trail: List[str] = []
    buf: List[str] = []
    size = 0         # running length of buf: re-summing it per line was quadratic on text with no blank lines

    def flush() -> None:
        nonlocal size
        size = 0
        text = "\n".join(buf).strip()
        if text:
            for i in range(0, len(text), max_chars):
                chunks.append({"heading": " > ".join(trail), "text": text[i:i + max_chars]})
        buf.clear()

    in_code = False
    for line in markdown.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"(#{1,6}) (.+)", line)
        if m:
            flush()
            level = len(m.group(1))
            trail[:] = trail[:level - 1] + [m.group(2).strip()]
            continue
        buf.append(line)
        size += len(line) + 1
        if size > max_chars and not in_code and not line.strip():
            flush()
    flush()
    return chunks


def demo() -> None:
    html = """<html lang="en"><head><title>Leave policy | Acme</title>
      <meta property="og:description" content="How leave works"><link rel="canonical" href="/hr/leave?utm_source=x"></head>
      <body><nav><a href="/">Home</a><a href="/about">About</a></nav>
      <div class="cookie-banner">We use cookies <a href="/c">ok</a></div>
      <div class="post-content"><h1>Leave policy</h1>
        <p>Employees get <strong>18 days</strong> of paid leave, accrued monthly, and may carry over up to 6 days.</p>
        <ul><li>Apply in the <a href="/portal?utm_campaign=y#top">portal</a></li><li>Manager approves<ul><li>within 2 days</li></ul></li></ul>
        <pre><code class="language-python">print("hi")</code></pre>
        <table><tr><th>Type</th><th>Days</th></tr><tr><td>Casual</td><td>12</td></tr></table>
        <script>alert(1)</script></div>
      <footer>© Acme <a href="/legal">Legal</a></footer></body></html>"""
    out = html_to_markdown(html, "https://acme.test/hr/leave")
    md = out["markdown"]
    assert "# Leave policy" in md and "**18 days**" in md, md
    assert "[portal](https://acme.test/portal)" in md and "  - within 2 days" in md, md
    assert '```python\nprint("hi")\n```' in md and "| Casual | 12 |" in md, md
    assert "cookies" not in md and "Legal" not in md and "alert" not in md and "Home" not in md, md
    assert out["metadata"]["canonical"] == "https://acme.test/hr/leave" and out["metadata"]["lang"] == "en"
    assert {l["url"] for l in out["links"]} >= {"https://acme.test/about", "https://acme.test/legal"}
    assert chunk(md, 80)[0]["heading"] == "Leave policy"
    print("web_markdown ok")


if __name__ == "__main__":
    demo()
