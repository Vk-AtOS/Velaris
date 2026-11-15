"""Memory fabric: in-process key-value memory shared between agents, with no persistence.

MEMORY_FABRICAgent offers write_bucket(bucket, data) and read_bucket(bucket) (returns {} for an unknown bucket).
MemoryFabric, a compatibility shim, offers get_store(namespace) (a dict, created on demand), put(namespace, key, value,
ttl) (ttl in seconds, None means never expires), get(namespace, key) (the value, or None if absent or expired) and
query(namespace, prefix) (unexpired {key: value}, optionally only keys starting with prefix). health_check() returns ok.
State: Python dicts in memory only; everything is lost when the process ends. It does no validation and raises nothing
on bad input beyond the normal TypeError for unhashable keys.
"""
import logging
import time
logger = logging.getLogger("MEMORY_FABRIC")

class MEMORY_FABRICAgent:
    def __init__(self):
        self.name = "MEMORY_FABRIC"
        self._buckets = {}
        logger.debug("MEMORY_FABRIC initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def write_bucket(self, bucket: str, data: dict):
        self._buckets[bucket] = data
        logger.debug(f"BUCKET {bucket} written")

    def read_bucket(self, bucket: str):
        return self._buckets.get(bucket, {})

# ---- MemoryFabric: the store other agents use (get_store / put / get / query with optional TTL) ----


class MemoryFabric:
    """
    The in-process key/value store with optional expiry that other agents use. It is the only implementation (there is no other
    "real" MemoryFabric): it lives in this process's memory and is lost on restart; durable data belongs in JsonState.
    Provides the API other agents expect:
      - health_check()
      - get_store(name) -> dict-like object
      - put(namespace, key, value, ttl=None) / get(namespace, key) / query(namespace, prefix=None)
    """
    def __init__(self):
        self._stores = {}
        self._expires = {}   # (namespace, key) -> monotonic deadline
        logger.debug("MemoryFabric initialized")

    def health_check(self):
        return { "agent": "MEMORY_FABRIC", "status": "ok", "version": "0.1.0" }

    def get_store(self, name):
        if name not in self._stores:
            self._stores[name] = {}
        return self._stores[name]

    def put(self, namespace, key, value, ttl=None):
        """Store value under namespace/key; ttl is seconds until it expires (None = never)."""
        self.get_store(namespace)[key] = value
        if ttl is None:
            self._expires.pop((namespace, key), None)
        else:
            self._expires[(namespace, key)] = time.monotonic() + ttl
        return True

    def _live(self, namespace, key):
        deadline = self._expires.get((namespace, key))
        if deadline is not None and time.monotonic() >= deadline:
            self._stores.get(namespace, {}).pop(key, None)
            del self._expires[(namespace, key)]
            return False
        return key in self._stores.get(namespace, {})

    def get(self, namespace, key):
        """The stored value, or None if absent or expired."""
        return self._stores[namespace][key] if self._live(namespace, key) else None

    def query(self, namespace, prefix=None):
        """Unexpired {key: value} in a namespace, optionally only keys starting with prefix."""
        keys = [k for k in list(self._stores.get(namespace, {})) if self._live(namespace, k)]
        return {k: self._stores[namespace][k] for k in keys if prefix is None or str(k).startswith(prefix)}
