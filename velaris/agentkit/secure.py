"""The three primitives every security agent needs, in one place so no agent rolls its own.

  hash_secret / verify_secret   scrypt with a random salt for PINs, passwords and recovery codes. verify_secret
                                never raises and costs the same whether or not the secret exists (pass
                                stored=None to burn the same time for an unknown user).
  Throttle                      consecutive-failure lockout kept in a JsonState file, so it survives a restart
                                and is shared by every worker process. A locked key is refused even with the
                                right secret until the lock expires.
  safe_join                     base / name, where name must be a plain file name and the result must resolve
                                inside base (no separators, no "..", no symlink out).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Optional, Union

from velaris.agentkit.checks import is_name
from velaris.agentkit.state import JsonState

_N, _R, _P = 2 ** 14, 8, 1
_DUMMY_SALT = b"\x00" * 16
MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60


def _scrypt(secret: str, salt: bytes) -> bytes:
    return hashlib.scrypt(secret.encode("utf-8", "surrogatepass"), salt=salt, n=_N, r=_R, p=_P, dklen=32)


def hash_secret(secret: str) -> str:
    salt = os.urandom(16)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(_scrypt(secret, salt)).decode()


def verify_secret(secret: object, stored: Optional[str]) -> bool:
    """True only for the secret that produced `stored`. Anything malformed is False, never an exception."""
    try:
        if not isinstance(secret, str):
            raise ValueError("not a string")
        scheme, salt_b64, hash_b64 = (stored or "").split("$")
        if scheme != "scrypt":
            raise ValueError("unknown scheme")
        salt, want = base64.b64decode(salt_b64), base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        if isinstance(secret, str):
            _scrypt(secret, _DUMMY_SALT)          # same cost for "no such user" as for a wrong secret
        return False
    return hmac.compare_digest(_scrypt(secret, salt), want)


class Throttle:
    """`MAX_ATTEMPTS` failures in a row lock `key` for `LOCK_SECONDS`; a success clears the count."""

    def __init__(self, agent: str, filename: str = "throttle.json", *, max_attempts: int = MAX_ATTEMPTS,
                 lock_seconds: float = LOCK_SECONDS) -> None:
        self._state = JsonState(agent, filename)
        self.max_attempts, self.lock_seconds = max_attempts, lock_seconds

    def locked(self, key: str) -> bool:
        rec = self._state.load().get(key) or {}
        return float(rec.get("until", 0)) > time.time()

    def fail(self, key: str) -> None:
        def go(data: dict) -> None:
            rec = data.get(key) or {"fails": 0}
            if float(rec.get("until", 0)) <= time.time() and rec.get("until"):
                rec = {"fails": 0}                      # an expired lock starts a fresh count
            rec["fails"] = int(rec.get("fails", 0)) + 1
            if rec["fails"] >= self.max_attempts:
                rec["until"] = time.time() + self.lock_seconds
            data[key] = rec
        self._state.update(go)

    def clear(self, key: str) -> None:
        self._state.update(lambda d: d.pop(key, None))


def safe_join(base: Union[str, Path], name: object, suffix: str = "") -> Path:
    """`base/name+suffix`, refusing anything that is not a plain file name or that resolves outside `base`."""
    if not is_name(name) or name in (".", "..") or ".." in str(name) or "\x00" in str(name):
        raise ValueError("name must be a plain file name without path separators or '..'")
    root = Path(base).resolve()
    target = (root / f"{name}{suffix}").resolve()
    if target.parent != root:
        raise ValueError("path escapes its folder")
    return target
