"""SELF_AUDIT: Velaris inspecting its own installation.

audit() runs three concrete checks and reports each finding with a severity:

  agent_load    every departments/<dept>/<AGENT>/main.py is imported; one that
                fails to import is "high"
  permissions   every file and directory under the data directory must be
                private to its owner. Group/other access is "high" for key
                material and anything under agents/, "medium" elsewhere; a file
                owned by another user is "high"
  trace         the hash-chained trace (velaris.intel.trace) must verify; a broken
                or unreadable chain is "critical"

It reports and changes nothing: no permission is fixed, no file removed. The
latest report is kept on disk, and update() lets another component add a
finding of its own to the same record. snapshot() returns both.
"""
from __future__ import annotations

import logging
import os
import stat
import time
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_name
from velaris.agentkit.results import invalid
from velaris.agentkit.state import JsonState
from velaris.agentkit.infra_store import audit
from velaris.agents.router import AgentRouter
from velaris.intel import paths, trace

logger = logging.getLogger("SELF_AUDIT")
NAME = "SELF_AUDIT"
SEVERITIES = ("low", "medium", "high", "critical")
MAX_FINDINGS = 200
MAX_REPORTED = 500


def _finding(severity: str, check: str, detail: str) -> Dict[str, str]:
    return {"severity": severity, "check": check, "detail": detail}


class SELF_AUDITAgent:
    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "audit.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    @staticmethod
    def _load_findings(load_failures: Optional[Dict[str, str]]) -> List[Dict[str, str]]:
        failed = AgentRouter().failed if load_failures is None else load_failures
        return [_finding("high", "agent_load", f"{name}: {str(error)[:200]}") for name, error in sorted(failed.items())]

    @staticmethod
    def _permission_findings() -> List[Dict[str, str]]:
        root = str(paths.data_dir())
        found = []
        for folder, dirs, files in os.walk(root, followlinks=False):
            for entry in [folder] + [os.path.join(folder, f) for f in files]:
                try:
                    st = os.lstat(entry)
                except OSError as e:
                    found.append(_finding("medium", "permissions", f"{os.path.relpath(entry, root)}: unreadable ({e.strerror})"))
                    continue
                rel = os.path.relpath(entry, root)
                if stat.S_ISLNK(st.st_mode):
                    continue
                if st.st_uid != os.getuid():
                    found.append(_finding("high", "permissions", f"{rel}: owned by uid {st.st_uid}, not this user"))
                if st.st_mode & 0o077:
                    sensitive = rel.startswith("agents") or rel.endswith((".key", ".pem")) or "key" in os.path.basename(rel)
                    found.append(_finding("high" if sensitive else "medium", "permissions",
                                          f"{rel}: mode {stat.S_IMODE(st.st_mode):o} lets other users in"))
        return found

    @staticmethod
    def _trace_findings() -> List[Dict[str, str]]:
        try:
            v = trace.verify()
        except (OSError, ValueError, KeyError, TypeError) as e:
            return [_finding("critical", "trace", f"trace is unreadable: {type(e).__name__}")]
        return [] if v["ok"] else [_finding("critical", "trace", f"chain broken at entry {v['broken_at']}: {v['reason']}")]

    def audit(self, load_failures: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Run every check. `load_failures` ({agent: error}) replaces the import scan when supplied."""
        if load_failures is not None and not (isinstance(load_failures, dict) and all(
                isinstance(k, str) for k in load_failures)):
            return invalid("load_failures must be an object of {agent: error}")
        findings = self._load_findings(load_failures) + self._permission_findings() + self._trace_findings()
        counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
        report = {"ts": time.time(), "clean": not findings, "counts": counts, "total": len(findings),
                  "findings": findings[:MAX_FINDINGS], "truncated": len(findings) > MAX_FINDINGS}
        self._state.update(lambda d: d.__setitem__("last_audit", report))
        audit(NAME, "audit", {"total": len(findings), "counts": counts})
        return {"status": "ok", **report}

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a finding another component reports: {"check": name, "severity": ..., "detail": text}."""
        valid = (isinstance(data, dict) and is_name(data.get("check")) and data.get("severity") in SEVERITIES
                 and isinstance(data.get("detail"), str) and data["detail"].strip())
        if not valid:
            return {**invalid(f"need check (a name), severity ({', '.join(SEVERITIES)}) and detail (text)"), "updated": False}
        entry = {"ts": time.time(), **_finding(data["severity"], data["check"], data["detail"][:500])}
        self._state.update(lambda d: d.__setitem__("reported", (d.get("reported", []) + [entry])[-MAX_REPORTED:]))
        return {"status": "ok", "updated": True}

    def snapshot(self) -> Dict[str, Any]:
        data = self._state.load()
        return {"status": "ok", "snapshot": self.name, "last_audit": data.get("last_audit"),
                "reported": data.get("reported", [])}
