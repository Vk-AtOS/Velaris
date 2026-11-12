"""JIRA connector: Atlassian Jira Cloud REST API v3 (API token + account email, HTTP Basic).

Read-only (safe to call without approval):   search_issues, get_issue, get_transitions, list_projects
Consequential (change the customer's Jira): create_issue, transition_issue
  These two are `act` rules in velaris.api.allowlist: the API turns a call into a flow step that
  waits for approval (Prime or local) and runs it afterwards. The methods themselves refuse any call
  that is not running inside an approved flow step (atlassian.refuse_unless_approved), whatever
  arguments it carries; there is no approval parameter to forge. Each run is traced.

Issue text (summary, description) is data: it is screened by velaris.intel.guard and withheld when
it reads like instructions to a model; the level is returned beside it.

Endpoints: GET /rest/api/3/search/jql (token-paged: nextPageToken; the older /rest/api/3/search is
deprecated by Atlassian and being removed), GET /rest/api/3/issue/{key}, GET/POST
/rest/api/3/issue/{key}/transitions, POST /rest/api/3/issue, GET /rest/api/3/project/search.
ponytail: parameter and field names follow Atlassian's published API as understood when this was
written; the first call against a real site should be checked against the live response.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from velaris.agents.JIRA.atlassian import AtlassianClient, AtlassianError, refuse_unless_approved, screen
from velaris.intel import trace

logger = logging.getLogger("JIRA")

READ_ONLY_METHODS = ("search_issues", "get_issue", "get_transitions", "list_projects")
CONSEQUENTIAL_METHODS = ("create_issue", "transition_issue")
ISSUE_KEY = re.compile(r"[A-Z][A-Z0-9_]{1,49}-[1-9][0-9]{0,9}")
PROJECT_KEY = re.compile(r"[A-Z][A-Z0-9_]{1,49}")
SEARCH_FIELDS = "summary,status,issuetype,priority,assignee,project,description,created,updated"


def _adf_text(node: Any) -> str:
    """Plain text of an Atlassian Document Format value (or a plain string)."""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text", ""))
    body = "".join(_adf_text(c) for c in node.get("content", []))
    return body + ("\n" if node.get("type") in ("paragraph", "heading", "listItem", "codeBlock") else "")


def _adf_paragraphs(text: str) -> Dict[str, Any]:
    paragraphs = [{"type": "paragraph", "content": [{"type": "text", "text": line}]} if line else
                  {"type": "paragraph", "content": []} for line in text.split("\n")]
    return {"type": "doc", "version": 1, "content": paragraphs}


class JiraConnector:
    def __init__(self, config: Optional[Dict[str, Any]] = None, **client_args: Any) -> None:
        self.client = AtlassianClient(config, **client_args)

    def health_check(self) -> Dict[str, Any]:
        ok = self.client.configured
        return {"agent": "JIRA", "status": "ok" if ok else "unconfigured", "configured": ok,
                "read_only": list(READ_ONLY_METHODS), "consequential": list(CONSEQUENTIAL_METHODS)}

    # ── shaping ──────────────────────────────────────────────────────────
    @staticmethod
    def _issue(raw: Dict[str, Any]) -> Dict[str, Any]:
        f = raw.get("fields") or {}
        key = str(raw.get("key", ""))
        summary = screen(str(f.get("summary") or ""), f"jira:{key}:summary")
        description = screen(_adf_text(f.get("description")).strip(), f"jira:{key}:description")
        levels = {summary["guard"], description["guard"]}
        return {
            "key": key, "id": raw.get("id"), "summary": summary["text"], "description": description["text"],
            "status": (f.get("status") or {}).get("name"), "type": (f.get("issuetype") or {}).get("name"),
            "priority": (f.get("priority") or {}).get("name"), "project": (f.get("project") or {}).get("key"),
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "created": f.get("created"), "updated": f.get("updated"),
            "guard": next(l for l in ("block", "high", "low", "none") if l in levels),
        }

    # ── read-only ────────────────────────────────────────────────────────
    def search_issues(self, jql: str, *, max_results: int = 50, fields: str = SEARCH_FIELDS) -> Dict[str, Any]:
        """Issues matching a JQL query, token-paged up to max_results (1-1000)."""
        if not isinstance(jql, str) or not jql.strip():
            raise ValueError("jql must be a non-empty string")
        if not 1 <= max_results <= 1000:
            raise ValueError("max_results must be 1 to 1000")
        raw = self.client.paged("/rest/api/3/search/jql", params={"jql": jql, "fields": fields, "maxResults": 100},
                                items_key="issues", limit=max_results, next_token=True)
        return {"status": "ok", "count": len(raw), "issues": [self._issue(i) for i in raw]}

    def get_issue(self, key: str) -> Dict[str, Any]:
        self._key(key)
        return {"status": "ok", "issue": self._issue(self.client.request(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": SEARCH_FIELDS}))}

    def get_transitions(self, key: str) -> Dict[str, Any]:
        """The transitions the issue can take now: needed to pick the id for transition_issue."""
        self._key(key)
        data = self.client.request("GET", f"/rest/api/3/issue/{key}/transitions")
        return {"status": "ok", "transitions": [{"id": t.get("id"), "name": t.get("name"),
                                                 "to": (t.get("to") or {}).get("name")}
                                                for t in (data or {}).get("transitions", [])]}

    def list_projects(self, *, max_results: int = 100) -> Dict[str, Any]:
        if not 1 <= max_results <= 1000:
            raise ValueError("max_results must be 1 to 1000")
        raw = self.client.paged("/rest/api/3/project/search", params={"maxResults": 100, "startAt": 0},
                                items_key="values", limit=max_results)
        return {"status": "ok", "projects": [{"key": p.get("key"), "name": p.get("name"), "id": p.get("id"),
                                              "type": p.get("projectTypeKey")} for p in raw]}

    # ── consequential: run only through an approval path ─────────────────
    def create_issue(self, project_key: str, summary: str, issue_type: str = "Task", description: str = "",
                     ) -> Dict[str, Any]:
        """CONSEQUENTIAL. Creates an issue in the customer's Jira."""
        refusal = refuse_unless_approved("JIRA", "create_issue", {"project": str(project_key)[:50]})
        if refusal:
            return refusal
        if not PROJECT_KEY.fullmatch(project_key or "") or not summary.strip() or "\n" in summary or len(summary) > 255:
            raise ValueError("project_key like 'ABC', and a one-line summary of at most 255 characters, are required")
        fields: Dict[str, Any] = {"project": {"key": project_key}, "summary": summary.strip(),
                                  "issuetype": {"name": issue_type}}
        if description.strip():
            fields["description"] = _adf_paragraphs(description)
        trace.append("jira", "create_issue", {"project": project_key})
        created = self.client.request("POST", "/rest/api/3/issue", json_body={"fields": fields}) or {}
        return {"status": "created", "key": created.get("key"), "id": created.get("id")}

    def transition_issue(self, key: str, transition_id: str) -> Dict[str, Any]:
        """CONSEQUENTIAL. Moves an issue through its workflow (ids from get_transitions)."""
        refusal = refuse_unless_approved("JIRA", "transition_issue", {"key": str(key)[:20]})
        if refusal:
            return refusal
        self._key(key)
        if not re.fullmatch(r"[0-9]{1,6}", str(transition_id)):
            raise ValueError("transition_id must be the numeric id from get_transitions")
        trace.append("jira", "transition_issue", {"key": key, "transition": str(transition_id)})
        self.client.request("POST", f"/rest/api/3/issue/{key}/transitions",
                            json_body={"transition": {"id": str(transition_id)}})
        return {"status": "transitioned", "key": key, "transition_id": str(transition_id)}

    @staticmethod
    def _key(key: str) -> None:
        if not isinstance(key, str) or not ISSUE_KEY.fullmatch(key):
            raise ValueError("issue key must look like ABC-123")


__all__ = ["JiraConnector", "AtlassianError", "READ_ONLY_METHODS", "CONSEQUENTIAL_METHODS"]
