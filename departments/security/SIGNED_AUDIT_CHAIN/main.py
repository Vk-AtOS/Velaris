# ================================================================================

"""Signed audit chain: tamper-evident append-only log of events, linked by hashes and signed with HMAC.
SignedAuditChain.append_event(actor, action, details) appends a signed entry holding a UTC timestamp,
actor, action, details and the hash of the previous line, under a file lock, and updates a signed
head (entry count plus last-line hash). verify_chain() returns True only if every line is signed
and linked and the signed head matches the end, so edits, reordering and truncation are detected.
State: <VELARIS_DATA>/agents/SIGNED_AUDIT_CHAIN/chain.log, chain.head and chain.key (owner-only
files; key is 64 bytes, created on first use). Failure: verify_chain never raises on bad data and
returns False; append_event raises OSError or TypeError on unwritable files or details that are not
JSON serializable, and has no caller check.
"""
import os
import json
import base64
import hmac
import fcntl
import hashlib
from datetime import datetime

from velaris.intel.paths import agent_dir, load_or_create_key, open_private, write_private

class SignedAuditChain:
    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SIGNED_AUDIT_CHAIN"))
        self.CHAIN_PATH = os.path.join(self.AGENT_DIR, "chain.log")
        self.HEAD_PATH = os.path.join(self.AGENT_DIR, "chain.head")
        self.KEY_PATH = os.path.join(self.AGENT_DIR, "chain.key")
        # Signing key and chain are owner-only from the moment they exist.
        self.key = load_or_create_key(self.KEY_PATH, 64)
        open_private(self.CHAIN_PATH, "a").close()

    def _sign(self, entry_bytes: bytes) -> str:
        sig = hmac.new(self.key, entry_bytes, hashlib.sha256).digest()
        return base64.b64encode(sig).decode()

    def _head_sign(self, count: int, last: str) -> str:
        return self._sign(f"{count}:{last}".encode())

    def _read_head(self):
        """(count, last_line_hash) from the signed head file, or None when absent/forged."""
        try:
            with open_private(self.HEAD_PATH, "r") as f:
                count, last, sig = f.read().strip().split("|")
            return (int(count), last) if hmac.compare_digest(self._head_sign(int(count), last), sig) else None
        except (OSError, ValueError):
            return None

    def append_event(self, actor: str, action: str, details: dict):
        # flock: two processes appending at once would both chain onto the same previous line.
        with open_private(self.CHAIN_PATH + ".lock", "a") as lk:
            fcntl.flock(lk.fileno(), fcntl.LOCK_EX)
            try:
                lines = self._lines()
                entry = {
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "actor": actor,
                    "action": action,
                    "details": details,
                    # Hash of the previous line: removing or reordering an entry breaks every later one.
                    "prev": self._line_hash(lines[-1]) if lines else "",
                }
                entry_bytes = json.dumps(entry, sort_keys=True).encode()
                line = base64.b64encode(entry_bytes).decode() + "::" + self._sign(entry_bytes)
                with open_private(self.CHAIN_PATH, "a") as f:
                    f.write(line + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                # Signed head (count + hash of the newest line): removing lines from the END is detected.
                last = self._line_hash(line)
                write_private(self.HEAD_PATH, f"{len(lines) + 1}|{last}|{self._head_sign(len(lines) + 1, last)}")
            finally:
                fcntl.flock(lk.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _line_hash(line: str) -> str:
        return hashlib.sha256(line.strip().encode()).hexdigest()

    def _lines(self):
        with open_private(self.CHAIN_PATH, "r") as f:
            return [ln for ln in f.read().splitlines() if ln.strip()]

    def _last_line_hash(self) -> str:
        lines = self._lines()
        return self._line_hash(lines[-1]) if lines else ""

    def verify_chain(self) -> bool:
        """True only if every line is signed and linked and the signed head matches the end. Never raises on bad data."""
        try:
            lines = self._lines()
            prev = ""
            for line in lines:
                if "::" not in line:
                    return False
                b64entry, sig = line.strip().split("::", 1)
                entry_bytes = base64.b64decode(b64entry.encode())
                if not hmac.compare_digest(self._sign(entry_bytes), sig):
                    return False
                if json.loads(entry_bytes).get("prev") != prev:
                    return False
                prev = self._line_hash(line)
            head = self._read_head()
            if head is None:
                return not lines          # a chain with entries but no valid head was truncated or tampered with
            return head == (len(lines), prev)
        except (OSError, ValueError, TypeError, AttributeError):
            return False

# ================================================================================
