"""Auditor: checks a workflow against required steps and scans log lines for banned terms.

check_compliance(workflow_steps, required_steps) is True only when every required step is
present; find_violations(log_entries, banned_terms) returns the entries containing any banned
term (case-sensitive substring). Pure functions, no policy source and no audit trail: it keeps
no state. Non-iterable input raises TypeError.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("AUDITOR")

class AuditorAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "AUDITOR", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def check_compliance(self, workflow_steps: List[str], required_steps: List[str]) -> bool:
        """
        Ensure required steps are included in workflow_steps.
        """
        logger.debug("Checking compliance workflow=%s required=%s",
                     workflow_steps, required_steps)
        for step in required_steps:
            if step not in workflow_steps:
                logger.debug("Missing required step=%s", step)
                return False
        return True

    def find_violations(self, log_entries: List[str], banned_terms: List[str]) -> List[str]:
        """
        Returns log entries containing banned terms.
        """
        logger.debug("Scanning logs for violations terms=%s", banned_terms)
        violations = []
        for entry in log_entries:
            for term in banned_terms:
                if term in entry:
                    violations.append(entry)
                    break
        logger.debug("Violations found: %s", violations)
        return violations
