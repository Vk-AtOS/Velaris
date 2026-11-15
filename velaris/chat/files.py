"""Attachments: stored by the sha256 of their bytes, sniffed rather than trusted, owner-only on disk.

Rules: at most Limits.max_file_bytes; the type is worked out from the bytes (magic numbers; OOXML by
the parts inside the zip; text only if it is valid UTF-8 without NUL) and must be on the allow-list;
a declared content type that disagrees is refused. HTML, SVG, scripts and archives are not on it.
A file may be downloaded by whoever uploaded it, and by members of a channel holding a live message
that references it. It is always served as an attachment with nosniff.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from velaris.chat.core import ChatCore
from velaris.chat.errors import ChatError
from velaris.core import fieldseal, vault
from velaris.core.access import Caller
from velaris.intel.paths import private_dir, read_private, write_private

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
ALLOWED = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf",
                     "text/plain", "text/csv", DOCX, XLSX, PPTX})
_OOXML = (("word/document.xml", DOCX), ("xl/workbook.xml", XLSX), ("ppt/presentation.xml", PPTX))
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def sniff(data: bytes, name: str = "") -> Optional[str]:
    """The content type the bytes really are, or None if it is not a type chat accepts."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        except (zipfile.BadZipFile, ValueError, OSError):
            return None
        return next((t for part, t in _OOXML if part in names), None)
    if data and b"\x00" not in data[:8192]:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return "text/csv" if name.lower().endswith(".csv") else "text/plain"
    return None


NAME_SEAL = "chat:file-name"     # the file name column is sealed at rest (KAN-167); the blob is sealed per content hash


def file_name(stored: Any) -> str:
    """The plaintext file name of a `files.name` value (plaintext is refused outside the migration window)."""
    return fieldseal.unseal(stored, NAME_SEAL)


def clean_name(name: Any) -> str:
    base = re.sub(r"[\x00-\x1f\x7f/\\]", "", str(name or "")).strip().lstrip(".")
    return (base or "file")[:120]


def _blob_purpose(digest: str) -> str:
    return f"chat:blob:{digest}"      # bound to the content hash: a blob copied over another's path does not open


class FilesMixin(ChatCore):
    def _blob(self, digest: str) -> Path:
        root = private_dir(self.store.path.parent / "blobs")
        return private_dir(root / digest[:2]) / digest

    def upload(self, caller: Caller, name: Any, declared: Optional[str], data: bytes) -> Dict[str, Any]:
        caller = self._enter(caller)
        if not isinstance(data, bytes) or not data:
            raise ChatError(400, "empty_file", "the file is empty")
        if len(data) > self.limits.max_file_bytes:
            raise ChatError(413, "file_too_large", f"files may be at most {self.limits.max_file_bytes} bytes")
        name = clean_name(name)
        found = sniff(data, name)
        declared = (declared or "").split(";")[0].strip().lower() or None
        if found not in ALLOWED:
            self._denied(caller, "upload", "type not allowed")
            raise ChatError(415, "unsupported_type", "this kind of file cannot be attached")
        if declared and declared not in (found, "application/octet-stream") and not (declared.startswith("text/") and found.startswith("text/")):
            self._denied(caller, "upload", "type mismatch")
            raise ChatError(415, "type_mismatch", "the file is not the type it says it is")
        self._spend(caller, 2)
        digest = hashlib.sha256(data).hexdigest()
        with self._write() as db:
            db.execute("INSERT OR IGNORE INTO files VALUES(?,?,?,?,?,?,?)",
                       (digest, caller.org, len(data), found, fieldseal.seal(name, NAME_SEAL), caller.id, self.clock()))
            self._audit("file.upload", caller.id, caller.org, file=digest, bytes=len(data), type=found)
            if not self._blob(digest).exists():
                vault.write_sealed(self._blob(digest), data, _blob_purpose(digest))
        return {"hash": digest, "size": len(data), "content_type": found, "name": name}

    def download(self, caller: Caller, digest: Any) -> Tuple[Dict[str, Any], bytes]:
        caller = self._enter(caller)
        meta = self.store.one("SELECT * FROM files WHERE hash=? AND org=? ORDER BY created_at LIMIT 1",
                              (digest, caller.org)) if isinstance(digest, str) and _HASH.match(digest) else None
        allowed = meta is not None and (
            self.store.one("SELECT 1 FROM files WHERE hash=? AND org=? AND uploader=?", (digest, caller.org, caller.id)) is not None
            or self.store.one(
                "SELECT 1 FROM messages m JOIN members mb ON mb.channel_id=m.channel_id WHERE mb.user_id=? AND m.org=? "
                "AND m.deleted_at IS NULL AND m.erased=0 AND m.attachments LIKE ? LIMIT 1",
                (caller.id, caller.org, f'%"{digest}"%')) is not None)
        if not allowed:
            if meta is not None:
                self._denied(caller, "download", "not uploader or channel member")
            raise ChatError(404, "no_such_file", "no such file")
        try:
            path = self._blob(digest)
            raw = read_private(path)
        except OSError:
            raise ChatError(404, "no_such_file", "no such file") from None
        data = vault.open_bytes(raw, _blob_purpose(digest)) if vault.is_sealed(raw) else vault.legacy_plaintext(raw, path)
        if hashlib.sha256(data).hexdigest() != digest:       # a blob swapped or damaged on disk is never served
            raise ChatError(404, "no_such_file", "no such file")
        if not vault.is_sealed(raw):                         # migration window only: seal the old plaintext blob now
            vault.write_sealed(path, data, _blob_purpose(digest))
        return {"hash": digest, "size": meta["size"], "content_type": meta["ctype"], "name": file_name(meta["name"])}, data
