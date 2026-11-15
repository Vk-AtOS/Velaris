"""Helix: stores and verifies SHA-256 signatures of "genome" data.
HelixAgent.generate_signature(data) returns the SHA-256 hex digest of the JSON of data (sorted keys).
store_genome(key, data) stores that signature under key and returns it. verify_genome(key, data)
returns True when the signature of data equals the stored one, False for an unknown key or a mismatch.
Only the hash is kept, not the data. It is a plain integrity check with no secret key, so it does
not prove who produced the data.
State: in-memory dict only, nothing persisted. Failure: data that is not JSON serializable raises
TypeError.
"""
import logging
import hashlib
import json

logger = logging.getLogger("HELIX")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - HELIX - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class HelixAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.genome_store = {}

    def health_check(self):
        status = {"agent": "HELIX", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def generate_signature(self, data):
        encoded = json.dumps(data, sort_keys=True).encode()
        h = hashlib.sha256(encoded).hexdigest()
        logger.debug("Generated signature: %s", h)
        return h

    def store_genome(self, key, data):
        sig = self.generate_signature(data)
        self.genome_store[key] = sig
        logger.debug("Stored genome: key=%s sig=%s", key, sig)
        return sig

    def verify_genome(self, key, data):
        if key not in self.genome_store:
            return False
        current = self.generate_signature(data)
        stored = self.genome_store[key]
        ok = current == stored
        logger.debug("Verify genome: key=%s ok=%s", key, ok)
        return ok
