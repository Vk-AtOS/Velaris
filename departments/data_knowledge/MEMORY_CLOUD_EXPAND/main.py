"""MEMORY_CLOUD_EXPAND: move a scope's memories between Velaris installations as a checked file.

There is no cloud service behind this agent and it opens no connection. What it
does is the part that can be exact:

  export_scope(scope)       writes every currently valid memory of the scope to a
                            bundle file in this agent's directory: one JSON header
                            (scope, count, sha256 of the body, and an HMAC-SHA256 of
                            the rest of the header) and one JSON line per memory.
  verify_bundle(path)       checks the HMAC, the checksum and the count.
  import_bundle(path, ...)  verifies, then replays each memory through
                            MemoryStore.remember(), so imported text is screened,
                            masked and deduplicated like any other.

Bundles are read only from this agent's own directory (a bare file name, or a path
that resolves inside it; symbolic links are refused), and only bundles signed with this
installation's key (agent_dir/bundle.key) are accepted: to move a bundle between
installations, both must hold the same key file. Exporting and importing a scope need a
governance admin of the organisation the scope belongs to (velaris.core.access.may_write_scope).
  sync_meta / meta          a persistent index of what has been placed where,
                            kept by the operator who carries the bundle.

Copying the bundle to another machine or bucket is the operator's step.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit import infra_memory
from velaris.agentkit.infra_store import State, audit, fail, invalid, is_json, is_name, ok
from velaris.core.access import GOVERNANCE_ADMINS, check_caller, may_write_scope
from velaris.intel.memory import MemoryStore
from velaris.intel.paths import agent_dir, load_or_create_key, read_private, write_private

NAME = "MEMORY_CLOUD_EXPAND"
MAX_BUNDLE_BYTES = 64 * 1024 * 1024


def _mac(header: Dict[str, Any]) -> str:
    """HMAC-SHA256 over every header field but "hmac" (the header carries the body's sha256)."""
    unsigned = {k: v for k, v in header.items() if k != "hmac"}
    key = load_or_create_key(agent_dir(NAME) / "bundle.key", 32)
    return hmac.new(key, json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()


def _bundle_path(path: Any) -> Tuple[Optional[Path], str]:
    """The bundle `path` names inside this agent's directory, or (None, why it is refused)."""
    if not isinstance(path, (str, os.PathLike)) or not str(path) or "\x00" in str(path):
        return None, "path must name a bundle file"
    home = agent_dir(NAME).resolve()
    p = Path(path) if Path(path).is_absolute() else home / path
    if p.is_symlink():
        return None, "bundle path is a symbolic link"
    if p.resolve().parent != home:
        return None, "bundles are read only from this agent's own directory"
    return p, ""


def _read_bundle(path: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str]:
    """(header, records, problem). problem is "" only when the HMAC, checksum and count match."""
    p, problem = _bundle_path(path)
    if p is None:
        return {}, [], problem
    try:
        if os.lstat(p).st_size > MAX_BUNDLE_BYTES:
            return {}, [], "bundle is larger than 64 MB"
        head, _, body = read_private(p).decode("utf-8").partition("\n")     # never follows a link
        header = json.loads(head)
        records = [json.loads(line) for line in body.splitlines() if line.strip()]
    except (OSError, TypeError, ValueError) as e:
        return {}, [], f"unreadable bundle: {type(e).__name__}"
    if not isinstance(header, dict) or not isinstance(header.get("hmac"), str) \
            or not hmac.compare_digest(header["hmac"], _mac(header)):
        return {}, [], "signature mismatch: the bundle was not made by this installation's key, or was altered"
    if header.get("sha256") != hashlib.sha256(body.encode()).hexdigest():
        return {}, [], "checksum mismatch: the bundle was altered or truncated"
    if header.get("count") != len(records) or not all(isinstance(r, dict) and isinstance(r.get("text"), str) for r in records):
        return {}, [], "record count or shape does not match the header"
    return header, records, ""


class MEMORY_CLOUD_EXPANDAgent:
    def __init__(self) -> None:
        self.name = NAME
        self.llm = None                 # optional velaris.intel.llm.LLM used when importing
        self._state = State(NAME, "index.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def sync_meta(self, meta: dict) -> Dict[str, Any]:
        """Merge entries into the placement index ({key: JSON value})."""
        if not isinstance(meta, dict) or not all(isinstance(k, str) and k for k in meta) or not is_json(meta):
            return invalid("meta must be a JSON object with non-empty string keys")
        size = self._state.change(lambda d: (d.setdefault("index", {}).update(meta), len(d["index"]))[1])
        return ok(entries=size)

    def meta(self) -> Dict[str, Any]:
        return dict(self._state.load().get("index", {}))

    @staticmethod
    def _scope_refusal(change: str, scope: str) -> Optional[Dict[str, Any]]:
        """None if the current caller may export or import `scope`, else why not (traced)."""
        caller, refused = check_caller(NAME, change, {"scope": scope}, roles=GOVERNANCE_ADMINS)
        if refused:
            return refused
        if not may_write_scope(caller, scope):
            audit(NAME, f"{change}.refused", {"scope": scope, "caller": caller.id})
            return fail("denied", f"{caller.id} may not use scope {scope!r}: it belongs to another organisation")
        return None

    def export_scope(self, scope: str, bundle: str = "") -> Dict[str, Any]:
        if not infra_memory.is_scope(scope) or (bundle and not is_name(bundle, 80)):
            return invalid("scope must be a name and bundle a plain file name")
        refused = self._scope_refusal("export", scope)
        if refused:
            return refused
        try:
            # ponytail: MemoryStore has no public "list a scope" call, so this reads its
            # private _rows(). Replace with the public method once the core has one.
            rows = MemoryStore(self.llm)._rows(scope, None)
        except (sqlite3.Error, OSError) as e:
            return fail("error", f"long-term memory unavailable: {type(e).__name__}")
        body = "".join(json.dumps({"text": r["text"], "source": r["source"], "created_at": r["created_at"]},
                                  sort_keys=True) + "\n" for r in sorted(rows, key=lambda r: (r["created_at"], r["id"])))
        digest = hashlib.sha256(body.encode()).hexdigest()
        header = {"format": "velaris-memory-bundle-1", "scope": scope, "count": len(rows), "sha256": digest,
                  "exported_at": time.time()}
        header["hmac"] = _mac(header)
        path = agent_dir(NAME) / (bundle or f"bundle-{digest[:16]}.jsonl")
        write_private(path, json.dumps(header, sort_keys=True) + "\n" + body)
        self.sync_meta({path.name: {"scope": scope, "count": len(rows), "sha256": digest, "location": "local"}})
        return ok(path=str(path), count=len(rows), sha256=digest)

    def verify_bundle(self, path: str) -> Dict[str, Any]:
        header, records, problem = _read_bundle(path)
        if problem:
            return fail("rejected", problem, valid=False)
        return ok(valid=True, scope=header.get("scope"), count=len(records), sha256=header["sha256"])

    def import_bundle(self, path: str, scope: str) -> Dict[str, Any]:
        """Verify a bundle and store its memories under `scope` (which may differ from the exported one)."""
        if not infra_memory.is_scope(scope):
            return invalid("scope must be a non-empty string", imported=0)
        refused = self._scope_refusal("import", scope)
        if refused:
            return {**refused, "imported": 0}
        header, records, problem = _read_bundle(path)
        if problem:
            return fail("rejected", problem, imported=0)
        result = infra_memory.remember(self.llm, [r["text"] for r in records], scope, f"bundle:{header['sha256'][:16]}")
        return {**result, "records": len(records)}
