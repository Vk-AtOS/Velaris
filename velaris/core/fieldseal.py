"""Column-level encryption at rest for the big sqlite stores (mail, chat, memory, docs), decision D4 (KAN-167).

  seal(value, purpose)      "vlv1:" + base64(AES-256-GCM, key outside VELARIS_DATA via velaris.core.vault); None and an
                            already sealed value are returned unchanged. Empty text IS sealed, so '' is never a valid
                            plaintext in a sealed column. Anything else that is not text raises TypeError.
  unseal(value, purpose)    the plaintext; None stays None; EVERYTHING else that is not a properly prefixed sealed text
                            (unprefixed text, '', bytes, int, float) raises vault.PlaintextRefused (a planted row must
                            not be trusted) unless the one-time migration window of velaris.core.vault is open.
  row_class(purpose, cols)  a sqlite3.Row subclass: reading row["body"] (or dict(row)) of a sealed column gives the
                            plaintext, so SELECT code does not change. Columns are matched by NAME.
  seal_existing(conn, table, cols, purpose, key)   one-off: seal plaintext values already stored, in batches, then
                            checkpoint the WAL and VACUUM so the old plaintext pages do not stay in the file. Outside
                            the migration window it raises PlaintextRefused for any non-empty plaintext; empty strings
                            carry no data and are sealed silently (older releases stored them unsealed).
  blind_tokens(text, purpose)  space-separated HMAC-SHA256 (truncated) of the words of `text`, for a search index that
                            holds no readable words (see mail/chat): exact-word search, no prefix or substring search.

A missing key raises VaultKeyError on every seal/unseal: the store fails closed. The purpose is authenticated, so a
value cannot be moved from one store to another. sqlite itself (indexes, FTS) never sees the plaintext of a sealed
column, so SQL cannot filter or sort by it: only identifiers and metadata stay in clear columns.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import sqlite3
from typing import Any, Iterable, List, Optional, Sequence, Union

from velaris.core import vault

PREFIX = "vlv1:"                # sealed for a purpose only (written before binding existed)
BOUND = "vlv2:"                 # sealed for a purpose AND one record (column + row id): not movable to another row
_WORD = re.compile(r"[\wऀ-ॿ஀-௿]+")
MAX_TOKENS = 5000


def is_sealed(v: Any) -> bool:
    return isinstance(v, str) and v.startswith((PREFIX, BOUND))


def bind_for(col: str, *parts: Any) -> str:
    """The record a sealed value belongs to: its column and its row id (or the parts of a composite key)."""
    return f"{col}#" + ".".join(str(p) for p in parts)


def seal(v: Any, purpose: str, bind: Optional[str] = None) -> Any:
    """Seal text. With `bind` (see bind_for) the value opens only for that record; without it, for the purpose only."""
    if v is None or is_sealed(v):
        return v
    if not isinstance(v, str):
        raise TypeError(f"only text is sealed, not {type(v).__name__}")
    blob = vault.seal_bytes(v.encode("utf-8"), purpose, bind)
    return (PREFIX if bind is None else BOUND) + base64.b64encode(blob).decode("ascii")


def unseal(v: Any, purpose: str, bind: Optional[str] = None) -> Any:
    """The plaintext. With `bind`, a value sealed for another record (moved between rows) raises vault.VaultError, and a
    value sealed without a binding (vlv1) is judged like plaintext: refused outside the migration window."""
    if v is None:
        return None
    if not is_sealed(v):
        return vault.legacy_plaintext(v, f"a {purpose} value of type {type(v).__name__}")
    if v.startswith(BOUND) and bind is None:
        raise vault.VaultError("sealed value is bound to a record and none was given")
    return vault.open_bytes(base64.b64decode(v[len(PREFIX):]), purpose, bind).decode("utf-8")


# How a row names itself, by the key columns it carries (first match wins). A SELECT of a sealed column must include them.
ROW_KEYS = (("id",), ("message_id", "version"), ("user_id", "channel_id", "topic"))


def row_class(purpose: str, cols: Iterable[str], keys: Iterable[Iterable[str]] = ROW_KEYS) -> type:
    """sqlite3.Row subclass that unseals `cols` on read, bound to the row's key (`keys`: column sets, first present wins)."""
    sealed, key_sets = frozenset(cols), tuple(tuple(k) for k in keys)

    class SealedRow(sqlite3.Row):
        def _bind(self, col: str) -> str:
            have = set(self.keys())
            for ks in key_sets:
                if have.issuperset(ks):
                    return bind_for(col, *(sqlite3.Row.__getitem__(self, k) for k in ks))
            raise vault.VaultError(f"a row with sealed column {col!r} must also select its key ({key_sets})")

        def __getitem__(self, key):
            v = super().__getitem__(key)
            if isinstance(key, int):
                key = self.keys()[key]
            if key not in sealed or v is None:
                return v
            return unseal(v, purpose, self._bind(key) if is_sealed(v) else None)

        def __iter__(self):
            return (self[i] for i in range(len(self.keys())))

    return SealedRow


