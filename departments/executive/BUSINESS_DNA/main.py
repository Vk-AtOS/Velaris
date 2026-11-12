"""BUSINESS_DNA: the company profile register.

"DNA" here means the handful of facts other agents and documents should agree
on: who the company is, what it sells and to whom. The agent validates a
profile, stores it with a version number, returns it, and reports which
required fields are still missing. It does not analyse or infer anything.

run(payload):
  {"action": "set", "profile": {...}}   validate, merge over the stored profile, save
  {"action": "get"}                     the stored profile, its version and missing fields

State: <VELARIS_DATA>/agents/BUSINESS_DNA/profile.json (owner-only).
"""
import logging
import time
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("BUSINESS_DNA")

TEXT_FIELDS = {"name": 200, "sector": 100, "location": 200, "target_customers": 500,
               "value_proposition": 1000, "legal_form": 100}
LIST_FIELDS = ("services", "values")
INT_FIELDS = {"team_size": (1, 1_000_000), "founded_year": (1800, 2200)}
REQUIRED = ("name", "sector", "location", "services", "target_customers", "value_proposition")


def _profile_errors(profile: Any) -> List[str]:
    if not isinstance(profile, dict) or not profile:
        return ["profile must be a non-empty object"]
    errors = []
    for key, value in profile.items():
        if key in TEXT_FIELDS:
            if kit.ident(value, TEXT_FIELDS[key]) is None:
                errors.append(f"{key} must be a non-empty string of at most {TEXT_FIELDS[key]} characters")
        elif key in LIST_FIELDS:
            if not isinstance(value, list) or not value or len(value) > 50 \
                    or any(kit.ident(v, 200) is None for v in value):
                errors.append(f"{key} must be a list of 1 to 50 non-empty strings")
        elif key in INT_FIELDS:
            lo, hi = INT_FIELDS[key]
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                errors.append(f"{key} must be a whole number from {lo} to {hi}")
        else:
            errors.append(f"unknown field {key}")
    return errors


class BusinessDnaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)
        self._state = kit.JsonState("BUSINESS_DNA", "profile.json", {"profile": {}, "version": 0, "updated_at": None})

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "BUSINESS_DNA", "status": "ok", "version": self.version}

    def _view(self, data: Dict[str, Any]) -> Dict[str, Any]:
        missing = [f for f in REQUIRED if f not in data["profile"]]
        return {"status": "ok" if data["profile"] else "needs_data", "profile": data["profile"],
                "profile_version": data["version"], "updated_at": data["updated_at"],
                "missing_required": missing, "complete": not missing}

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object"])
        action = payload.get("action", "set" if "profile" in payload else "get")
        data = self._state.load()
        if action == "get":
            return self._view(data)
        if action != "set":
            return kit.failed([f"unknown action {action!r}; use 'set' or 'get'"])
        errors = _profile_errors(payload.get("profile"))
        if errors:
            return kit.failed(errors)
        data["profile"].update(payload["profile"])
        data["version"] += 1
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._state.save(data)
        return self._view(data)
