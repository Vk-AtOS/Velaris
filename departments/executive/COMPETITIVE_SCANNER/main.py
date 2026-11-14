"""COMPETITIVE_SCANNER: read competitors' public pages and report what changed.

scan(competitors=[{"name", "url"}], fields=None):
  * each URL is fetched through velaris.intel.web.scrape (public addresses only, robots
    obeyed, text screened by the guard);
  * the page's title, description, size and a SHA-256 of its text are reported, with
    `changed` against the hash stored at the previous scan;
  * with `fields` ({name: description}), a model pulls those values out through
    web.extract, which drops any value the page text does not support. Without a model
    the extraction is `not_configured`; the change report still works.

The agent holds no competitor knowledge of its own: a page it cannot read is
reported as an error, never filled in. No competitors supplied -> `needs_data`.
State: <VELARIS_DATA>/agents/COMPETITIVE_SCANNER/snapshots.json (owner-only).
"""
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit
from velaris.intel import web

logger = logging.getLogger("COMPETITIVE_SCANNER")
MAX_COMPETITORS = 25
MAX_FIELDS = 12


class COMPETITIVE_SCANNERAgent:
    def __init__(self, name="COMPETITIVE_SCANNER"):
        self.name = name
        self._state = kit.JsonState("COMPETITIVE_SCANNER", "snapshots.json", {"pages": {}})

    def health_check(self):
        return kit.health(self.name)

    def scan(self, competitors: Any, fields: Optional[Dict[str, str]] = None, llm: Any = None,
             fetcher: Any = None) -> Dict[str, Any]:
        if not isinstance(competitors, (list, tuple)) or len(competitors) > MAX_COMPETITORS:
            return kit.failed([f"competitors must be a list of at most {MAX_COMPETITORS} records"])
        if not competitors:
            return kit.needs_data("no competitors supplied; the scanner does not guess who they are", results=[])
        errors: List[str] = []
        for i, c in enumerate(competitors):
            url = kit.ident(c.get("url"), 500) if isinstance(c, dict) else None
            if not isinstance(c, dict) or kit.ident(c.get("name")) is None:
                errors.append(f"competitors[{i}].name must be a non-empty string")
            if url is None or not url.startswith(("http://", "https://")):
                errors.append(f"competitors[{i}].url must be an http(s) address")
        if fields is not None and not (isinstance(fields, dict) and 0 < len(fields) <= MAX_FIELDS and all(
                kit.ident(k, 60) and kit.ident(v, 300) for k, v in fields.items())):
            errors.append(f"fields must map 1 to {MAX_FIELDS} field names to plain descriptions")
        if errors:
            return kit.failed(errors)
        can_extract = fields is not None and (llm is not None or kit.model_available())
        data = self._state.load()
        results = []
        for c in competitors:
            url = c["url"].strip()
            page = web.scrape(url, f=fetcher)
            row: Dict[str, Any] = {"name": c["name"].strip(), "url": url, "source": page.final_url or url}
            if not page.ok:
                row.update(status="error", error=page.error)
                results.append(row)
                continue
            digest = hashlib.sha256(page.markdown.encode("utf-8")).hexdigest()
            before = data["pages"].get(url)
            row.update(status="ok", title=page.title, description=page.metadata.get("description", ""),
                       words=len(page.markdown.split()), sha256=digest,
                       changed=None if before is None else before["sha256"] != digest,
                       previous_scan_at=before["seen_at"] if before else None, risk=page.risk)
            if fields is not None:
                if can_extract:
                    got = web.extract(page, fields, llm=llm)
                    row.update(extracted=got["data"], ungrounded=got["ungrounded"],
                               extraction="ok" if not got["error"] else f"error: {got['error']}")
                else:
                    row.update(extracted=None, extraction="not_configured")
            if fields is not None and can_extract and row.get("extraction") != "ok":
                results.append(row)       # extraction failed: keep the old hash so the next scan still sees the change
                continue
            data["pages"][url] = {"sha256": digest, "seen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            results.append(row)
        self._state.save(data)
        read = sum(r["status"] == "ok" for r in results)
        return {"status": "ok" if read else "no_results", "results": results, "pages_read": read,
                "pages_failed": len(results) - read,
                "changed": [r["name"] for r in results if r.get("changed")]}
