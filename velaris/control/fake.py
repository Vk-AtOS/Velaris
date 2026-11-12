"""A scripted browser driver for tests and demos: pages are dicts, nothing touches a network.

pages = {"https://forms.test/new": {"elements": [{"role": "textbox", "name": "Full name"}, ...],
         "text": "New hire form", "submit_to": "https://forms.test/done"}}
Clicking a link goes to its href; clicking a button named like `submit_button` records the form
in `submissions` and goes to the page's `submit_to`. `unsticky` names fields whose typing is
silently lost (the page looks fine; the value is not kept): what verification must catch.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional, Tuple


class FakeDriver:
    def __init__(self, pages: Dict[str, Dict[str, Any]], start: str, *, unsticky: Iterable[str] = (),
                 submit_button: str = "Submit") -> None:
        self.pages = copy.deepcopy(pages)
        self._url, self.unsticky, self.submit_button = start, set(unsticky), submit_button
        self.submissions: List[Dict[str, str]] = []
        self.history: List[str] = [start]
        self.closed = False

    def _page(self) -> Dict[str, Any]:
        return self.pages.get(self._url, {"elements": [], "text": ""})

    def goto(self, url: str) -> None:
        if self.closed:
            raise RuntimeError("closed")
        self._url = url
        self.history.append(url)

    def url(self) -> str:
        return self._url

    def snapshot(self) -> Tuple[List[Dict[str, Any]], str]:
        if self.closed:
            raise RuntimeError("closed")
        p = self._page()
        return [dict(e) for e in p.get("elements", [])], p.get("text", "")

    def click(self, index: int) -> None:
        e = self._page()["elements"][index]
        if e["role"] == "link":
            self.goto(e["href"])
        elif e["role"] == "button" and e["name"] == self.submit_button:
            fields = {x["name"]: x.get("value", "") for x in self._page()["elements"] if x["role"] in ("textbox", "combobox")}
            self.submissions.append(fields)
            if self._page().get("submit_to"):
                self.goto(self._page()["submit_to"])
        elif e["role"] in ("checkbox", "radio"):
            e["value"] = "" if e.get("value") == "on" else "on"

    def fill(self, index: int, value: str) -> None:
        e = self._page()["elements"][index]
        if e["name"] not in self.unsticky:
            e["value"] = value

    select = fill

    def records(self) -> List[Dict[str, str]]:
        """What the (fake) system of record holds: the submissions it actually stored."""
        return list(self.submissions)

    def close(self) -> None:
        self.closed = True
