"""A small file must not be able to unpack into something enormous.

Limits are lowered with monkeypatch so the bombs here are a few kilobytes; one test runs
at the real limits to show the defaults themselves hold.
"""
import io
import struct
import zipfile

import pytest

from velaris.intel import docs
from velaris.intel.docs import DocError, DocTooLarge, convert

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def zipped(members) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in members.items():
            z.writestr(name, body)
    return buf.getvalue()


def docx(paragraph: str, extra=None) -> bytes:
    body = f"<w:document {W}><w:body><w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p></w:body></w:document>"
    return zipped({"word/document.xml": body, **(extra or {})})


def pptx(slides: int, text: str) -> bytes:
    a = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    p = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    members = {
        "ppt/presentation.xml": f"<p:presentation {p} {R}><p:sldIdLst>" + "".join(
            f'<p:sldId id="{i}" r:id="r{i}"/>' for i in range(slides)) + "</p:sldIdLst></p:presentation>",
        "ppt/_rels/presentation.xml.rels": "<Relationships>" + "".join(
            f'<Relationship Id="r{i}" Target="slides/slide{i}.xml"/>' for i in range(slides)) + "</Relationships>",
    }
    for i in range(slides):
        members[f"ppt/slides/slide{i}.xml"] = f"<p:sld {p} {a}><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:sld>"
    return zipped(members)


def xlsx(sheet_rows: str, shared: str = "") -> bytes:
    return zipped({
        "xl/workbook.xml": f'<workbook {S} {R}><sheets><sheet name="A" r:id="r1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/sharedStrings.xml": f"<sst {S}>{shared}</sst>",
        "xl/worksheets/sheet1.xml": f"<worksheet {S}><sheetData>{sheet_rows}</sheetData></worksheet>",
    })


def test_ordinary_office_file_still_reads():
    assert convert("a.docx", docx("hello there"))[0] == "hello there"


def test_real_limits_refuse_a_real_bomb_before_unpacking_it():
    bomb = docx(" " * (docs.MAX_MEMBER + 1))                 # 64 MB of spaces in about 62 kB
    assert len(bomb) < 200_000
    with pytest.raises(DocTooLarge, match=r"word/document\.xml is \d+ bytes unpacked"):
        convert("bomb.docx", bomb)


def test_one_part_over_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(docs, "MAX_MEMBER", 5_000)
    with pytest.raises(DocTooLarge, match="word/document.xml"):
        convert("bomb.docx", docx("x" * 20_000))


def test_many_parts_each_under_the_limit_are_refused_on_the_total(monkeypatch):
    monkeypatch.setattr(docs, "MAX_MEMBER", 5_000)
    monkeypatch.setattr(docs, "MAX_UNPACKED", 12_000)
    assert "slide text" in convert("ok.pptx", pptx(2, "slide text"))[0]
    with pytest.raises(DocTooLarge, match="in total"):
        convert("bomb.pptx", pptx(10, "y" * 3_000))          # 10 slides x 3 kB: each fine, together not


def test_too_many_entries_is_refused(monkeypatch):
    monkeypatch.setattr(docs, "MAX_MEMBERS", 50)
    with pytest.raises(DocTooLarge, match="entries"):
        convert("many.docx", docx("hi", {f"junk/{i}": "" for i in range(60)}))


def test_declared_size_is_not_trusted(monkeypatch):
    """The part says it is 10 bytes and unpacks to 20 kB. It is refused, and reading stopped
    at the limit instead of following the stream to its end."""
    monkeypatch.setattr(docs, "MAX_MEMBER", 5_000)
    honest = bytearray(docx("x" * 20_000))
    real = len(f"<w:document {W}><w:body><w:p><w:r><w:t>{'x' * 20_000}</w:t></w:r></w:p></w:body></w:document>")
    packed = struct.pack("<I", real)
    assert honest.count(packed) == 2                          # local header and central directory
    lying = bytes(honest.replace(packed, struct.pack("<I", 10)))
    with zipfile.ZipFile(io.BytesIO(lying)) as z:
        assert z.getinfo("word/document.xml").file_size == 10
    with pytest.raises(DocError):
        convert("liar.docx", lying)
    archive = docs._Zip(lying)
    with pytest.raises((DocTooLarge, zipfile.BadZipFile)):
        archive.part("word/document.xml")
    assert archive.unpacked <= docs.MAX_MEMBER + (1 << 20)   # never more than one block past the limit


def test_spreadsheet_cannot_multiply_one_shared_string(monkeypatch):
    monkeypatch.setattr(docs, "MAX_TEXT_CHARS", 50_000)
    rows = "".join(f'<row r="{i}"><c r="A{i}" t="s"><v>0</v></c></row>' for i in range(1, 400))
    bomb = xlsx(rows, shared=f"<si><t>{'z' * 1_000}</t></si>")   # 399 cells x 1,000 characters
    with pytest.raises(DocTooLarge, match="cell text"):
        convert("bomb.xlsx", bomb)


def test_spreadsheet_cannot_span_a_huge_empty_grid(monkeypatch):
    monkeypatch.setattr(docs, "MAX_CELLS", 100_000)
    rows = "".join(f'<row r="{i}"><c r="XFD{i}" t="inlineStr"><is><t>x</t></is></c></row>' for i in range(1, 20))
    with pytest.raises(DocTooLarge, match="cells"):
        convert("sparse.xlsx", xlsx(rows))                   # 19 rows x 16,384 columns


def test_pdf_page_count_and_text_are_capped(monkeypatch):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    monkeypatch.setattr(docs, "MAX_PDF_PAGES", 3)
    with pytest.raises(DocTooLarge, match="5 pages"):
        convert("long.pdf", buf.getvalue())
    monkeypatch.setattr(docs, "MAX_PDF_PAGES", 2000)
    monkeypatch.setattr(docs, "MAX_TEXT_CHARS", 10)
    monkeypatch.setattr(pypdf.PageObject, "extract_text", lambda self, *a, **k: "word " * 3)
    with pytest.raises(DocTooLarge, match="characters of text"):
        convert("wordy.pdf", buf.getvalue())


def test_too_much_text_in_a_plain_file_is_refused(monkeypatch):
    monkeypatch.setattr(docs, "MAX_TEXT_CHARS", 100)
    with pytest.raises(DocTooLarge, match="characters of text"):
        convert("big.txt", b"a" * 500)


def test_store_refuses_a_bomb_and_keeps_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    monkeypatch.setattr(docs, "MAX_MEMBER", 5_000)
    from velaris.intel.llm import FakeLLM
    store = docs.DocStore(FakeLLM(lambda messages: ""))
    with pytest.raises(DocTooLarge):
        store.ingest("bomb.docx", docx("x" * 20_000), scope="acme")
    assert store.documents("acme") == []
