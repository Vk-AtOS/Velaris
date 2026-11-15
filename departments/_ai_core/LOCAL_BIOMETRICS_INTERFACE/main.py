# ================================================================================

"""Local biometrics interface: stores SHA-256 hashes of biometric strings per user and checks presented ones against them.

LocalBiometricsInterface: enroll(user, biometrics) stores a hash per factor
({"finger"|"face"|"voice": text}, any key accepted) and returns False if the user is
already enrolled; verify(user, biometrics) is True only if the user exists, at least one
factor is presented, and every presented factor equals its enrolled hash; update(user,
biometrics) overwrites or adds factor hashes for an enrolled user; list_users() returns
the enrolled user names.
This is an exact-hash comparison, not fuzzy biometric matching, and the hash is unsalted.
State: in memory only (self.templates), lost on restart.
Failure: unknown user, empty input or any unmatched or un-enrolled factor returns False
(fail closed); non-string factor values raise AttributeError.
"""

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
        if not biometrics:
            return False  # fail closed: no factor presented
        for k, v in biometrics.items():
            # fail closed: an un-enrolled factor is not evidence
            if self.templates[user].get(k) != self._hash(v):
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