PREFIXES = (3, 4, 6, 8)


def blind_tokens(text: str, purpose: str, prefixes: bool = False) -> str:
    """Opaque tokens, one per distinct word (lower-cased), for an index that can be searched but not read.

    With `prefixes` a word also yields tokens for its first 3, 4, 6 and 8 letters, so a query word of exactly those
    lengths (or a whole word) finds words that start with it ("piz" finds "pizza"); other lengths match whole words only."""
    key = vault.derive_key(f"blind:{purpose}")
    words = list(dict.fromkeys(w for w in _WORD.findall((text or "").lower()) if len(w) >= 2))[:MAX_TOKENS]
    pieces = [w for word in words for w in ([word] + ([word[:k] for k in PREFIXES if k < len(word)] if prefixes else []))]
    return " ".join(dict.fromkeys(hmac.new(key, w.encode(), hashlib.sha256).hexdigest()[:16] for w in pieces))


def blind_value(text: str, purpose: str) -> str:
    """One opaque, deterministic token for a whole value, usable for equality lookups (e.g. a normalised subject)."""
    return "bn1:" + hmac.new(vault.derive_key(f"blind:{purpose}"), (text or "").encode(), hashlib.sha256).hexdigest()[:32]


def blind_query(terms: List[str], purpose: str) -> List[str]:
    """Tokens to MATCH for the query words (each one a whole word, or a prefix of a length indexed with `prefixes`)."""
    return blind_tokens(" ".join(terms), purpose).split()


def seal_existing(conn: sqlite3.Connection, table: str, cols: List[str], purpose: str, key: Union[str, Sequence[str]] = "rowid",
                  batch: int = 500, bind: bool = True) -> int:
    """Seal (and, with `bind`, bind to the row) values already in `table`: plaintext of old releases and vlv1 values written
    before binding existed. `key` is the column, or columns, that name the row (what row_class reads back). Returns the
    number of rows changed. Anything that is not already bound needs the one-time migration window (vault.legacy_plaintext),
    except empty strings, which carry no data; a value is never blessed by being sealed."""
    keys = [key] if isinstance(key, str) else list(key)
    done = BOUND if bind else PREFIX
    where = " OR ".join(f"({c} IS NOT NULL AND {c} NOT LIKE '{done}%'" + ("" if bind else f" AND {c} NOT LIKE '{BOUND}%'") + ")" for c in cols)
    changed = 0
    while True:
        cur = conn.cursor()
        cur.row_factory = None                          # raw tuples: stored values as they are, sealed or not
        rows = cur.execute(f"SELECT {', '.join(keys)}, {', '.join(cols)} FROM {table} WHERE {where} LIMIT {int(batch)}").fetchall()
        if not rows:
            break
        n = len(keys)
        if any(v != "" for r in rows for v in r[n:] if v is not None):
            vault.legacy_plaintext(None, f"{len(rows)}+ rows of {table}")     # never bless planted values by sealing them
        for r in rows:
            vals = []
            for c, v in zip(cols, r[n:]):
                if is_sealed(v):
                    v = vault.open_bytes(base64.b64decode(v[len(PREFIX):]), purpose).decode("utf-8")   # unbound (vlv1): window only
                vals.append(seal(v, purpose, bind_for(c, *r[:n]) if bind else None))
            sets = ", ".join(f"{c}=?" for c in cols)
            conn.execute(f"UPDATE {table} SET {sets} WHERE " + " AND ".join(f"{k}=?" for k in keys), (*vals, *r[:n]))
        conn.commit()
        changed += len(rows)
    if changed:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
    return changed
