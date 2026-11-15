# ================================================================================

"""Connector layer: an in-memory registry of connector configs with a simulated request.

register_connector(name, config) (False if it exists), update_connector(name, config) (merges;
False if unknown), get_connector(name) (None if unknown), remove_connector(name) (False if
unknown). request(connector_name, payload) performs no real IO: it echoes the payload as
{"status": "OK", ...} or returns {"status": "ERROR", "error": "ConnectorMissing"}. Configs are
stored as given, with no secret handling. State: a dict in memory only, lost on restart.
"""
import json
import re
from typing import Dict, Any, Optional

_SECRET_KEY = re.compile(r"(secret|token|password|passwd|api_?key|credential|authorization|private)", re.I)


def _masked(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _masked(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_masked(v, key) for v in value]
    return "***" if value and _SECRET_KEY.search(key) else value


class ConnectorLayer:
    """
    Velaris Connector Layer
    - Manages external/internal service connectors
    - Provides registry for adapters
    - Normalizes request/response formats
    """

    def __init__(self):
        self.connectors: Dict[str, Dict[str, Any]] = {}

    def register_connector(self, name: str, config: Dict[str, Any]) -> bool:
        if name in self.connectors:
            return False
        self.connectors[name] = config
        return True

    def update_connector(self, name: str, config: Dict[str, Any]) -> bool:
        if name not in self.connectors:
            return False
        self.connectors[name].update(config)
        return True

    def get_connector(self, name: str) -> Optional[Dict[str, Any]]:
        """A COPY of the connector's config with secret-looking values masked; the live config never leaves this agent."""
        cfg = self.connectors.get(name)
        return None if cfg is None else _masked(cfg)

    def remove_connector(self, name: str) -> bool:
        if name in self.connectors:
            del self.connectors[name]
            return True
        return False

    def request(self, connector_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulation of a request dispatch.
        Real IO is not permitted in Lockdown mode.
        Returns normalized Velaris-style response.
        """
        if connector_name not in self.connectors:
            return {"status": "ERROR", "error": "ConnectorMissing"}
        return {
            "status": "OK",
            "connector": connector_name,
            "payload": payload,
            "echo": True
        }

# ================================================================================