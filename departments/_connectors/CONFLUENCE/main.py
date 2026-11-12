"""CONFLUENCE connector: Atlassian Confluence Cloud (API token + account email).

Read-only: search (CQL), get_page_markdown, list_spaces.
Consequential: ingest_space writes into the company document library (DOCUMENT_LIBRARY /
velaris.intel.docs), Velaris's own store (nothing in the customer's Confluence changes). It is an
`act` rule in velaris.api.allowlist and refuses to run outside an approved flow step, like the
Jira writes (atlassian.refuse_unless_approved).

Endpoints: GET /wiki/rest/api/search?cql= (v1 CQL search), GET /wiki/api/v2/spaces,
GET /wiki/api/v2/pages/{id}?body-format=storage, GET /wiki/api/v2/spaces/{id}/pages?body-format=storage.
Pages come back in "storage format" (XHTML with ac:/ri: macros) and are converted with
velaris.intel.web_markdown. Macro bodies other than plain text are rendered as text only
(ponytail: code and table-of-contents macros lose their special form; map macros if that bites).
Scope: only the spaces in config confluence_spaces / vault ATLASSIAN_CONFLUENCE_SPACES can be read or
ingested (see atlassian.py); empty means nothing. CQL is wrapped in `space in (...) AND (...)`, a page is
returned only if its spaceId belongs to an in-scope space, list_spaces shows only those, and the API
requires the atlassian_reader role for the reads. ingest_space also skips pages with view restrictions
(own or inherited from a parent, GET /wiki/rest/api/content/{id}/restriction/byOperation/read) so restricted
content never enters the shared library; if the restriction check fails the page is skipped.
Page text is data: it is screened by velaris.intel.guard; a page that reads like instructions is
withheld from the results and from the library, and said so.
"""
import html
import logging
import re
from typing import Any, Dict, List, Optional

from velaris.agents.JIRA.atlassian import (AtlassianClient, AtlassianError, in_scope, refuse_unless_approved, scope_query,
                                           screen)
from velaris.intel import trace
from velaris.intel.web_markdown import html_to_markdown

logger = logging.getLogger("CONFLUENCE")

READ_ONLY_METHODS = ("search", "get_page_markdown", "list_spaces")
CONSEQUENTIAL_METHODS = ("ingest_space",)
PAGE_ID = re.compile(r"[0-9]{1,19}")
SPACE_KEY = re.compile(r"~?[A-Za-z0-9]{1,255}")
MAX_INGEST_PAGES = 1000


def storage_to_markdown(storage: str, title: str = "") -> str:
    """Confluence storage format -> markdown."""
    doc = f"<html><head><title>{html.escape(title)}</title></head><body>{storage}</body></html>"
    return str(html_to_markdown(doc)["markdown"])


