"""Column-level encryption at rest for the big sqlite stores (mail, chat, memory, docs), decision D4 (KAN-167).

  seal(value, purpose, bind)  "vlv2:" (with `bind`, see bind_for: table, column and row key in the authenticated data) or
                            "vlv1:" + base64(AES-256-GCM, key outside VELARIS_DATA via velaris.core.vault); None stays None.
                            Everything else is encrypted, text that starts with "vlv1:" included. Empty text IS sealed, so
                            '' is never a valid plaintext in a sealed column. Anything that is not text raises TypeError.
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
import json
import logging
import re
import sqlite3
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union

from velaris.core import vault

logger = logging.getLogger("velaris.fieldseal")
PREFIX = "vlv1:"                # sealed for a purpose only (written before binding existed)
BOUND = "vlv2:"                 # sealed for a purpose AND one record (column + row id): not movable to another row
_WORD = re.compile(r"[\wऀ-ॿ஀-௿]+")
MAX_TOKENS = 5000


def is_sealed(v: Any) -> bool:
    """True for a STORED value in sealed format. Only ever ask this of what was read from a sealed column: never decide
    "already sealed" from user text (seal() encrypts everything it is given)."""
    return isinstance(v, str) and v.startswith((PREFIX, BOUND))


def bind_for(table: str, col: str, *parts: Any) -> str:
    """The record a sealed value belongs to: table, column and row key (several parts for a composite key). JSON-encoded, so
    ('a.b', 'c') and ('a', 'b.c') differ; versioned ('b2') so a later encoding can be told apart."""
    return "b2:" + json.dumps([table, col, *map(str, parts)], separators=(",", ":"), ensure_ascii=True)


def seal(v: Any, purpose: str, bind: Optional[str] = None) -> Any:
    """Seal text. With `bind` (see bind_for) the value opens only for that record; without it, for the purpose only. Text
    that merely looks sealed (starts with "vlv1:") is encrypted like any other text, so it reads back as it was written."""
    if v is None:
        return None
    if not isinstance(v, str):
        raise TypeError(f"only text is sealed, not {type(v).__name__}")
    blob = vault.seal_bytes(v.encode("utf-8"), purpose, bind)
    return (PREFIX if bind is None else BOUND) + base64.b64encode(blob).decode("ascii")


def _blob(v: str) -> Optional[bytes]:
    """The sealed blob inside a stored value, or None when `v` is not in sealed format (plaintext that happens to start with
    the prefix is not: it has no valid base64 body with the vault magic)."""
    try:
        raw = base64.b64decode(v[len(PREFIX):], validate=True)
    except ValueError:
        return None
    return raw if vault.is_sealed(raw) else None


def unseal(v: Any, purpose: str, bind: Optional[str] = None) -> Any:
    """The plaintext. With `bind`, a value sealed for another record (moved between rows) raises vault.VaultError, and a
    value sealed without a binding (vlv1) is judged like plaintext: refused outside the migration window."""
    if v is None:
        return None
    raw = _blob(v) if is_sealed(v) else None
    if raw is None:
        return vault.legacy_plaintext(v, f"a {purpose} value of type {type(v).__name__}")
    if vault.is_bound(raw) and bind is None:
        raise vault.VaultError("sealed value is bound to a record and none was given")
    return vault.open_bytes(raw, purpose, bind).decode("utf-8")


class RowKey:
    """How a table's rows name themselves: `table`, the key `cols`, and optionally `when(values)` to tell tables with the same
    key columns apart (chat messages and ai_drafts both have `id`: one is an integer, the other a hex string)."""

    def __init__(self, table: str, cols: Sequence[str], when: Optional[Callable[[Sequence[Any]], bool]] = None) -> None:
        self.table, self.cols, self.when = table, tuple(cols), when


def row_class(purpose: str, cols: Iterable[str], keys: Union[str, Sequence[RowKey]], key: Sequence[str] = ("id",)) -> type:
    """sqlite3.Row subclass that unseals `cols` on read, bound to the row. `keys` is the table name (key columns `key`) or a
    list of RowKey for a connection that reads several tables; a row must carry its key columns (SELECT them)."""
    sealed = frozenset(cols)
    specs = [RowKey(keys, key)] if isinstance(keys, str) else list(keys)

    class SealedRow(sqlite3.Row):
        def _bind(self, col: str) -> str:
            have = set(self.keys())
            for sp in specs:
                if have.issuperset(sp.cols):
                    vals = [sqlite3.Row.__getitem__(self, k) for k in sp.cols]
                    if sp.when is None or sp.when(vals):
                        return bind_for(sp.table, col, *vals)
            raise vault.VaultError(f"a row with sealed column {col!r} must also select its key")

        def __getitem__(self, name):
            v = super().__getitem__(name)
            if isinstance(name, int):
                name = self.keys()[name]
            if name not in sealed or v is None:
                return v
            return unseal(v, purpose, self._bind(name))

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


class Migrated(int):
    """seal_existing's result: the number of rows changed; `.failed` lists keys of rows that could not be migrated."""
    failed: List[Any]


