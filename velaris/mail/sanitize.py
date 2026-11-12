"""HTML from outside, reduced to a strict allowlist. Standard library only.

Rules: only the tags in ALLOWED are kept, with only the attributes listed for them; scripts,
styles, frames, forms, objects and SVG are removed with their content; every style and event
attribute is dropped (so no CSS url(), no onerror); remote images are blocked (an image is kept
only when it points at a cid: part of the same message); links must be http, https or mailto and
get rel/target set and the real host shown next to the text, so "https://bank.example" text over an
evil.test target is visible. Anything the parser cannot cope with becomes plain escaped text.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urlsplit

ALLOWED = frozenset("p br div span b strong i em u s strike sub sup ul ol li blockquote pre code h1 h2 h3 h4 h5 h6 "
                    "table thead tbody tfoot tr td th hr a img".split())
ATTRS = {"a": ("href", "title"), "td": ("colspan", "rowspan"), "th": ("colspan", "rowspan"), "ol": ("start",),
         "img": ("src", "alt")}
DROP_WITH_CONTENT = frozenset("script style iframe object embed form svg math head title noscript template textarea "
                              "select button applet frame frameset video audio canvas option datalist".split())
VOID = frozenset("br hr img input link meta base area col source track wbr".split())
BLOCK = frozenset("p div br li tr h1 h2 h3 h4 h5 h6 blockquote pre hr table".split())
MAX_DEPTH = 40
_CTRL = re.compile(r"[\x00-\x20\x7f-\x9f​-‏  ﻿]")
_CID = re.compile(r"cid:[A-Za-z0-9._@%+=~-]{1,200}\Z")
_DIGITS = re.compile(r"\d{1,4}\Z")


@dataclass
class Sanitized:
    html: str
    blocked_images: int = 0
    hosts: List[str] = field(default_factory=list)      # hosts of the links kept
    truncated: bool = False


def safe_url(value: str) -> Optional[str]:
    """The URL if it is http(s) with a host, or mailto; else None. Control characters are removed first
    because browsers ignore them inside a scheme ("java\\tscript:")."""
    url = _CTRL.sub("", value or "")
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme == "mailto" and parts.path:
            return url[:2000]
        if scheme in ("http", "https") and parts.hostname:
            return url[:2000]
    except ValueError:
        return None
    return None


def display_host(url: str) -> str:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    try:
        return host.encode("idna").decode("ascii")       # show the punycode form of look-alike names
    except UnicodeError:
        return host


class _San(HTMLParser):
    def __init__(self, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self.stack: List[str] = []
        self.size, self.limit, self.truncated = 0, limit, False
        self.skip: Optional[str] = None
        self.skip_depth = 0
        self.blocked = 0
        self.hosts: List[str] = []
        self.anchor: Optional[List[str]] = None            # [host, text so far]

    def _emit(self, s: str) -> None:
        if self.size + len(s) > self.limit:
            self.truncated = True
            return
        self.size += len(s)
        self.out.append(s)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if self.skip:
            if tag == self.skip:
                self.skip_depth += 1
            return
        if tag in DROP_WITH_CONTENT:
            self.skip, self.skip_depth = tag, 1
            return
        a = {k: (v or "") for k, v in attrs}
        if tag == "img":
            src = _CTRL.sub("", a.get("src", ""))
            if _CID.match(src):
                self._emit(f'<img src="{html.escape(src)}" alt="{html.escape(a.get("alt", "")[:200])}">')
            else:
                self.blocked += 1
                self._emit(f"[image blocked{': ' + html.escape(a['alt'][:80]) if a.get('alt') else ''}]")
            return
        if tag not in ALLOWED or len(self.stack) >= MAX_DEPTH:
            return
        keep = []
        if tag == "a":
            url = safe_url(a.get("href", ""))
            if url is None:
                return                                   # a link we cannot make safe: keep the text only
            host = display_host(url) if not url.lower().startswith("mailto:") else ""
            keep.append(f'href="{html.escape(url)}" rel="noopener noreferrer nofollow" target="_blank"')
            if host:
                keep.append(f'data-host="{html.escape(host)}"')
                self.hosts.append(host)
            if a.get("title"):
                keep.append(f'title="{html.escape(a["title"][:200])}"')
            self.anchor = [host, ""]
        else:
            for name in ATTRS.get(tag, ()):
                if name in a and name != "src" and (name not in ("colspan", "rowspan", "start") or _DIGITS.match(a[name])):
                    keep.append(f'{name}="{html.escape(a[name][:200])}"')
        self._emit(f"<{tag}{' ' + ' '.join(keep) if keep else ''}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            if tag == self.skip:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip = None
            return
        if tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self._emit(f"</{top}>")
            if top == "a" and self.anchor is not None:
                host, text = self.anchor
                self.anchor = None
                if host and host not in text.lower():
                    self._emit(f'<span class="link-host"> ({html.escape(host)})</span>')
            if top == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.anchor is not None:
            self.anchor[1] += data
        self._emit(html.escape(data, quote=False))

    def close_all(self) -> None:
        while self.stack:
            self.handle_endtag(self.stack[-1])


def sanitize_html(raw: str, *, max_len: int = 400_000) -> Sanitized:
    p = _San(max_len)
    try:
        p.feed(raw[:2_000_000])
        p.close()
        p.close_all()
    except (ValueError, AssertionError, RecursionError):      # fail closed: plain escaped text, no markup at all
        return Sanitized(html.escape(html_to_text(raw))[:max_len], 0, [], True)
    return Sanitized("".join(p.out), p.blocked, p.hosts[:100], p.truncated)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "head", "title"):
            self.skip += 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head", "title") and self.skip:
            self.skip -= 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    try:
        p.feed(raw[:2_000_000])
        p.close()
    except (ValueError, AssertionError, RecursionError):
        return re.sub(r"<[^>]*>", " ", raw)[:100_000]
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "".join(p.parts))).strip()


def demo() -> None:
    s = sanitize_html('<p onclick="x()" style="background:url(http://e/x)">Hi<script>alert(1)</script>'
                      '<img src="http://t.example/p.gif"><a href="https://evil.test/x">https://bank.example</a>'
                      '<a href="java\tscript:alert(1)">no</a></p>')
    assert "script" not in s.html and "onclick" not in s.html and "style" not in s.html
    assert s.blocked_images == 1 and "evil.test" in s.html and "javascript" not in s.html.lower(), s
    print("sanitize ok")


if __name__ == "__main__":
    demo()
