"""Chromos: detects schema changes by hashing a canonical JSON form of each schema.

ChromosAgent(config): health_check(); normalize_schema(dict) returns JSON with sorted
keys; schema_hash(normalized) returns its SHA-256 hex; store_schema(key, dict) records
the hash under key and returns it; compare_schema(key, new_schema) returns True when the
new hash differs from the stored one.
State: in memory only (self.schemas, hashes not schemas), lost on restart.
Failure: compare_schema returns False for an unknown key (indistinguishable from
unchanged); a schema that json cannot serialise raises TypeError.
"""

import logging
import json
import hashlib

logger = logging.getLogger("CHROMOS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CHROMOS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class ChromosAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.schemas = {}

    def health_check(self):
        status = {"agent": "CHROMOS", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def normalize_schema(self, schema_dict):
        """Sort keys, remove whitespace, and produce deterministic ordering."""
        norm = json.dumps(schema_dict, sort_keys=True)
        logger.debug("Normalized schema: %s", norm)
        return norm

    def schema_hash(self, normalized_schema):
        """SHA-256 hash of schema."""
        h = hashlib.sha256(normalized_schema.encode()).hexdigest()
        logger.debug("Schema hash: %s", h)
        return h

    def store_schema(self, key, schema_dict):
        norm = self.normalize_schema(schema_dict)
        h = self.schema_hash(norm)
        self.schemas[key] = h
        logger.debug("Stored schema: key=%s hash=%s", key, h)
        return h

    def compare_schema(self, key, new_schema):
        if key not in self.schemas:
            logger.debug("Schema comparison: key not found (%s)", key)
            return False
        norm = self.normalize_schema(new_schema)
        new_hash = self.schema_hash(norm)
        old_hash = self.schemas[key]
        changed = (new_hash != old_hash)
        logger.debug("Schema compare: key=%s changed=%s", key, changed)
        return changed
