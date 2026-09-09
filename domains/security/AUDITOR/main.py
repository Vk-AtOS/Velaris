import logging
from typing import Dict, Any, List

logger = logging.getLogger("AUDITOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - AUDITOR - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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
