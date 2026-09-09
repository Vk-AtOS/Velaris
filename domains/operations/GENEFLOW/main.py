import logging
import json

logger = logging.getLogger("GENEFLOW")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - GENEFLOW - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class GeneFlowAgent:
    def __init__(self, config=None):
        self.config = config or {}

    def health_check(self):
        status = {"agent": "GENEFLOW", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def compute_diff(self, old, new):
        """Return added, removed, changed keys."""
        added = [k for k in new if k not in old]
        removed = [k for k in old if k not in new]
        changed = [k for k in old if k in new and old[k] != new[k]]

        diff = {"added": added, "removed": removed, "changed": changed}
        logger.debug("Diff computed: %s", diff)
        return diff

    def apply_migration(self, base, changes):
        """Apply changes to a dict for migration."""
        result = base.copy()
        for k in changes.get("removed", []):
            result.pop(k, None)
        for k in changes.get("added", []):
            result[k] = changes["added"][k] if isinstance(changes["added"], dict) else None
        for k in changes.get("changed", []):
            result[k] = changes["changed"][k] if isinstance(changes["changed"], dict) else None
        logger.debug("Migration applied: %s", result)
        return result
