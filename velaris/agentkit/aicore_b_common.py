"""Shared plumbing for the _ai_core agents EAC_AUDIT..VPSE_SCENARIO (lane "aicore_b").

Nothing here is an agent. It holds what three or more of those agents need:
structured results, input checks, owner-only state files, the list of agents
that exist on disk, and one guarded way to ask a model for JSON.

ponytail: overlaps aicore_a_common (written in parallel by another lane);
merge the two once both lanes have landed.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from velaris.agents import department_dirs
from velaris.intel import guard
from velaris.intel.llm import LLM, LLMError, extract_json
from velaris.intel.paths import agent_dir

logger = logging.getLogger("velaris.agentkit.aicore_b")

VERSION = "1.0.0"
MAX_TEXT = 20_000          # longest caller-supplied text any of these agents will process
_MODEL_ENV = ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK")


# ---- results -----------------------------------------------------------------

def ok(**fields: Any) -> Dict[str, Any]:
    return {"status": "ok", **fields}


def fail(status: str, reason: str, **fields: Any) -> Dict[str, Any]:
    """A non-ok result. `status` says what kind (invalid_input, denied, ...), `reason` says why."""
    return {"status": status, "reason": reason, **fields}


def invalid(reason: str, **fields: Any) -> Dict[str, Any]:
    return fail("invalid_input", reason, **fields)


def health(name: str, **fields: Any) -> Dict[str, Any]:
    return {"agent": name, "status": "ok", "version": VERSION, **fields}


# ---- input checks ------------------------------------------------------------

def number(value: Any) -> Optional[float]:
    """The value as a finite float, or None. Booleans and numeric strings are not numbers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def numbers(values: Any, minimum: int = 1) -> Optional[List[float]]:
    """A list of at least `minimum` finite numbers, or None."""
    if not isinstance(values, (list, tuple)) or len(values) < minimum:
        return None
    out = [number(v) for v in values]
    return None if any(v is None for v in out) else out  # type: ignore[return-value]


def ident(value: Any, max_len: int = 200) -> Optional[str]:
    """A usable identifier: a non-empty string (stripped) of sane length, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= max_len else None


def text(value: Any, max_len: int = MAX_TEXT) -> Optional[str]:
    """Non-empty text within the size cap, or None."""
    return ident(value, max_len)


def dig(record: Any, path: str) -> Tuple[bool, Any]:
    """Look up a dotted path in nested dicts. Returns (found, value)."""
    cur = record
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def known_agents() -> Dict[str, str]:
    """{agent name: department} for every departments/<dept>/<AGENT>/main.py on disk."""
    return {a.name: d.name for d in department_dirs() for a in d.iterdir() if (a / "main.py").exists()}


# ---- state -------------------------------------------------------------------

def peek_dir(agent: str) -> Path:
    """Where an agent's state lives, WITHOUT creating it (reads must not leave directories behind)."""
    return Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris") / "agents" / agent


class JsonState:
    """One JSON document under agent_dir(agent), owner-only, replaced atomically.

    The path is resolved on every access, so the file follows VELARIS_DATA, and
    nothing is created on disk until the first save. A file that no longer
    parses is moved aside (never overwritten) and the agent starts from `default`.
    ponytail: one lock per process, no cross-process file lock; move to SQLite
    if several processes ever write the same agent's state.
    """

    def __init__(self, agent: str, filename: str, default: Optional[Dict[str, Any]] = None) -> None:
        self._agent, self._filename = agent, filename
        self._default = default or {}
        self._lock = threading.RLock()

    def load(self) -> Dict[str, Any]:
        path = peek_dir(self._agent) / self._filename
        with self._lock:
            if not path.exists():
                return json.loads(json.dumps(self._default))
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("state file is not a JSON object")
                return data
            except (OSError, ValueError) as e:
                aside = path.with_suffix(path.suffix + ".corrupt")
                logger.warning("Unreadable state %s moved to %s: %s", path, aside, e)
                os.replace(path, aside)
                return json.loads(json.dumps(self._default))

    def save(self, data: Dict[str, Any]) -> None:
        path = agent_dir(self._agent) / self._filename
        tmp = path.with_suffix(path.suffix + ".tmp")
        with self._lock:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, sort_keys=True, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)

    def update(self, change: Callable[[Dict[str, Any]], Any]) -> Any:
        """Load, let `change` mutate the document, save. Returns what `change` returned."""
        with self._lock:
            data = self.load()
            result = change(data)
            self.save(data)
            return result


_append_lock = threading.Lock()


def append_line(path: Path, record: Dict[str, Any]) -> None:
    """Append one JSON line to an owner-only file."""
    with _append_lock:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())


def read_lines(path: Path) -> List[Dict[str, Any]]:
    """Every parseable JSON line of a file; a torn last line is skipped with a warning."""
    if not path.exists():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            out.append(json.loads(line))
        except ValueError as e:
            logger.warning("Skipping unreadable line %s of %s: %s", n, path, e)
    return out


# ---- models ------------------------------------------------------------------

def model_or_none(llm: Optional[LLM]) -> Optional[LLM]:
    """The model gateway to use: the one passed in, else the real one if a model is configured."""
    if llm is not None:
        return llm
    return LLM() if any(os.environ.get(k) for k in _MODEL_ENV) else None


NOT_CONFIGURED = "no model is configured (set VELARIS_MODEL or a provider key, or pass llm=)"


def ask_json(llm: LLM, instruction: str, outside_text: str, *, purpose: str) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """Ask a model for JSON about a piece of outside text. Returns (data, error_result).

    The outside text is screened first (a blocked scan is never sent), fenced so
    it cannot give instructions, and stripped of secrets and personal
    identifiers. The reply is only parsed here: the caller must validate it.
    """
    scan = guard.scan(outside_text, source=purpose)
    if scan.blocked:
        return None, fail("blocked", "the text looks like an attempt to instruct the model; not sent",
                          findings=[f["rule"] for f in scan.findings])
    masked, _ = guard.redact(outside_text)
    preamble, fenced = guard.wrap(masked)
    try:
        reply = llm.complete(f"{instruction}\n\n{preamble}\n{fenced}\n\nReply with JSON only.", purpose=purpose)
        return extract_json(reply.text), None
    except LLMError as e:
        logger.warning("%s: model call failed: %s", purpose, e)
        return None, fail("model_error", str(e))
