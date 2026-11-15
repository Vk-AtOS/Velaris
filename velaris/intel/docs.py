"""Company documents: read a file, cut it into passages that stand alone, find them, answer from them.

  ingest(name, bytes, scope)   1. the file is identified by its content, not its extension, and
                                  converted to markdown (PDF, Word, Excel, PowerPoint, CSV, HTML, text)
                               2. markdown is cut on headings; every passage carries its heading
                                  trail, and every table row carries its column names, so a passage
                                  still makes sense when it is the only thing retrieved
                               3. each passage is screened; one that reads like instructions to a
                                  model is kept on record but never retrieved
                               4. the file and each passage are stored under their sha256. The same
                                  file again is a no-op; a changed file closes the old version (it is
                                  kept, not deleted) and passages that did not change are not re-embedded
  search(query, scope)         meaning (embedding) and wording (BM25) ranked separately, then fused
  ask(question, scope)         a model answers from the retrieved passages only; code then removes
                               every sentence that does not cite a passage it was actually given

A scope is one company's (or one team's) library; nothing crosses scopes.
Office files are read with zipfile + defusedxml. PDF needs `pypdf` (text PDFs; scans have no text to read).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import math
import posixpath
import re
import sqlite3

from velaris.core.sqlite_util import connect as connect_db
import threading
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from defusedxml.ElementTree import fromstring as safe_xml

from velaris.intel import guard, trace
from velaris.intel.llm import LLM, LLMError, cosine
from velaris.intel.paths import data_dir
from velaris.intel.research_report import verify_report
from velaris.intel.web_markdown import chunk, html_to_markdown

logger = logging.getLogger("velaris.intel.docs")

MAX_BYTES = 50_000_000        # one file, as stored
MAX_MEMBER = 64_000_000       # one unpacked part of an Office file
MAX_UNPACKED = 256_000_000    # every part read from one Office file, together
MAX_MEMBERS = 10_000          # entries in one Office file's archive
MAX_CHUNKS = 5000             # per file
MAX_SLIDES = 2000             # per presentation
MAX_PDF_PAGES = 2000          # per PDF
MAX_CELLS = 5_000_000         # per workbook, counting the gaps a sparse row spans
CHUNK_CHARS = 2000
MAX_TEXT_CHARS = MAX_CHUNKS * CHUNK_CHARS      # text taken from one file; more could not be ingested anyway
RRF_K = 60

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


class DocError(RuntimeError):
    pass


class DocTooLarge(DocError):
    """The file breaks a size limit (a zip bomb, or simply too big). It is refused outright;
    no other converter is tried on it."""


class _Zip(zipfile.ZipFile):
    """An Office file opened with limits on how much it may unpack.

    Before anything is read: the number of entries, and each part's declared size against the
    per-part limit and what is left of the total. While reading: the bytes that actually come
    out are counted against the same two limits, so a part that declares a small size and
    unpacks to a large one is cut off at the limit, not trusted.
    """

    def __init__(self, data: bytes) -> None:
        super().__init__(io.BytesIO(data))
        self.unpacked = 0
        if len(self.infolist()) > MAX_MEMBERS:
            raise DocTooLarge(f"archive has {len(self.infolist())} entries (limit {MAX_MEMBERS})")

    def part(self, member: str) -> bytes:
        info = self.getinfo(member)
        if info.file_size > MAX_MEMBER:
            raise DocTooLarge(f"{member} is {info.file_size} bytes unpacked (limit {MAX_MEMBER})")
        if self.unpacked + info.file_size > MAX_UNPACKED:
            raise DocTooLarge(f"the file unpacks to more than {MAX_UNPACKED} bytes in total")
        body = bytearray()
        with self.open(info) as f:
            while block := f.read(1 << 20):
                body += block
                self.unpacked += len(block)
                if len(body) > MAX_MEMBER:
                    raise DocTooLarge(f"{member} unpacks to more than {MAX_MEMBER} bytes")
                if self.unpacked > MAX_UNPACKED:
                    raise DocTooLarge(f"the file unpacks to more than {MAX_UNPACKED} bytes in total")
        return bytes(body)


# ── converters: bytes -> markdown ────────────────────────────────────────────
def table(rows: List[List[str]]) -> str:
    """One paragraph per row, every value next to its column name, so any cut between rows is safe."""
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        return " | ".join(rows[0]) if rows else ""
    head = rows[0]
    name = lambda i: head[i].strip() if i < len(head) and head[i].strip() else f"column {i + 1}"  # noqa: E731
    return "\n\n".join("; ".join(f"{name(i)} = {v.strip()}" for i, v in enumerate(r) if v.strip()) for r in rows[1:])


def _text(data: bytes) -> str:
    # ponytail: UTF-8 and UTF-16 only. Old Windows-1252 / TSCII text files are refused rather
    # than guessed at; add a charset detector if such files turn up.
    try:
        return data.decode("utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    except UnicodeDecodeError as e:
        raise DocError("not a text file") from e


def _xml(z: _Zip, member: str) -> ET.Element:
    return safe_xml(z.part(member))      # defusedxml: entity declarations and external references are refused


def _wtext(el: ET.Element) -> str:
    return "".join((n.text or "") if n.tag == W + "t" else "\t" if n.tag == W + "tab" else
                   "\n" if n.tag == W + "br" else "" for n in el.iter()).strip()


def _docx(data: bytes) -> str:
    out: List[str] = []
    with _Zip(data) as z:
        body = _xml(z, "word/document.xml").find(W + "body")
    for el in (body if body is not None else []):
        if el.tag == W + "tbl":
            out.append(table([[_wtext(c) for c in r.findall(W + "tc")] for r in el.findall(W + "tr")]))
        elif el.tag == W + "p" and _wtext(el):
            style = el.find(f"{W}pPr/{W}pStyle")
            # ponytail: heading styles are recognised by their English ids ("Heading1", "Title").
            # A template with renamed styles reads as plain paragraphs; map styles.xml if that bites.
            m = re.fullmatch(r"(?:Heading|heading)\s?(\d)", style.get(W + "val", "") if style is not None else "")
            title = style is not None and style.get(W + "val") == "Title"
            listed = el.find(f"{W}pPr/{W}numPr") is not None or (
                style is not None and style.get(W + "val", "").startswith("List"))
            prefix = "#" * int(m.group(1)) + " " if m else "# " if title else "- " if listed else ""
            out.append(prefix + _wtext(el))
    return "\n\n".join(out)


def _part(folder: str, target: str) -> str:
    """Zip member a relationship Target points at ('/xl/x.xml' is absolute, 'x.xml' is relative to folder)."""
    return target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))


# Built-in number format ids that show a serial number as a date or a time (ECMA-376 part 1,
# 18.8.30, including the ids whose text depends on the locale). 22 shows both.
_DATE_FORMAT_IDS = {
    **dict.fromkeys((14, 15, 16, 17, 27, 28, 29, 30, 31, 36, 50, 51, 52, 53, 54, 57, 58), "date"),
    **dict.fromkeys((18, 19, 20, 21, 32, 33, 34, 35, 45, 46, 47, 55, 56), "time"), 22: "datetime"}


def _date_kind(code: str) -> str:
    """What a custom number format shows: 'date', 'time', 'datetime', or '' for an ordinary number."""
    # Drop what is not a format token: "quoted text", \x escapes, _x padding, *x fill, and [..]
    # sections (colours, conditions, locales) other than the elapsed-time tokens [h] [m] [s].
    bare = re.sub(r'"[^"]*"|\\.|_.|\*.|\[(?!(?:h+|m+|s+)\])[^\]]*\]', "", code.lower())
    clock = re.search(r"[hs]|am/pm|a/p", bare) is not None
    bare = bare.replace("am/pm", "").replace("a/p", "")
    calendar = re.search(r"[yd]", bare) is not None or ("m" in bare and not clock)   # m beside h or s is minutes
    return "datetime" if calendar and clock else "date" if calendar else "time" if clock else ""


def _date_styles(z: _Zip, member: str) -> List[str]:
    """For every cell style index (a cell's s="n"): 'date' | 'time' | 'datetime' | ''."""
    if member not in z.namelist():
        return []
    root = _xml(z, member)
    custom = {f.get("numFmtId"): _date_kind(f.get("formatCode", "")) for f in root.findall(f"{S}numFmts/{S}numFmt")}
    out: List[str] = []
    for xf in root.findall(f"{S}cellXfs/{S}xf"):
        fmt = xf.get("numFmtId", "0")
        out.append(custom[fmt] if fmt in custom else _DATE_FORMAT_IDS.get(int(fmt), "") if fmt.isdigit() else "")
    return out


def _serial_to_iso(text: str, kind: str, date1904: bool) -> str:
    """An Excel serial number as an ISO date, time or date-time; the text unchanged if it is not one."""
    try:
        serial = float(text)
        seconds = round(serial * 86400)
        if kind == "time":
            # ponytail: a time-only format on a value of a day or more is a duration ([h]:mm);
            # it stays a number. Render as ISO 8601 durations if anyone searches by them.
            return (datetime.min + timedelta(seconds=seconds)).time().isoformat() if 0 <= serial < 1 else text
        if date1904:
            if serial < 0:
                return text
            start = datetime(1904, 1, 1)
        elif serial >= 61:
            start = datetime(1899, 12, 30)   # Excel counts a 29 February 1900 that never happened
        elif 1 <= serial < 60:
            start = datetime(1899, 12, 31)
        else:
            return text                      # serial 0 and 60 are days that do not exist
        when = start + timedelta(seconds=seconds)
    except (ValueError, OverflowError):
        return text
    return when.date().isoformat() if kind == "date" else when.isoformat()


def _xlsx(data: bytes) -> str:
    out: List[str] = []
    chars = grid = 0    # a tiny sheet can point a million cells at one long shared string, or put
                        # one cell in the last column of every row
    with _Zip(data) as z:
        shared = (["".join(t.text or "" for t in si.iter(S + "t")) for si in _xml(z, "xl/sharedStrings.xml")]
                  if "xl/sharedStrings.xml" in z.namelist() else [])
        rel_nodes = list(_xml(z, "xl/_rels/workbook.xml.rels"))
        rels = {r.get("Id"): r.get("Target", "") for r in rel_nodes}
        styles = _date_styles(z, next((_part("xl", r.get("Target", "")) for r in rel_nodes
                                       if r.get("Type", "").endswith("/styles")), "xl/styles.xml"))
        workbook = _xml(z, "xl/workbook.xml")
        props = workbook.find(S + "workbookPr")
        date1904 = props is not None and props.get("date1904", "0").lower() in ("1", "true")
        for sheet in workbook.iter(S + "sheet"):
            target = rels.get(sheet.get(R_ID), "")
            if "worksheets/" not in target:
                continue
            rows: List[List[str]] = []
            for row in _xml(z, _part("xl", target)).iter(S + "row"):
                cells: Dict[int, str] = {}
                for c in row.findall(S + "c"):
                    letters = re.match(r"[A-Z]+", c.get("r", ""))
                    col = len(cells)
                    if letters:
                        col = -1
                        for ch in letters.group(0):
                            col = (col + 1) * 26 + ord(ch) - 65
                    v, kind, style = c.find(S + "v"), c.get("t"), c.get("s", "0")
                    shown_as = styles[int(style)] if style.isdigit() and int(style) < len(styles) else ""
                    cells[col] = ("".join(t.text or "" for t in c.iter(S + "t")) if kind == "inlineStr" else
                                  "" if v is None or v.text is None else
                                  shared[int(v.text)] if kind == "s" else
                                  _serial_to_iso(v.text, shown_as, date1904) if shown_as and kind in (None, "n")
                                  else v.text)
                if any(cells.values()):
                    chars += sum(len(v) for v in cells.values())
                    grid += max(cells) + 1
                    if chars > MAX_TEXT_CHARS or grid > MAX_CELLS:
                        raise DocTooLarge(f"workbook holds more than {MAX_TEXT_CHARS} characters of cell "
                                          f"text or spans more than {MAX_CELLS} cells")
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            if rows:
                out.append(f"## {sheet.get('name', 'Sheet')}\n\n{table(rows)}")
    return "\n\n".join(out)


def _pptx(data: bytes) -> str:
    out: List[str] = []
    with _Zip(data) as z:
        # Shown order is the presentation's slide id list, each id resolved through its relationship.
        rels = ({r.get("Id"): r.get("Target", "") for r in _xml(z, "ppt/_rels/presentation.xml.rels")}
                if "ppt/_rels/presentation.xml.rels" in z.namelist() else {})
        names = [_part("ppt", rels[s.get(R_ID)]) for s in _xml(z, "ppt/presentation.xml").iter(P + "sldId")
                 if rels.get(s.get(R_ID))]
        if not names:   # no slide list at all (a damaged or hand-made file): fall back to file-number order
            names = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                           key=lambda n: int(re.findall(r"\d+", n)[-1]))
        # A slide list may name one part many times or parts that are not there; each real part is read once.
        present = set(z.namelist())
        names = [n for n in dict.fromkeys(names) if n in present]
        if len(names) > MAX_SLIDES:
            raise DocTooLarge(f"presentation has {len(names)} slides (limit {MAX_SLIDES})")
        for i, n in enumerate(names, 1):
            paras = ["".join(t.text or "" for t in p.iter(A + "t")).strip() for p in _xml(z, n).iter(A + "p")]
            if any(paras):
                out.append(f"## Slide {i}\n\n" + "\n\n".join(p for p in paras if p))
    return "\n\n".join(out)


