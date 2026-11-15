# ================================================================================

"""Codex: detects changes in rule sets by hashing a canonical JSON form of each.

CodexAgent(config): health_check(); encode_rules(rules) returns JSON with sorted keys;
rules_hash(encoded) returns its SHA-256 hex; store_rules(key, rules_dict) records the hash
under key and returns it; rules_changed(key, new_rules_dict) is True when the new hash
differs from the stored one.
State: in memory only (self.rule_store, hashes not rules), lost on restart.
Failure: rules_changed returns False for an unknown key (indistinguishable from
unchanged); non-serialisable rules raise TypeError.
"""

import logging
import json
import hashlib

logger = logging.getLogger("CODEX")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CODEX - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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