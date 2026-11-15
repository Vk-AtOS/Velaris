# ================================================================================

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
        if not templates or self._throttle.locked("owner"):
            return False
        results = [verify_secret(v, templates.get(k)) for k, v in presented.items()]   # no early exit: constant work
        ok = bool(results) and all(results)
        self._throttle.clear("owner") if ok else self._throttle.fail("owner")
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