def _pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise DocError("reading PDF needs the 'pypdf' package") from e
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise DocTooLarge(f"PDF has {len(reader.pages)} pages (limit {MAX_PDF_PAGES})")
    # ponytail: the limits are on page count and on text as it accumulates. One page whose
    # content stream alone unpacks enormously is left to pypdf's own handling.
    pages, chars = [], 0
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        chars += len(text)
        if chars > MAX_TEXT_CHARS:
            raise DocTooLarge(f"PDF holds more than {MAX_TEXT_CHARS} characters of text")
        pages.append(text)
    return "\n\n".join(f"## Page {i}\n\n{t}" for i, t in enumerate(pages, 1) if t)


def _zip_with(member: str) -> Callable[[str, bytes], bool]:
    def accepts(name: str, data: bytes) -> bool:
        if data[:2] != b"PK":
            return False
        with _Zip(data) as z:
            return member in z.namelist()
    return accepts


def _ext(*exts: str) -> Callable[[str, bytes], bool]:
    return lambda name, data: name.lower().endswith(exts)


# Tried top to bottom; content is checked before the file name, because names lie.
CONVERTERS: List[Tuple[str, Callable[[str, bytes], bool], Callable[[bytes], str]]] = [
    ("pdf", lambda name, data: data[:5] == b"%PDF-", _pdf),
    ("docx", _zip_with("word/document.xml"), _docx),
    ("xlsx", _zip_with("xl/workbook.xml"), _xlsx),
    ("pptx", _zip_with("ppt/presentation.xml"), _pptx),
    ("csv", _ext(".csv"), lambda d: table(list(csv.reader(io.StringIO(_text(d)))))),
    ("tsv", _ext(".tsv"), lambda d: table(list(csv.reader(io.StringIO(_text(d)), delimiter="\t")))),
    ("html", lambda name, data: name.lower().endswith((".html", ".htm"))
        or re.match(rb"\s*<(!doctype html|html)\b", data[:300], re.I) is not None,
     lambda d: str(html_to_markdown(_text(d))["markdown"])),
    ("text", lambda name, data: True, _text),
]


