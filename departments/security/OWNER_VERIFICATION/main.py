# ================================================================================

"""Owner verification: compares fingerprint, face and voice strings with hashes enrolled for one owner.

enroll(fingerprint, face, voice) stores the SHA-256 of each string as the single owner's templates, replacing any earlier
ones, with no check on who is enrolling. verify(...) is True only when all three hash-match. partial_verify(finger=, face=,
voice=) is True when every supplied factor matches; no factors, an unknown factor name, or any mismatch gives False. With
nothing enrolled everything is False (fails closed). It compares exact strings, so it does no biometric matching, and the
hashes are unsalted. State: in memory only, so the enrolment is lost on exit.
"""
import hashlib
from typing import Dict


class OwnerVerification:
    """
    Velaris Owner Verification Module
    - Uses fingerprint, face, and voice templates for strong local verification
    - All offline, hash-based
    """

    def __init__(self):
        self.owner_templates: Dict[str, str] = {}

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def enroll(self, fingerprint: str, face: str, voice: str):
        """
        Registers the *single real owner* of Velaris.
        No multi-user support.
        """
        self.owner_templates = {
            "finger": self._hash(fingerprint),
            "face": self._hash(face),
            "voice": self._hash(voice),
        }

    def verify(self, fingerprint: str, face: str, voice: str) -> bool:
        if not self.owner_templates:
            return False
        return (
            self.owner_templates["finger"] == self._hash(fingerprint)
            and self.owner_templates["face"] == self._hash(face)
            and self.owner_templates["voice"] == self._hash(voice)
        )

    def partial_verify(self, **kwargs) -> bool:
        """
        Allows partial matching (e.g., only fingerprint or only face).
        """
        if not kwargs:
            return False  # fail closed: no factor presented
        for key, value in kwargs.items():
            if key not in self.owner_templates:
                return False
            if self.owner_templates[key] != self._hash(value):
                return False
        return True

# ================================================================================