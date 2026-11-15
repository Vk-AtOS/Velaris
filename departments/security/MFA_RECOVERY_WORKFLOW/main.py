# ================================================================================

import hashlib
import hmac
import secrets
import time
from typing import Optional

from velaris.agentkit.secure import Throttle, hash_secret, verify_secret
from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "MFA_RECOVERY_WORKFLOW"
CODE_TTL = 15 * 60          # a recovery code is good for 15 minutes, once
TOKEN_TTL = 10 * 60         # a reset token is good for 10 minutes, once
MAX_HASH = 512


def _now() -> float:
    return time.time()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()    # tokens are 192 random bits: a fast hash is enough


class MFARecoveryWorkflow:
    """
    Velaris MFA Recovery Workflow
    - A security admin issues a one-time recovery code (random, hashed, expires, 5 wrong tries lock the user)
    - A correct code is consumed and returns one reset token to the verifier (the user or a security admin)
    - The token is single use and is consumed by reset_credentials, which records the new credential hash
    State lives in VELARIS_DATA, so it is shared by workers and survives a restart.
    """

    def __init__(self):
        self._state = JsonState(NAME, "recovery.json")
        self._throttle = Throttle(NAME)

    def issue_recovery_code(self, user: str) -> Optional[str]:
        """A fresh 8-digit code (replacing any earlier one), or None when the caller may not issue one."""
        if not isinstance(user, str) or not user.strip():
            return None
        _, refused = check_caller(NAME, "issue_recovery_code", {"user": user[:128]}, roles=SECURITY_ADMINS)
        if refused:
            return None
        code = f"{secrets.randbelow(10 ** 8):08d}"
        entry = {"h": hash_secret(code), "exp": _now() + CODE_TTL}

        def put(d):
            d.setdefault("codes", {})[user] = entry
            d.get("tokens", {}).pop(user, None)
        self._state.update(put)
        return code

    def verify_recovery_code(self, user: str, code: str) -> Optional[str]:
        """The reset token (once) for a correct, unexpired, unused code; None otherwise.

        Only `user` themselves or a security admin may try (so a stranger cannot lock a user out by guessing), and
        the token is handed to that verifier in the same atomic step that consumes the code: there is no
        separate "verified" flag another caller could redeem. A wrong guess counts toward the lockout.
        """
        if not isinstance(user, str) or not isinstance(code, str):
            return None
        _, refused = check_caller(NAME, "verify_recovery_code", {"user": user[:128]}, roles=SECURITY_ADMINS, also=user)
        if refused or not self._throttle.begin(user):        # reserved BEFORE checking: parallel guesses all count
            return None
        entry = (self._state.load().get("codes") or {}).get(user)
        if not (verify_secret(code, entry["h"] if entry else None) and entry["exp"] > _now()):
            return None
        token = secrets.token_urlsafe(24)

        def consume(d):
            if d.get("codes", {}).get(user) != entry:        # another worker used it first
                return None
            del d["codes"][user]
            d.setdefault("tokens", {})[user] = {"h": _digest(token), "exp": _now() + TOKEN_TTL}
            return token
        got = self._state.update(consume)
        if got:
            self._throttle.clear(user)
        return got

    def _token_ok(self, rec, token) -> bool:
        return bool(rec) and isinstance(token, str) and rec["exp"] > _now() and hmac.compare_digest(rec["h"], _digest(token))

    def verify_reset_token(self, user: str, token: str) -> bool:
        return isinstance(user, str) and self._token_ok((self._state.load().get("tokens") or {}).get(user), token)

    def reset_credentials(self, user: str, token: str, new_hash: str) -> bool:
        """Consume the token and record `new_hash` (a hash made by the caller, never a password) as the user's credential."""
        if not isinstance(user, str) or not isinstance(new_hash, str) or not 0 < len(new_hash) <= MAX_HASH:
            return False
        _, refused = check_caller(NAME, "reset_credentials", {"user": user[:128]}, roles=SECURITY_ADMINS, also=user)
        if refused:
            return False

        def go(d):
            if not self._token_ok(d.get("tokens", {}).get(user), token):
                return False
            del d["tokens"][user]
            d.setdefault("credentials", {})[user] = new_hash
            return True
        return bool(self._state.update(go))

    def credential_hash(self, user: str) -> Optional[str]:
        return (self._state.load().get("credentials") or {}).get(user)

# ================================================================================