def convert(name: str, data: bytes) -> Tuple[str, str]:
    """(markdown, converter used). Raises DocError listing every converter that was tried and why it failed.

    A file that breaks a size limit (stored size, entries, unpacked size per part and in total,
    slides, PDF pages, extracted text) raises DocTooLarge at once and nothing more is tried.
    """
    if len(data) > MAX_BYTES:
        raise DocTooLarge(f"{name} is larger than {MAX_BYTES // 1_000_000} MB")
    failed: List[str] = []
    for kind, accepts, to_markdown in CONVERTERS:
        try:
            if not accepts(name, data):
                continue
            markdown = to_markdown(data)
            if len(markdown) > MAX_TEXT_CHARS:
                raise DocTooLarge(f"holds more than {MAX_TEXT_CHARS} characters of text")
            if markdown.strip():
                return markdown, kind
            failed.append(f"{kind}: no text in it")
        except DocTooLarge as e:
            raise DocTooLarge(f"{name} refused: {e}") from e
        except Exception as e:  # a hostile or damaged file can fail anywhere in a parser; try the next one
            failed.append(f"{kind}: {type(e).__name__}: {str(e)[:80]}")
    raise DocError(f"could not read {name} ({'; '.join(failed)})")


# ── the library ──────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, scope TEXT NOT NULL, name TEXT NOT NULL, sha256 TEXT NOT NULL,
    format TEXT NOT NULL, source TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
    invalid_at REAL, supersedes TEXT
);
CREATE INDEX IF NOT EXISTS ix_documents_scope ON documents (scope, invalid_at);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, seq INTEGER NOT NULL, heading TEXT NOT NULL,
    text TEXT NOT NULL, sha256 TEXT NOT NULL, embedding TEXT NOT NULL, flagged INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks (doc_id);
