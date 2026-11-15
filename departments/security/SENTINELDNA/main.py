"""Sentinel DNA: hash baselines to detect drift in data.

compute_hash(data) is the SHA-256 of the JSON form (sorted keys; non-JSON data raises
TypeError). set_baseline(key, data) stores and returns the hash; drift_detected(key, new_data)
is True when the hash differs from the baseline, or when no baseline exists for the key.
State: a dict in memory only, so baselines are lost on restart.
"""
import logging
import hashlib
import json

logger = logging.getLogger("SENTINELDNA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - SENTINELDNA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class SentinelDNAAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.baseline = {}

    def health_check(self):
        status = {"agent": "SENTINELDNA", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def compute_hash(self, data):
        encoded = json.dumps(data, sort_keys=True).encode()
        h = hashlib.sha256(encoded).hexdigest()
        logger.debug("Computed hash: %s", h)
        return h

    def set_baseline(self, key, data):
        h = self.compute_hash(data)
        self.baseline[key] = h
        logger.debug("Baseline set: key=%s hash=%s", key, h)
        return h

    def drift_detected(self, key, new_data):
        if key not in self.baseline:
            logger.debug("No baseline found for key=%s", key)
            return True
        new_hash = self.compute_hash(new_data)
        drift = (new_hash != self.baseline[key])
        logger.debug("Drift check: key=%s drift=%s", key, drift)
        return drift
