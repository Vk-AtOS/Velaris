import logging
import json

logger = logging.getLogger("GENEFLOW")

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

        # "values" carries the new value of every added or changed key, so apply_migration(base, diff) works.
        diff = {"added": added, "removed": removed, "changed": changed,
                "values": {k: new[k] for k in added + changed}}
        logger.debug("Diff computed: %s", diff)
        return diff

    def apply_migration(self, base, changes):
        """Apply changes to a dict for migration."""
        result = base.copy()
        for k in changes.get("removed", []):
            result.pop(k, None)
        values = changes.get("values", {})
        for part in ("added", "changed"):
            for k in changes.get(part, []):
                if isinstance(changes[part], dict):
                    result[k] = changes[part][k]
                elif k in values:
                    result[k] = values[k]
                else:
                    raise ValueError(f"no new value for {part} key {k!r}; pass the dict form or the diff from compute_diff")
        logger.debug("Migration applied: %s", result)
        return result
