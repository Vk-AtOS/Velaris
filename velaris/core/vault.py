"""Encryption at rest for personal-data stores (decision D4).

  seal_bytes(data, purpose) -> bytes   b"VLV1" + nonce + AES-256-GCM(data); `purpose` (e.g. "mail") is
                                       authenticated, so a blob cannot be swapped between stores.
  open_bytes(blob, purpose)  -> bytes  raises VaultError on tamper, wrong purpose or wrong key.
  is_sealed(blob)            -> bool   lets callers migrate files that are still plaintext.

The master key lives OUTSIDE VELARIS_DATA, so a copy of the data directory is useless without it:
  VELARIS_VAULT_KEY        base64 (urlsafe or standard) of 32 bytes, or
  VELARIS_VAULT_KEY_FILE   path to a file holding that base64, mode 0600, not inside VELARIS_DATA.
A missing, short, world-readable or in-data-dir key raises VaultKeyError: the store fails CLOSED, a new key
is never invented (a restore without the key must not silently start a fresh, unreadable store).
Per-purpose keys are derived from the master with HKDF-SHA256.
"""
from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

from velaris.intel.paths import read_private, write_private
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"VLV1"


class VaultError(ValueError):
    """The blob cannot be opened (tampered, wrong store, wrong key)."""


class VaultKeyError(RuntimeError):
    """No usable master key: personal data is not read or written."""


def _master() -> bytes:
    raw = os.environ.get("VELARIS_VAULT_KEY", "").strip()
    if not raw:
        kf = os.environ.get("VELARIS_VAULT_KEY_FILE", "").strip()
        if not kf:
            raise VaultKeyError("VELARIS_VAULT_KEY or VELARIS_VAULT_KEY_FILE is not set; refusing to handle personal data")
        p = Path(kf)
        try:
            if stat.S_IMODE(p.stat().st_mode) & 0o077:
                raise VaultKeyError(f"vault key file {p} must be mode 0600")
            data_dir = Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris").resolve()
            if data_dir in p.resolve().parents:
                raise VaultKeyError("vault key file must not live inside VELARIS_DATA")
            raw = p.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise VaultKeyError(f"vault key file unreadable: {e}") from e
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except ValueError as e:
        raise VaultKeyError("vault key is not base64") from e
    if len(key) != 32:
        raise VaultKeyError("vault key must be 32 bytes")
    return key


def _key(purpose: str) -> bytes:
    return HKDF(hashes.SHA256(), 32, None, b"velaris-vault:" + purpose.encode()).derive(_master())


def derive_key(purpose: str) -> bytes:
    """A 32-byte key for `purpose` derived from the master key (e.g. to MAC a file); raises VaultKeyError without one."""
    return _key(purpose)


def is_sealed(blob: bytes) -> bool:
    return blob[:4] == MAGIC


def seal_bytes(data: bytes, purpose: str) -> bytes:
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(_key(purpose)).encrypt(nonce, data, purpose.encode())


def open_bytes(blob: bytes, purpose: str) -> bytes:
    if not is_sealed(blob) or len(blob) < 32:
        raise VaultError("not a sealed blob")
    try:
        return AESGCM(_key(purpose)).decrypt(blob[4:16], blob[16:], purpose.encode())
    except InvalidTag as e:
        raise VaultError("sealed blob failed authentication (tampered, wrong store or wrong key)") from e


def new_key() -> str:
    """A fresh master key, base64, for the operator to store outside VELARIS_DATA."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def write_sealed(path, data: bytes, purpose: str) -> None:
    """Atomically write `data` sealed (owner-only file)."""
    write_private(path, seal_bytes(data, purpose))


def read_sealed(path, purpose: str) -> bytes:
    """The plaintext of a sealed file; a file still in plaintext (written before sealing existed) is returned as is."""
    blob = read_private(path)
    return open_bytes(blob, purpose) if is_sealed(blob) else blob
