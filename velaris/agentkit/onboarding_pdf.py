"""A minimal PDF writer and structure parser (standard library only). Text layout, A4, base-14 fonts.

What it is for: offer letters and the evidence page of a signed document. What it is not: a layout engine.
Lines are plain text in Helvetica or Helvetica-Bold, wrapped to the page width (widths are the Helvetica
metrics, bold is wrapped a little wider to be safe), with a "row" kind for aligned money tables. Characters
outside Latin-1 are replaced (the rupee sign becomes "Rs."), nothing is embedded, nothing is compressed, so
the content streams stay readable by parse_pdf() and by any viewer.

parse_pdf() re-reads a file's structure: header, the xref chain (/Prev followed), that every xref entry
points at "N G obj", the catalog, the page tree, the page count and the text of each page. It is how tests
prove a file is well formed, and how append_page() finds what it must extend.

append_page() adds one page by an INCREMENTAL UPDATE: the original bytes are left untouched and new objects,
a new xref section and a trailer are appended, so the original document's hash is still a prefix of the
result. It only understands files written by this module; for any other PDF it raises PdfError and the
caller keeps the evidence page as a separate file. Where a PDF library (pyHanko) would plug in is described in
velaris/agentkit/onboarding_esign.py.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple, Union

PAGE_W, PAGE_H, MARGIN = 595, 842, 56
_SIZE, _LEAD = 10.5, 14.5
Line = Tuple[str, Union[str, Sequence[str]]]       # ("h1"|"h2"|"p"|"b"|"gap"|"row"|"rowb", text | cells)

_W = dict(zip(" !\"#$%&'()*+,-./0123456789:;<=>?@", (278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333,
          278, 278) + (556,) * 10 + (278, 278, 584, 584, 584, 556, 1015)))
_W.update(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
          667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611)))
_W.update(zip("[\\]^_`", (278, 278, 278, 469, 556, 333)))
_W.update(zip("abcdefghijklmnopqrstuvwxyz", (556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
          556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500)))
_W.update(zip("{|}~", (334, 260, 334, 584)))


class PdfError(ValueError):
    """The bytes are not a PDF this module can read or extend."""


def latin1(text: str) -> str:
    text = text.replace("\u20b9", "Rs.").replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return text.encode("latin-1", "replace").decode("latin-1")


def _esc(text: str) -> str:
    return latin1(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\r", " ").replace("\n", " ")


def text_width(text: str, size: float, bold: bool = False) -> float:
    return sum(_W.get(c, 556) for c in text) * size / 1000 * (1.07 if bold else 1.0)


def wrap(text: str, size: float, width: float, bold: bool = False) -> List[str]:
    """Greedy word wrap; a single word wider than the line is split by characters."""
    out: List[str] = []
    for para in latin1(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            while text_width(word, size, bold) > width:
                cut = max(1, int(len(word) * width / text_width(word, size, bold)) - 1)
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(word[:cut])
                word = word[cut:]
            trial = f"{cur} {word}" if cur else word
            if cur and text_width(trial, size, bold) > width:
                out.append(cur)
                cur = word
            else:
                cur = trial
        out.append(cur)
    return out


def _layout(lines: Sequence[Line]) -> List[List[Tuple[str, float, float, str, float]]]:
    """Pages of drawing ops (font, size, x, text, y)."""
    pages: List[List[Tuple[str, float, float, str, float]]] = [[]]
    y = PAGE_H - MARGIN
    right = PAGE_W - MARGIN
    for kind, content in lines:
        size = {"h1": 16.0, "h2": 12.5}.get(kind, _SIZE)
        bold = kind in ("h1", "h2", "b", "rowb")
        font = "F2" if bold else "F1"
        if kind == "gap":
            y -= _LEAD / 2
            continue
        if kind in ("row", "rowb"):
            cells = [latin1(str(c)) for c in content]       # type: ignore[union-attr]
            if y < MARGIN + _LEAD:
                pages.append([])
                y = PAGE_H - MARGIN
            pages[-1].append((font, size, MARGIN, cells[0], y))
            for k, cell in enumerate(reversed(cells[1:])):
                x = right - 105 * k - text_width(cell, size, bold)
                pages[-1].append((font, size, x, cell, y))
            y -= _LEAD
            continue
        lead = _LEAD * (1.35 if kind == "h1" else 1.15 if kind == "h2" else 1.0)
        for piece in wrap(str(content), size, right - MARGIN, bold):
            if y < MARGIN + lead:
                pages.append([])
                y = PAGE_H - MARGIN
            pages[-1].append((font, size, MARGIN, piece, y))
            y -= lead
    return pages


def _content(ops: Sequence[Tuple[str, float, float, str, float]]) -> bytes:
    body = "".join(f"BT /{f} {s} Tf {x:.1f} {y:.1f} Td ({_esc(t)}) Tj ET\n" for f, s, x, t, y in ops)
    return body.encode("latin-1")


def _obj(num: int, body: bytes) -> bytes:
    return f"{num} 0 obj\n".encode() + body + b"\nendobj\n"


def _stream(data: bytes) -> bytes:
    return b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"


_FONTS = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
          b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")


def _page_objs(first: int, fonts: Tuple[int, int], parent: int, ops: Any) -> List[bytes]:
    page = (f"<< /Type /Page /Parent {parent} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Contents {first + 1} 0 R "
            f"/Resources << /Font << /F1 {fonts[0]} 0 R /F2 {fonts[1]} 0 R >> >> >>").encode()
    return [_obj(first, page), _obj(first + 1, _stream(_content(ops)))]


def _xref(offsets: Dict[int, int]) -> bytes:
    """An xref section for the given {object number: offset}, as subsections of consecutive numbers."""
    nums = sorted(offsets)
    out, i = b"xref\n", 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out += f"{nums[i]} {j - i + 1}\n".encode()
        out += b"".join(b"%010d 00000 n \n" % offsets[n] for n in nums[i:j + 1])
        i = j + 1
    return out


def build_pdf(lines: Sequence[Line], *, title: str = "", producer: str = "Velaris") -> bytes:
    """An A4 PDF of `lines`. Deterministic: the same lines give the same bytes (no timestamps)."""
    pages = _layout(lines)
    n = len(pages)
    kids = " ".join(f"{6 + 2 * i} 0 R" for i in range(n))
    objs: List[Tuple[int, bytes]] = [
        (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        (2, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()),
        (3, _FONTS[0]), (4, _FONTS[1]),
        (5, f"<< /Title ({_esc(title)}) /Producer ({_esc(producer)}) >>".encode()),
    ]
    blob = [_obj(num, body) for num, body in objs]
    for i, ops in enumerate(pages):
        blob += _page_objs(6 + 2 * i, (3, 4), 2, ops)
    out = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets: Dict[int, int] = {}
    for b in blob:
        offsets[int(b.split(b" ", 1)[0])] = len(out)
        out += b
    start = len(out)
    size = 6 + 2 * n
    return out + _xref({0: 0, **offsets}).replace(b"0000000000 00000 n", b"0000000000 65535 f", 1) + (
        f"trailer\n<< /Size {size} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{start}\n%%EOF\n").encode()


# ---- reading -------------------------------------------------------------------------------------

_OBJ_RE = re.compile(rb"(\d+) 0 obj\n")


def _read_xref(data: bytes, pos: int) -> Tuple[Dict[int, int], bytes]:
    if data[pos:pos + 5] != b"xref\n":
        raise PdfError("startxref does not point at an xref section")
    end = data.index(b"trailer", pos)
    entries: Dict[int, int] = {}
    lines = data[pos + 5:end].decode("latin-1").split("\n")
    i = 0
    while i < len(lines) and lines[i].strip():
        first, count = (int(x) for x in lines[i].split())
        for k in range(count):
            off, _gen, flag = lines[i + 1 + k].split()
            if flag == "n":
                entries[first + k] = int(off)
        i += 1 + count
    tr_end = data.index(b"startxref", end)
    return entries, data[end + 7:tr_end]


def _structure(data: bytes) -> Dict[str, Any]:
    if not data.startswith(b"%PDF-1.") or not data.rstrip().endswith(b"%%EOF"):
        raise PdfError("missing %PDF header or %%EOF trailer")
    try:
        pos = int(data[data.rindex(b"startxref") + 10:].split()[0])
    except (ValueError, IndexError) as e:
        raise PdfError("no startxref") from e
    newest = pos
    table: Dict[int, int] = {}
    trailers: List[bytes] = []
    seen = set()
    while True:
        if pos in seen:
            raise PdfError("xref chain loops")
        seen.add(pos)
        try:
            entries, trailer = _read_xref(data, pos)
        except (ValueError, IndexError) as e:
            raise PdfError(f"unreadable xref: {e}") from e
        for num, off in entries.items():
            table.setdefault(num, off)        # newest section wins
        trailers.append(trailer)
        prev = re.search(rb"/Prev (\d+)", trailer)
        if not prev:
            break
        pos = int(prev.group(1))
    for num, off in table.items():
        m = _OBJ_RE.match(data, off)
        if not m or int(m.group(1)) != num:
            raise PdfError(f"xref entry for object {num} does not point at that object")
    root = re.search(rb"/Root (\d+) 0 R", trailers[0])
    if not root:
        raise PdfError("trailer has no /Root")
    return {"table": table, "trailer": trailers[0], "root": int(root.group(1)), "start": newest}


def _body(data: bytes, table: Dict[int, int], num: int) -> bytes:
    if num not in table:
        raise PdfError(f"object {num} is not in the xref")
    off = table[num]
    m = _OBJ_RE.match(data, off)
    end = data.index(b"endobj", m.end())            # type: ignore[union-attr]
    return data[m.end():end]                        # type: ignore[union-attr]


def parse_pdf(data: bytes) -> Dict[str, Any]:
    """Check the structure and return {"pages", "objects", "text": [per page], "title"}. Raises PdfError."""
    st = _structure(data)
    table = st["table"]
    cat = _body(data, table, st["root"])
    pages_ref = re.search(rb"/Pages (\d+) 0 R", cat)
    if b"/Type /Catalog" not in cat or not pages_ref:
        raise PdfError("catalog is missing or has no /Pages")
    tree = _body(data, table, int(pages_ref.group(1)))
    kids = [int(k) for k in re.findall(rb"(\d+) 0 R", re.search(rb"/Kids \[(.*?)\]", tree, re.S).group(1))] \
        if re.search(rb"/Kids \[", tree) else []
    count = re.search(rb"/Count (\d+)", tree)
    if not count or int(count.group(1)) != len(kids) or not kids:
        raise PdfError("page tree /Count does not match /Kids")
    texts = []
    for k in kids:
        page = _body(data, table, k)
        mb = re.search(rb"/MediaBox \[0 0 (\d+) (\d+)\]", page)
        c = re.search(rb"/Contents (\d+) 0 R", page)
        if b"/Type /Page" not in page or not mb or not c or (int(mb.group(1)), int(mb.group(2))) != (PAGE_W, PAGE_H):
            raise PdfError(f"page object {k} is malformed (or not A4)")
        stream = _body(data, table, int(c.group(1)))
        length = int(re.search(rb"/Length (\d+)", stream).group(1))        # type: ignore[union-attr]
        raw = stream.split(b"stream\n", 1)[1][:length]
        if stream.split(b"stream\n", 1)[1][length:length + 10] != b"\nendstream":
            raise PdfError("stream /Length is wrong")
        texts.append("\n".join(_unesc(t) for t in re.findall(rb"\(((?:\\.|[^\\)])*)\) Tj", raw)))
    info = re.search(rb"/Info (\d+) 0 R", st["trailer"])
    title = ""
    if info:
        t = re.search(rb"/Title \(((?:\\.|[^\\)])*)\)", _body(data, table, int(info.group(1))))
        title = _unesc(t.group(1)) if t else ""
    return {"pages": len(kids), "objects": len(table), "text": texts, "title": title}


def _unesc(raw: bytes) -> str:
    return re.sub(r"\\(.)", r"\1", raw.decode("latin-1"))


def append_page(pdf: bytes, lines: Sequence[Line]) -> bytes:
    """`pdf` plus one more page, by incremental update; the original bytes are an exact prefix of the result."""
    st = _structure(pdf)
    table = st["table"]
    cat = _body(pdf, table, st["root"])
    pages_num = int(re.search(rb"/Pages (\d+) 0 R", cat).group(1))               # type: ignore[union-attr]
    tree = _body(pdf, table, pages_num)
    kids_m = re.search(rb"/Kids \[(.*?)\]", tree, re.S)
    if not kids_m or not re.search(rb"/Count (\d+)", tree):
        raise PdfError("page tree not understood")
    size = int(re.search(rb"/Size (\d+)", st["trailer"]).group(1))               # type: ignore[union-attr]
    kids = kids_m.group(1).decode().strip()
    # the layout may spill onto several pages; every one is appended
    pages = _layout(lines)
    out, offsets = bytearray(pdf if pdf.endswith(b"\n") else pdf + b"\n"), {}
    fonts = (size, size + 1)
    nxt = size + 2
    new_kids = []
    for num, body in ((fonts[0], _FONTS[0]), (fonts[1], _FONTS[1])):
        offsets[num] = len(out)
        out += _obj(num, body)
    for ops in pages:
        for blob in _page_objs(nxt, fonts, pages_num, ops):
            offsets[int(blob.split(b" ", 1)[0])] = len(out)
            out += blob
        new_kids.append(f"{nxt} 0 R")
        nxt += 2
    count = len(re.findall(r"\d+ 0 R", kids)) + len(new_kids)
    offsets[pages_num] = len(out)
    out += _obj(pages_num, f"<< /Type /Pages /Kids [{kids} {' '.join(new_kids)}] /Count {count} >>".encode())
    start = len(out)
    trailer = st["trailer"].decode("latin-1")
    trailer = re.sub(r"/Size \d+", f"/Size {nxt}", trailer)
    trailer = re.sub(r"\s*/Prev \d+", "", trailer).replace(">>", f"/Prev {st['start']} >>", 1)
    out += _xref(offsets) + b"trailer\n" + trailer.strip().encode() + f"\nstartxref\n{start}\n%%EOF\n".encode()
    return bytes(out)
