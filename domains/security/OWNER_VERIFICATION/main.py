# ================================================================================

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
        for key, value in kwargs.items():
            if key not in self.owner_templates:
                return False
            if self.owner_templates[key] != self._hash(value):
                return False
        return True

# ================================================================================