CREATE INDEX IF NOT EXISTS ix_chunks_sha ON chunks (sha256);
"""


@dataclass
class Passage:
    document: str
    heading: str
    text: str
    doc_sha256: str
    chunk_sha256: str
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _tokens(text: str) -> List[str]:
    # \w alone drops Tamil and Devanagari vowel signs and so breaks those words apart
    return re.findall(r"[\wऀ-ॿ஀-௿]+", text.lower())


def _bm25(query: List[str], docs: List[List[str]], k1: float = 1.5, b: float = 0.75) -> List[float]:
    n, avg = len(docs), (sum(map(len, docs)) / len(docs) if docs else 0) or 1
    df = Counter(t for d in docs for t in set(d))
    scores = []
    for d in docs:
        tf = Counter(d)
        scores.append(sum(math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * (k1 + 1)
                          / (tf[t] + k1 * (1 - b + b * len(d) / avg)) for t in set(query) if t in tf))
    return scores


class DocStore:
    def __init__(self, llm: Optional[LLM] = None, *, path: Optional[str] = None) -> None:
        self.llm = llm or LLM()
        self._db = connect_db(path or str(data_dir() / "docs.db"), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA secure_delete=ON")          # erased text must not linger in freed pages (DPDP)
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(_SCHEMA)
        try:                                                 # two current versions of one name can never coexist
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_documents_current ON documents (scope, name) WHERE invalid_at IS NULL")
        except sqlite3.IntegrityError as e:
            logger.warning("docs.db already holds duplicate current documents; unique index not created: %s", e)
        self._lock = threading.Lock()

    def _current(self, scope: str, name: str) -> Optional[sqlite3.Row]:
        return self._db.execute("SELECT * FROM documents WHERE scope=? AND name=? AND invalid_at IS NULL",
                                (scope, name)).fetchone()

    def ingest(self, name: str, data: bytes, *, scope: str, source: str = "") -> Dict[str, Any]:
        """Add a file, or a new version of it. Returns what happened and the counts."""
        sha = hashlib.sha256(data).hexdigest()
        old = self._current(scope, name)
        if old and old["sha256"] == sha:
            return {"action": "UNCHANGED", "doc_id": old["id"], "sha256": sha}
        markdown, kind = convert(name, data)
        parts = chunk(markdown, CHUNK_CHARS)
        if len(parts) > MAX_CHUNKS:
            raise DocError(f"{name} makes {len(parts)} passages (limit {MAX_CHUNKS}); split the file")
        shas = [hashlib.sha256(f"{p['heading']}\n{p['text']}".encode()).hexdigest() for p in parts]
        known = {}
        for s in set(shas):          # a passage seen before keeps its embedding
            row = self._db.execute("SELECT embedding FROM chunks WHERE sha256=? LIMIT 1", (s,)).fetchone()
            if row:
                known[s] = row["embedding"]
        new = [i for i, s in enumerate(shas) if s not in known]
        for start in range(0, len(new), 64):
            batch = new[start:start + 64]
            vectors = self.llm.embed([f"{parts[i]['heading']}\n{parts[i]['text']}" for i in batch])
            known.update({shas[i]: json.dumps(v) for i, v in zip(batch, vectors)})
        flags = [int(guard.scan(p["text"], source=f"docs:{name}").blocked) for p in parts]
        doc_id, now = uuid.uuid4().hex, time.time()
        with self._lock, self._db:
            old = self._current(scope, name)       # re-read under the lock: another writer may have added a version meanwhile
            if old and old["sha256"] == sha:
                return {"action": "UNCHANGED", "doc_id": old["id"], "sha256": sha}
            if old:
                self._db.execute("UPDATE documents SET invalid_at=? WHERE id=?", (now, old["id"]))
            self._db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,NULL,?)",
                             (doc_id, scope, name, sha, kind, source, now, old["id"] if old else None))
            self._db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)", [
                (uuid.uuid4().hex, doc_id, i, p["heading"], p["text"], shas[i], known[shas[i]], flags[i])
                for i, p in enumerate(parts)])
        out = {"action": "UPDATED" if old else "ADDED", "doc_id": doc_id, "sha256": sha, "format": kind,
               "passages": len(parts), "embedded": len(new), "withheld": sum(flags)}
        trace.append("docs", "ingest", {"scope": scope, "name": name, "source": source, **out})
        return out

    def ingest_file(self, path: str, *, scope: str) -> Dict[str, Any]:
        p = Path(path)
        return self.ingest(p.name, p.read_bytes(), scope=scope, source=str(p))

    def remove(self, name: str, *, scope: str, reason: str) -> bool:
        """Stop a document being retrieved. Its record stays."""
        with self._lock, self._db:
            cur = self._db.execute("UPDATE documents SET invalid_at=? WHERE scope=? AND name=? AND invalid_at IS NULL",
                                   (time.time(), scope, name))
        if cur.rowcount:
            trace.append("docs", "remove", {"scope": scope, "name": name, "reason": reason})
        return bool(cur.rowcount)

    def erase(self, name: str, *, scope: str, reason: str) -> int:
        """Hard delete (DPDP erasure): every version of the document and all its passages are removed, not just closed.
        Returns the number of document versions deleted. Only a hash of the name goes to the trace."""
        with self._lock, self._db:
            ids = [r["id"] for r in self._db.execute("SELECT id FROM documents WHERE scope=? AND name=?", (scope, name))]
            for i in ids:
                self._db.execute("DELETE FROM chunks WHERE doc_id=?", (i,))
                self._db.execute("DELETE FROM documents WHERE id=?", (i,))
        self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if ids:
            trace.append("docs", "erase", {"scope": scope, "name_sha256": hashlib.sha256(name.encode()).hexdigest(),
                                           "versions": len(ids), "reason": reason})
        return len(ids)

    def documents(self, scope: str) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._db.execute(
            "SELECT id, name, sha256, format, created_at FROM documents WHERE scope=? AND invalid_at IS NULL "
            "ORDER BY name", (scope,))]

    def search(self, query: str, *, scope: str, k: int = 6) -> List[Passage]:
        """The k best passages from the scope's current documents; passages the guard withheld never appear."""
        # ponytail: scans every passage in the scope per query. Fine to a few tens of thousands;
        # beyond that move vectors to pgvector and wording to Postgres full-text (both already run).
        rows = self._db.execute(
            "SELECT c.heading, c.text, c.sha256, c.embedding, d.name, d.sha256 AS doc_sha FROM chunks c "
            "JOIN documents d ON d.id = c.doc_id WHERE d.scope=? AND d.invalid_at IS NULL AND c.flagged=0",
            (scope,)).fetchall()
        if not rows:
            return []
        qv = self.llm.embed([query])[0]
        vecs = [json.loads(r["embedding"]) for r in rows]
        meaning = [cosine(qv, v) if len(v) == len(qv) else 0.0 for v in vecs]   # other-model vectors: wording only
        wording = _bm25(_tokens(query), [_tokens(f"{r['heading']} {r['text']}") for r in rows])
        fused = [0.0] * len(rows)
        for scores in (meaning, wording):                    # reciprocal rank fusion; a zero score earns nothing
            order = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: scores[i], reverse=True)
            for rank, i in enumerate(order):
                fused[i] += 1 / (RRF_K + rank + 1)
        best = sorted((i for i, s in enumerate(fused) if s > 0), key=lambda i: fused[i], reverse=True)[:k]
        trace.append("docs", "search", {"scope": scope, "query_chars": len(query), "returned": len(best)})
        return [Passage(rows[i]["name"], rows[i]["heading"], rows[i]["text"], rows[i]["doc_sha"], rows[i]["sha256"],
                        round(fused[i], 5)) for i in best]

    def ask(self, question: str, *, scope: str, k: int = 6, redact: bool = True,
            model: Optional[str] = None) -> Dict[str, Any]:
        """Answer from the library only. Every sentence kept cites a passage [n] listed in `sources`.

        `redact` masks secrets and personal identifiers (PAN, Aadhaar, phone, keys) before the
        model sees the passages; turn it off only where the question is about those values.
        """
        found = self.search(question, scope=scope, k=k)
        sources = [{"n": n, **{f: getattr(p, f) for f in ("document", "heading", "doc_sha256", "chunk_sha256")}}
                   for n, p in enumerate(found, 1)]
        if not found:
            return {"answer": "", "sources": [], "unsupported": [], "reason": "nothing relevant in the library"}
        shown = {n: f"{p.document}" + (f" > {p.heading}" if p.heading else "") + "\n"
                 + (guard.redact(p.text)[0] if redact else p.text) for n, p in enumerate(found, 1)}
        listing = "\n\n".join(f"[{n}] {text}" for n, text in shown.items())
        preamble, block = guard.wrap(listing, label="numbered passages from the company's documents")
        prompt = (f"{preamble}\n\n{block}\n\nQuestion: {question}\n\nAnswer using ONLY those passages. End every "
                  "sentence with the number of the passage it rests on, like [1] or [1][2]. If the passages do "
                  "not answer the question, say so in one sentence with no number. Add nothing of your own.")
        answer, unsupported, reason = "", [], ""
        try:
            draft = self.llm.complete(prompt, model=model, max_tokens=700, temperature=0.0, purpose="docs.ask").text
            # A sentence is kept only if it cites a passage and states no figure that passage lacks.
            answer, unsupported = verify_report(draft, set(shown), shown)
            reason = "" if answer else "the passages found do not support an answer"
        except LLMError as e:
            reason = f"model unavailable: {str(e)[:120]}"
        trace.append("docs", "ask", {"scope": scope, "sources": len(sources), "unsupported": len(unsupported),
                                     "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()})
        return {"answer": answer, "sources": sources, "unsupported": unsupported, "reason": reason}
