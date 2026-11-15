# ================================================================================

import logging
import json
import hashlib

logger = logging.getLogger("CODEX")

class CodexAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.rule_store = {}

    def health_check(self):
        status = {"agent": "CODEX", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def encode_rules(self, rules: dict):
        """Convert a rule dict into a stable JSON string."""
        encoded = json.dumps(rules, sort_keys=True)
        logger.debug("Encoded rules: %s", encoded)
        return encoded

    def rules_hash(self, encoded_rules: str):
        """Return SHA-256 hash."""
        h = hashlib.sha256(encoded_rules.encode()).hexdigest()
        logger.debug("Rule hash: %s", h)
        return h

    def store_rules(self, key, rules_dict):
        encoded = self.encode_rules(rules_dict)
        h = self.rules_hash(encoded)
        self.rule_store[key] = h
        logger.debug("Stored rules: key=%s hash=%s", key, h)
        return h

    def rules_changed(self, key, new_rules_dict):
        if key not in self.rule_store:
            return False
        encoded = self.encode_rules(new_rules_dict)
        new_hash = self.rules_hash(encoded)
        old_hash = self.rule_store[key]
        changed = (new_hash != old_hash)
        logger.debug("Rules changed: key=%s changed=%s", key, changed)
        return changed

# ================================================================================