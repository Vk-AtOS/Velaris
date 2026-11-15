import logging
import time

logger = logging.getLogger("ARGUS")

class ArgusAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.heartbeat_timeout = self.config.get("heartbeat_timeout", 5)
        self.last_heartbeat = {}
        self.signatures = {}

    def health_check(self):
        status = {"agent": "ARGUS", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def update_heartbeat(self, source):
        now = time.time()
        self.last_heartbeat[source] = now
        logger.debug("Heartbeat updated: source=%s time=%s", source, now)
        return now

    def is_missing_heartbeat(self, source):
        now = time.time()
        last = self.last_heartbeat.get(source)
        if last is None:
            logger.debug("No heartbeat for source=%s", source)
            return True
        missing = (now - last) > self.heartbeat_timeout
        logger.debug("Heartbeat check: source=%s missing=%s", source, missing)
        return missing

    def update_signature(self, source, version):
        self.signatures[source] = version
        logger.debug("Signature updated: source=%s version=%s", source, version)
        return version

    def signature_changed(self, source, new_version):
        old = self.signatures.get(source)
        changed = (old != new_version)
        logger.debug("Signature change check: source=%s old=%s new=%s changed=%s",
                     source, old, new_version, changed)
        return changed
