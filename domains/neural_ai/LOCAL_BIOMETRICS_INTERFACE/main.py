# ================================================================================

import hashlib
from typing import Dict, Any


class LocalBiometricsInterface:
    """
    Velaris Local Biometrics Interface
    - Offline biometric template storage
    - Local hashing + match scoring
    - Supports finger, face, voice templates (string hashes)
    """

    def __init__(self):
        self.templates: Dict[str, Dict[str, str]] = {}

    def _hash(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def enroll(self, user: str, biometrics: Dict[str, str]) -> bool:
        """
        biometrics = {
            "finger": "...",
            "face": "...",
            "voice": "..."
        }
        """
        if user in self.templates:
            return False
        hashed = {k: self._hash(v) for k, v in biometrics.items()}
        self.templates[user] = hashed
        return True

    def verify(self, user: str, biometrics: Dict[str, str]) -> bool:
        if user not in self.templates:
            return False
        for k, v in biometrics.items():
            if k in self.templates[user]:
                if self.templates[user][k] != self._hash(v):
                    return False
        return True

    def update(self, user: str, biometrics: Dict[str, str]) -> bool:
        if user not in self.templates:
            return False
        for k, v in biometrics.items():
            self.templates[user][k] = self._hash(v)
        return True

    def list_users(self):
        return list(self.templates.keys())

# ================================================================================