class ConfluenceConnector:
    def __init__(self, config: Optional[Dict[str, Any]] = None, *, library: Any = None, **client_args: Any) -> None:
        self.client = AtlassianClient(config, **client_args)
        self._library = library          # anything with ingest(name, data, scope); default DOCUMENT_LIBRARY

    def health_check(self) -> Dict[str, Any]:
        ok = self.client.configured
        return {"agent": "CONFLUENCE", "status": "ok" if ok else "unconfigured", "configured": ok,
                "read_only": list(READ_ONLY_METHODS), "consequential": list(CONSEQUENTIAL_METHODS)}

    def _lib(self) -> Any:
        if self._library is None:
            from velaris.agents.DOCUMENT_LIBRARY.main import DocumentLibrary
            self._library = DocumentLibrary()
        return self._library

    def _scoped_spaces(self) -> Dict[str, str]:
        """{space id: key} for the configured spaces that exist; empty when nothing is configured."""
        keys = self.client.scope("confluence_spaces")
        if not keys:
            return {}
        raw = self.client.paged("/wiki/api/v2/spaces", params={"keys": ",".join(keys), "limit": 100},
                                items_key="results", limit=1000)
        return {str(s.get("id")): str(s.get("key")) for s in raw if in_scope(s.get("key"), keys)}

    def _read_restricted(self, page_id: Any) -> bool:
        """True when the page has view restrictions or that cannot be established (fail closed)."""
        try:
            data = self.client.request("GET", f"/wiki/rest/api/content/{page_id}/restriction/byOperation/read") or {}
        except AtlassianError as e:
            logger.warning("restriction check of page %s failed: %s", page_id, e.reason)
            return True
        found = data.get("restrictions") if isinstance(data, dict) else None
        if not isinstance(found, dict) or not ({"user", "group"} & set(found)):
            return True
        return any((found.get(k) or {}).get("results") for k in ("user", "group"))

    def _hidden(self, page_id: Any, parents: Dict[str, Any], seen: Dict[str, bool]) -> bool:
        """Restricted itself or through an ancestor. Parents outside the listing are checked by id and end the walk."""
        pid = str(page_id)
        for _ in range(50):
            if pid not in seen:
                seen[pid] = self._read_restricted(pid)
            if seen[pid]:
                return True
            if pid not in parents or not parents[pid]:
                return False
            pid = str(parents[pid])
        return True                                     # too deep to trust

    def search(self, cql: str, *, limit: int = 25) -> Dict[str, Any]:
        """CQL search, paged up to `limit` (1-500). Titles and excerpts are screened."""
        if not isinstance(cql, str) or not cql.strip():
            raise ValueError("cql must be a non-empty string")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be 1 to 500")
        cql = scope_query(cql, "space", self.client.scope("confluence_spaces"))
        raw = self.client.paged("/wiki/rest/api/search", params={"cql": cql, "limit": 25}, items_key="results", limit=limit)
        results = []
        for r in raw:
            content = r.get("content") or {}
            title = screen(str(r.get("title") or content.get("title") or ""), "confluence:search:title")
            excerpt = screen(html.unescape(re.sub(r"<[^>]+>", "", str(r.get("excerpt") or ""))), "confluence:search:excerpt")
            results.append({"id": content.get("id"), "type": content.get("type") or r.get("entityType"),
                            "title": title["text"], "excerpt": excerpt["text"], "url": r.get("url"),
                            "guard": max((title["guard"], excerpt["guard"]), key=("none", "low", "high", "block").index)})
        return {"status": "ok", "count": len(results), "results": results}

    def get_page_markdown(self, page_id: str) -> Dict[str, Any]:
        """One page as markdown (version, space and title included)."""
        if not isinstance(page_id, str) or not PAGE_ID.fullmatch(page_id):
            raise ValueError("page_id must be the numeric page id")
        spaces = self._scoped_spaces()
        if not spaces:
            raise AtlassianError("out_of_scope", "no Confluence spaces are configured")
        page = self.client.request("GET", f"/wiki/api/v2/pages/{page_id}", params={"body-format": "storage"})
        if str((page or {}).get("spaceId")) not in spaces:
            raise AtlassianError("out_of_scope", "page is not in a configured Confluence space")
        return {"status": "ok", **self._page(page)}

    def list_spaces(self, *, limit: int = 100) -> Dict[str, Any]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be 1 to 1000")
        keys = self.client.scope("confluence_spaces")
        raw = [s for s in self.client.paged("/wiki/api/v2/spaces", params={"keys": ",".join(keys), "limit": 100},
                                            items_key="results", limit=1000) if in_scope(s.get("key"), keys)][:limit] if keys else []
        return {"status": "ok", "spaces": [{"id": s.get("id"), "key": s.get("key"), "name": s.get("name"),
                                            "type": s.get("type"), "status": s.get("status")} for s in raw]}

    def ingest_space(self, space_key: str, *, scope: str, max_pages: int = 200) -> Dict[str, Any]:
        """Copy the pages of a space into the document library under `scope`, as markdown.

        The library names each document "confluence <KEY> - <title> (<page id>)", which is what its
        answers cite. Unchanged pages are a no-op there, so this can run again to refresh.
        A page the guard blocks is not ingested; it is listed under "withheld". Only configured spaces are
        accepted; pages with view restrictions (their own or a parent's) are skipped and listed under
        "restricted". Each document starts with a line naming the space and page it came from.
        """
        refusal = refuse_unless_approved("CONFLUENCE", "ingest_space", {"space": str(space_key)[:40], "scope": str(scope)[:80]})
        if refusal:
            return refusal
        if not isinstance(space_key, str) or not SPACE_KEY.fullmatch(space_key):
            raise ValueError("space_key must be letters and digits, like ENG")
        if not scope or not isinstance(scope, str):
            raise ValueError("scope (the library to add to) is required")
        if not 1 <= max_pages <= MAX_INGEST_PAGES:
            raise ValueError(f"max_pages must be 1 to {MAX_INGEST_PAGES}")
        if not in_scope(space_key, self.client.scope("confluence_spaces")):
            raise AtlassianError("out_of_scope", "space is not in the configured Confluence scope")
        found = self.client.request("GET", "/wiki/api/v2/spaces", params={"keys": space_key, "limit": 1})
        spaces = [s for s in (found or {}).get("results") or [] if in_scope(s.get("key"), (space_key,))]
        if not spaces:
            raise AtlassianError("not_found", f"no space with key {space_key}")
        pages = self.client.paged(f"/wiki/api/v2/spaces/{spaces[0]['id']}/pages",
                                  params={"body-format": "storage", "limit": 25}, items_key="results", limit=max_pages)
        counts = {"ADDED": 0, "UPDATED": 0, "UNCHANGED": 0}
        withheld: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        restricted: List[Dict[str, Any]] = []
        parents = {str(p.get("id")): p.get("parentId") for p in pages}
        checked: Dict[str, bool] = {}
        for raw in pages:
            page = self._page(raw)
            if self._hidden(page["id"], parents, checked):
                restricted.append({"id": page["id"], "title": page["title"]})
                continue
            if page["guard"] == "block":
                withheld.append({"id": page["id"], "title": page["title"], "reason": "reads like instructions to an AI"})
                continue
            if not page["markdown"].strip():
                continue
            safe_title = re.sub(r"[/\\]", "-", page["title"])
            name = f"confluence {space_key.upper()} - {safe_title} ({page['id']}).md"
            try:
                result = self._lib().ingest(name, f"Source: Confluence space {space_key.upper()}, page {page['id']}\n\n{page['markdown']}".encode("utf-8"), scope)
            except Exception as e:      # one unreadable page must not stop the space; the others still go in
                logger.warning("ingest of Confluence page %s failed: %s", page["id"], type(e).__name__)
                failed.append({"id": page["id"], "title": page["title"], "error": type(e).__name__})
                continue
            counts[result["action"]] = counts.get(result["action"], 0) + 1
        trace.append("confluence", "ingest_space", {"space": space_key, "scope": scope, "pages_seen": len(pages), **counts,
                                                    "withheld": len(withheld), "restricted": len(restricted), "failed": len(failed)})
        return {"status": "ok" if not failed else "partial", "space": space_key, "pages_seen": len(pages),
                **counts, "withheld": withheld, "restricted": restricted, "failed": failed, "truncated": len(pages) >= max_pages}

    def _page(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        title = str(raw.get("title") or "")
        storage = ((raw.get("body") or {}).get("storage") or {}).get("value", "")
        text = screen(storage_to_markdown(storage, title), f"confluence:page:{raw.get('id')}")
        return {"id": raw.get("id"), "title": title, "space_id": raw.get("spaceId"),
                "version": (raw.get("version") or {}).get("number"), "markdown": text["text"], "guard": text["guard"]}


__all__ = ["ConfluenceConnector", "AtlassianError", "READ_ONLY_METHODS", "CONSEQUENTIAL_METHODS"]
