"""Encryption at rest for identifiers and collected documents, plus masking.

`cryptography` is already a runtime requirement (requirements.txt: velaris.api.auth), so the construction is
AES-256-GCM from cryptography.hazmat, not a home-made stream cipher. Nothing here invents a primitive.

  seal(plaintext, aad)   -> "v1.<nonce>.<ciphertext+tag>" (url-safe base64). A fresh random 96-bit nonce per
                            call. `aad` (the record id, the field name) is authenticated but not stored, so a
                            ciphertext cannot be moved to another record or field without failing to open.
  open_sealed(token, aad) -> plaintext bytes, or raises SealError (tampered, wrong record, wrong key).
  The key is 32 random bytes in <data dir>/onboarding_field.key, created owner-only on first use by
  velaris.intel.paths.load_or_create_key. Lose the key and the data is gone; that is the point of erasure by
  key destruction later (not built: it would erase everything at once).

Aadhaar is different: it is NOT stored in full, encrypted or not. aadhaar_digest() returns the last four digits
and an HMAC-SHA256 of the full number under a separate key. Why: the full number is a high-value identifier
that, once stored, must be protected for as long as it exists, and the employer's purpose (a record that
the person gave a valid number, a check that a later number matches) is met by the last four plus a keyed hash.
A keyed hash of a 12-digit number is guessable by anyone who has the key (10^12 candidates), so the key file
is as sensitive as the data: keep it owner-only and out of backups that leave the machine.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Dict

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from velaris.intel.paths import data_dir, load_or_create_key


class SealError(ValueError):
    """The sealed value cannot be opened: altered, moved to another record, or sealed under another key."""


def _key(name: str) -> bytes:
    return load_or_create_key(data_dir() / name, 32)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def seal(plaintext: bytes, aad: str) -> str:
    nonce = os.urandom(12)
    return f"v1.{_b64(nonce)}.{_b64(AESGCM(_key('onboarding_field.key')).encrypt(nonce, plaintext, aad.encode()))}"


def open_sealed(token: str, aad: str) -> bytes:
    try:
        version, nonce, body = token.split(".")
        if version != "v1":
            raise SealError("unknown sealed-value version")
        return AESGCM(_key("onboarding_field.key")).decrypt(_unb64(nonce), _unb64(body), aad.encode())
    except InvalidTag as e:
        raise SealError("sealed value failed authentication") from e
    except (ValueError, TypeError) as e:
        if isinstance(e, SealError):
            raise
        raise SealError("sealed value is malformed") from e


def aadhaar_digest(number: str) -> Dict[str, str]:
    """{"last4", "digest"}: all that is kept of an Aadhaar number (see the module docstring)."""
    digits = "".join(number.split())
    return {"last4": digits[-4:],
            "digest": hmac.new(_key("onboarding_aadhaar.key"), digits.encode(), hashlib.sha256).hexdigest()}


def aadhaar_matches(number: str, stored: Dict[str, str]) -> bool:
    """True only when the last four AND the keyed digest both match. Both are compared in constant time and combined
    without short-circuit, so neither the result nor its timing says whether the last four alone matched."""
    mine = aadhaar_digest(number)
    last4 = hmac.compare_digest(mine["last4"], str(stored.get("last4", "")))
    full = hmac.compare_digest(mine["digest"], str(stored.get("digest", "")))
    return last4 & full