def seal_existing(conn: sqlite3.Connection, table: str, cols: List[str], purpose: str, key: Union[str, Sequence[str]] = "id",
                  batch: int = 500) -> Migrated:
    """Seal and bind to the row every value of `table` that is plaintext (old releases) or vlv1 (sealed before binding).
    `key` names the row (what row_class reads back). Anything not already bound needs the one-time migration window
    (vault.legacy_plaintext), except empty strings, which carry no data. A vlv1 value is verified by opening it; a value that
    does not open is left as it is and reported in `.failed` (one bad row never stops the rest). Ciphertext is only ever
    re-sealed here, never from user text."""
    keys = [key] if isinstance(key, str) else list(key)
    where = " OR ".join(f"({c} IS NOT NULL AND {c} NOT LIKE '{BOUND}%')" for c in cols)
    changed, failed, last = 0, [], None
    n = len(keys)
    tup = f"({', '.join(keys)})"
    while True:
        cur = conn.cursor()
        cur.row_factory = None                          # raw tuples: stored values as they are, sealed or not
        after = f" AND {tup} > ({', '.join('?' * n)})" if last else ""    # keyset paging: a row that failed is not asked for again
        rows = cur.execute(f"SELECT {', '.join(keys)}, {', '.join(cols)} FROM {table} WHERE ({where}){after} "
                           f"ORDER BY {', '.join(keys)} LIMIT {int(batch)}", last or ()).fetchall()
        if not rows:
            break
        last = rows[-1][:n]
        if any(v != "" for r in rows for v in r[n:] if v is not None):
            vault.legacy_plaintext(None, f"{len(rows)}+ rows of {table}")     # never bless planted values by sealing them
        for r in rows:
            try:
                vals = []
                for c, v in zip(cols, r[n:]):
                    raw = _blob(v) if is_sealed(v) else None
                    if raw is not None:
                        v = vault.open_bytes(raw, purpose).decode("utf-8")       # vlv1 (unbound): verified by opening it
                    vals.append(seal(v, purpose, bind_for(table, c, *r[:n])))
            except (vault.VaultError, UnicodeDecodeError) as e:
                logger.warning("%s row %s not migrated: %s", table, r[:n], e)
                failed.append(r[:n])
                continue
            sets = ", ".join(f"{c}=?" for c in cols)
            conn.execute(f"UPDATE {table} SET {sets} WHERE " + " AND ".join(f"{k}=?" for k in keys), (*vals, *r[:n]))
            changed += 1
        conn.commit()
    if changed:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
    out = Migrated(changed)
    out.failed = failed
    if failed:
        logger.warning("%s: %d row(s) could not be migrated", table, len(failed))
    return out
