# ================================================================================

"""Local biometrics interface: enrols and verifies per-user biometric templates by exact string match.

enroll(user, biometrics) takes any non-empty subset of {"finger", "face", "voice"} as non-empty strings and stores a
salted scrypt hash of each. Only the user themselves or a security admin may enrol (check_caller, traced), and a user who
is already enrolled is refused. verify(user, biometrics) is True only when every presented factor matches an enrolled
one; an unknown user, an empty dict and an unknown or un-enrolled factor are all False, and 5 failed verifications in a
row lock that user for 15 minutes (correct templates are refused too). update(user, current, biometrics) replaces or adds
templates once `current` verifies, for the same callers as enroll. list_users() returns the enrolled names. Refusals are
False returns.
State: <VELARIS_DATA>/agents/LOCAL_BIOMETRICS_INTERFACE/templates.json (hashes only, owner-only, shared by workers) and
throttle.json. A real sensor never produces the same capture twice, so this is a stand-in for a matcher: it compares
enrolled strings and does not score similarity.
"""
from typing import Dict, Optional

from velaris.agentkit.secure import Throttle, hash_secret, verify_secret
from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "LOCAL_BIOMETRICS_INTERFACE"
FACTORS = ("finger", "face", "voice")


class LocalBiometricsInterface:
    """
    Velaris Local Biometrics Interface
    - Offline biometric template storage: salted scrypt hashes in VELARIS_DATA (owner-only, shared by workers)
    - EXACT string match only: a real sensor never produces identical captures twice, so this agent compares
      enrolled strings (a stand-in for a real matcher), it does not score similarity
    - Enrolling or changing a template needs the person themselves or a security admin, and a change needs proof
      of the current template; 5 failed verifications in a row lock that user for 15 minutes
    """

    def __init__(self):
        self._state = JsonState(NAME, "templates.json", encrypted="agent:LOCAL_BIOMETRICS_INTERFACE")
        self._throttle = Throttle(NAME)

    @staticmethod
    def _valid(biometrics) -> bool:
        return (isinstance(biometrics, dict) and biometrics and set(biometrics) <= set(FACTORS)
                and all(isinstance(v, str) and v for v in biometrics.values()))

    def _templates(self, user: str) -> Optional[Dict[str, str]]:
        return (self._state.load().get("templates") or {}).get(user)

    def enroll(self, user: str, biometrics: Dict[str, str]) -> bool:
        """biometrics = {"finger": "...", "face": "...", "voice": "..."} (any non-empty subset)."""
        if not isinstance(user, str) or not user or not self._valid(biometrics):
            return False
        _, refused = check_caller(NAME, "enroll", {"user": user[:128]}, roles=SECURITY_ADMINS, also=user)
        if refused:
            return False
        hashed = {k: hash_secret(v) for k, v in biometrics.items()}

        def put(d):
            templates = d.setdefault("templates", {})
            if user in templates:
                return False
            templates[user] = hashed
            return True
        return bool(self._state.update(put))

    def verify(self, user: str, biometrics: Dict[str, str]) -> bool:
        stored = self._templates(user) if isinstance(user, str) else None
        if not stored or not self._valid(biometrics):
            return False  # fail closed: unknown user, or no factor presented
        if not self._throttle.begin(user):
            return False
        # An un-enrolled factor is not evidence; no early exit, so the work does not reveal which factor failed.
        results = [verify_secret(v, stored.get(k)) for k, v in biometrics.items()]
        ok = all(results)
        if ok:
            self._throttle.clear(user)
        return ok

    def update(self, user: str, current: Dict[str, str], biometrics: Dict[str, str]) -> bool:
        """Replace or add templates. `current` must verify first (a stolen session cannot swap the enrolment)."""
        if not self._valid(biometrics) or not self.verify(user, current):
            return False
        _, refused = check_caller(NAME, "update", {"user": user[:128]}, roles=SECURITY_ADMINS, also=user)
        if refused:
            return False
        hashed = {k: hash_secret(v) for k, v in biometrics.items()}
        self._state.update(lambda d: d["templates"][user].update(hashed))
        return True

    def list_users(self):
        return list((self._state.load().get("templates") or {}))

# ================================================================================
