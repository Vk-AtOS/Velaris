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
from typing import Iterable, Iterator

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
    if is_stream(path):
        return b"".join(open_sealed_stream(path, purpose))
    blob = read_private(path)
    return open_bytes(blob, purpose) if is_sealed(blob) else blob


# ---- large files: chunked sealing (audio uploads of up to 200 MB must not be held in memory) -------------------------------
STREAM_MAGIC = b"VLS1"
CHUNK = 1 << 20


def _stream_aad(purpose: str, index: int, last: bool) -> bytes:
    return purpose.encode() + b"|" + index.to_bytes(8, "big") + (b"L" if last else b"M")     # no reordering, no truncation


def write_sealed_stream(path, chunks: Iterable[bytes], purpose: str) -> int:
    """Seal an iterable of byte chunks (any sizes) into `path` as VLS1 records of at most 1 MiB, atomically and owner-only.
    Each record is authenticated with its position and whether it is the last, so cutting the file short or swapping
    records fails on reading. Returns the number of plaintext bytes."""
    aead, target, total = AESGCM(_key(purpose)), Path(path), 0
    tmp = target.with_name(f".{target.name}.{os.urandom(6).hex()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(STREAM_MAGIC)
            index = 0
            buf = bytearray()

            def emit(block: bytes, last: bool) -> None:
                nonlocal index
                nonce = os.urandom(12)
                ct = aead.encrypt(nonce, block, _stream_aad(purpose, index, last))
                f.write(nonce + len(ct).to_bytes(4, "big") + ct)
                index += 1

            for part in chunks:
                total += len(part)
                buf += part
                while len(buf) > CHUNK:                       # keep at least one byte back: the last record must be marked
                    emit(bytes(buf[:CHUNK]), False)
                    del buf[:CHUNK]
            emit(bytes(buf), True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return total


def open_sealed_stream(path, purpose: str) -> Iterator[bytes]:
    """The plaintext of a VLS1 file, chunk by chunk. Raises VaultError on tamper, truncation, wrong store or key."""
    aead = AESGCM(_key(purpose))
    with open(path, "rb") as f:
        if f.read(4) != STREAM_MAGIC:
            raise VaultError("not a sealed stream")
        index, seen_last = 0, False
        while True:
            head = f.read(16)
            if not head:
                break
            if seen_last or len(head) < 16:
                raise VaultError("sealed stream has data after its last record or a torn record")
            nonce, n = head[:12], int.from_bytes(head[12:], "big")
            ct = f.read(n)
            if len(ct) != n or n > CHUNK + 16:
                raise VaultError("sealed stream is truncated")
            for last in (False, True):
                try:
                    yield aead.decrypt(nonce, ct, _stream_aad(purpose, index, last))
                    seen_last = last
                    break
                except InvalidTag:
                    continue
            else:
                raise VaultError("sealed stream failed authentication (tampered, reordered or wrong store/key)")
            index += 1
        if not seen_last:
            raise VaultError("sealed stream is truncated (no final record)")


def is_stream(path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == STREAM_MAGIC
    except OSError:
        return False


def unseal_to_file(path, purpose: str, dest) -> None:
    """Write the plaintext of a sealed file (either format) to `dest`, owner-only, without holding it in memory."""
    if not is_stream(path):
        write_private(dest, read_sealed(path, purpose))
        return
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        for block in open_sealed_stream(path, purpose):
            f.write(block)
