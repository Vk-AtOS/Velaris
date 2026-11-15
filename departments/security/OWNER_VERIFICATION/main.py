# ================================================================================

"""Owner verification: checks the fingerprint, face and voice templates of the single owner by exact string match.

enroll(fingerprint, face, voice) stores a salted scrypt hash of each non-empty template and replaces any earlier owner:
security admins only (check_caller, traced). verify(fingerprint, face, voice) is True only when all three match.
partial_verify(**factors) takes two or more of finger, face and voice and is True only when all of them match; a single
factor, or an unknown factor name, is False. With nobody enrolled everything is False. 5 failed verifications in a row
lock verification for 15 minutes, the right templates included; a success or a new enrolment clears the count.
owner_templates returns the stored hashes. This compares enrolled strings; it does no fuzzy biometric matching.
State: <VELARIS_DATA>/agents/OWNER_VERIFICATION/owner.json (hashes only) and throttle.json, owner-only and shared by
workers. Refusals are False returns; nothing is raised.
"""
from velaris.agentkit.secure import Throttle, hash_secret, verify_secret
from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "OWNER_VERIFICATION"
FACTORS = ("finger", "face", "voice")


class OwnerVerification:
    """
    Velaris Owner Verification Module
    - Uses fingerprint, face, and voice templates for strong local verification
    - All offline; each template is stored as a salted scrypt hash (an EXACT match is required: this
      agent compares enrolled strings, it does not do fuzzy biometric matching)
    - Enrolling or replacing the owner needs a security admin and is traced
    - 5 failed verifications in a row lock verification for 15 minutes
    """

    def __init__(self):
        self._state = JsonState(NAME, "owner.json")
        self._throttle = Throttle(NAME)

    @property
    def owner_templates(self):
        return self._state.load().get("templates") or {}

    def enroll(self, fingerprint: str, face: str, voice: str) -> bool:
        """Registers the *single real owner*. Only a security admin may do it, first time or replacement."""
        if not all(isinstance(v, str) and v for v in (fingerprint, face, voice)):
            return False
        _, refused = check_caller(NAME, "enroll", {"replacing": bool(self.owner_templates)}, roles=SECURITY_ADMINS)
        if refused:
            return False
        templates = {k: hash_secret(v) for k, v in zip(FACTORS, (fingerprint, face, voice))}
        self._state.update(lambda d: d.__setitem__("templates", templates))
        self._throttle.clear("owner")
        return True

    def _matches(self, presented: dict) -> bool:
        templates = self.owner_templates
        if not templates or not self._throttle.begin("owner"):
            return False
        results = [verify_secret(v, templates.get(k)) for k, v in presented.items()]   # no early exit: constant work
        ok = bool(results) and all(results)
        if ok:
            self._throttle.clear("owner")
        return ok

    def verify(self, fingerprint: str, face: str, voice: str) -> bool:
        return self._matches({"finger": fingerprint, "face": face, "voice": voice})

    def partial_verify(self, **kwargs) -> bool:
        """
        Two or more factors, ALL of which must match (one matching factor is never enough).
        Unknown factor names fail.
        """
        if len(kwargs) < 2 or any(k not in FACTORS for k in kwargs):
            return False  # fail closed: too few factors, or a factor we do not know
        return self._matches(kwargs)

# ================================================================================
