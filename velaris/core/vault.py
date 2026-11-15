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

Plaintext where a sealed value is expected is REFUSED (PlaintextRefused): otherwise anyone who can write the data
directory could replace a sealed file with a forged plaintext one and have it trusted (downgrade). Files written before
sealing existed are migrated once, in a window that only the key holder can open:
  1. python -m velaris.core.vault start-migration [hours]   writes <VELARIS_DATA>/.vault_plaintext_open: an expiry
     time MAC'd with a key derived from the master key (default 24 h, at most 168 h). Nobody who can only write the
     data directory can forge or extend it.
  2. start the services with VELARIS_VAULT_ALLOW_PLAINTEXT=1: stores read plaintext and seal it at once.
  3. python -m velaris.core.vault end-migration             deletes the token.
Both the switch AND a valid unexpired token are required; with either missing, plaintext is refused. The closed state is
the ABSENCE of a token that only the key can create, so deleting files cannot reopen anything; the one thing a data
directory writer can do is replay a copy of a token taken during an earlier window, until that token's expiry.
Every store goes through legacy_plaintext() for this, none decides on its own.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import stat
import sys
from pathlib import Path
from typing import Iterable, Iterator

from velaris.intel.paths import read_private, write_private
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"VLV1"
ALLOW_PLAINTEXT = "VELARIS_VAULT_ALLOW_PLAINTEXT"
OPEN_TOKEN = ".vault_plaintext_open"
MAX_WINDOW_HOURS = 168
logger = logging.getLogger("velaris.vault")


class VaultError(ValueError):
    """The blob cannot be opened (tampered, wrong store, wrong key)."""


class PlaintextRefused(VaultError):
    """A plaintext value where a sealed one is expected, outside the one-time migration window."""


def _data_dir() -> Path:
    return Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris")


def _token_mac(expires: int) -> str:
    return hmac.new(derive_key("plaintext-migration"), f"open|{expires}".encode(), hashlib.sha256).hexdigest()


def plaintext_allowed() -> bool:
    """True only inside the migration window: the env switch is set AND an unexpired, key-authenticated open token exists."""
    if os.environ.get(ALLOW_PLAINTEXT) != "1":
        return False
    try:
        tok = json.loads((_data_dir() / OPEN_TOKEN).read_text(encoding="utf-8"))
        expires = int(tok["expires"])
        return expires > time.time() and hmac.compare_digest(_token_mac(expires), str(tok["mac"]))
    except (OSError, ValueError, KeyError, TypeError, VaultKeyError):
        return False                                        # no token, forged token, no key: closed


def start_plaintext_migration(hours: float = 24) -> Path:
    """Open the migration window for this data directory (needs the master key)."""
    expires = int(time.time() + min(float(hours), MAX_WINDOW_HOURS) * 3600)
    path = _data_dir() / OPEN_TOKEN
    write_private(path, json.dumps({"expires": expires, "mac": _token_mac(expires)}).encode())
    return path


def legacy_plaintext(value, what: object):
    """`value` (plaintext found where `what` should be sealed) if the migration window is open, else PlaintextRefused."""
    if not plaintext_allowed():
        raise PlaintextRefused(f"{what} is not sealed; plaintext is refused (migrate once with {ALLOW_PLAINTEXT}=1, "
                               "then `python -m velaris.core.vault end-migration`)")
    logger.warning("accepting plaintext for %s (migration window open)", what)
    return value


def end_plaintext_migration() -> None:
    """Close the migration window: remove the open token."""
    (_data_dir() / OPEN_TOKEN).unlink(missing_ok=True)


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
    """The plaintext of a sealed file; a plaintext file raises PlaintextRefused outside the migration window."""
    if is_stream(path):
        return b"".join(open_sealed_stream(path, purpose))
    blob = read_private(path)
    return open_bytes(blob, purpose) if is_sealed(blob) else legacy_plaintext(blob, path)


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


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["start-migration"]:
        print(f"plaintext migration open until: {start_plaintext_migration(float(sys.argv[2]) if len(sys.argv) > 2 else 24)}")
    elif cmd == ["end-migration"]:
        end_plaintext_migration()
        print("plaintext migration ended")
    else:
        sys.exit("usage: python -m velaris.core.vault start-migration [hours] | end-migration")
