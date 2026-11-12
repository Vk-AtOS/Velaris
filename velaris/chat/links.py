"""Link previews. Off by default: a server that fetches whatever URL a person pastes can be aimed at
internal services (SSRF). It is on only for hosts an organisation lists in the `unfurl_hosts` setting,
and every fetch goes through velaris.intel.web_fetch, which refuses non-public addresses, honours
robots.txt, rate-limits and caps size. Only a page <title> is returned, for a person to read; it is
never given to the assistant."""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from velaris.chat.core import ChatCore
from velaris.core.access import Caller
from velaris.intel.web_fetch import FetchError, Fetcher

_URL = re.compile(r"https?://[^\s<>\"'\]\[]{1,500}")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
MAX_LINKS = 3


def host_allowed(url: str, hosts: List[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return bool(host) and any(host == h.lower() or host.endswith("." + h.lower()) for h in hosts)


class LinksMixin(ChatCore):
    fetcher: Optional[Fetcher] = None

    def unfurl(self, caller: Caller, message_id: int) -> List[Dict[str, Any]]:
        """[] unless the organisation has allow-listed hosts and the message links to one."""
        caller = self._enter(caller)
        msg = self._live(caller, message_id)                    # type: ignore[attr-defined]
        self._require(caller, self._channel(caller, msg["channel_id"]), "view")
        hosts = self.org_setting(caller.org, "unfurl_hosts")    # type: ignore[attr-defined]
        urls = [u for u in _URL.findall(msg["body"]) if hosts and host_allowed(u, hosts)][:MAX_LINKS]
        out = []
        for url in urls:
            try:
                page = (self.fetcher or Fetcher()).fetch(url)
            except FetchError:
                continue
            m = _TITLE.search(page.text[:100_000])
            out.append({"url": url, "title": " ".join(html.unescape(m.group(1)).split())[:200] if m else None})
        return out
