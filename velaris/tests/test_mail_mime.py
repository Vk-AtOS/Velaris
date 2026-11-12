"""Mail parsing and HTML sanitising: nested multipart, odd charsets, malformed headers, hostile HTML."""
import pytest

from velaris.mail.mime import build_message, normalise_subject, parse_addresses, parse_message, valid_address
from velaris.mail.sanitize import sanitize_html
from velaris.mail.common import MailError
from velaris.tests.mail_helpers import raw_mail


def test_nested_multipart_text_html_and_attachments():
    raw = (b"From: A <a@x.com>\r\nTo: b@y.org\r\nSubject: =?utf-8?q?caf=C3=A9?=\r\nMessage-ID: <n1@x>\r\nMIME-Version: 1.0\r\n"
           b'Content-Type: multipart/mixed; boundary="OUT"\r\n\r\n--OUT\r\nContent-Type: multipart/alternative; boundary="IN"\r\n\r\n'
           b"--IN\r\nContent-Type: text/plain\r\n\r\nplain body\r\n--IN\r\nContent-Type: text/html\r\n\r\n<p>html <b>body</b></p><script>x()</script>\r\n--IN--\r\n"
           b'--OUT\r\nContent-Type: application/pdf; name="r.pdf"\r\nContent-Disposition: attachment; filename="r.pdf"\r\n'
           b"Content-Transfer-Encoding: base64\r\n\r\nSGVsbG8=\r\n--OUT--\r\n")
    p = parse_message(raw)
    assert p.subject == "café" and p.text == "plain body" and "<b>body</b>" in p.html and "script" not in p.html
    assert [a.name for a in p.attachments] == ["r.pdf"] and p.attachments[0].data == b"Hello" and len(p.attachments[0].sha256) == 64


def test_odd_charsets_and_malformed_headers_never_raise():
    p = parse_message(b"From: =?bogus-charset?q?x?= <a@x.com>\r\nSubject: =?utf-99?b?????\r\nDate: not a date\r\nTo: <<<>>>, ok@y.org, broken@\r\n"
                      b"Content-Type: text/plain; charset=klingon\r\n\r\ncaf\xe9 \x00 text")
    assert p.from_addr == "a@x.com" and p.to == ["ok@y.org"] and p.date_ts is None
    assert "caf" in p.text and "\x00" not in p.text
    q = parse_message(b"\xff\xfe\x00garbage that is not a message")
    assert q.message_id.startswith("no-id-") and q.from_addr == ""
    r = parse_message(b"Subject: x\r\nContent-Type: multipart/mixed; boundary=nope\r\n\r\nno parts here")
    assert r.attachments == []


def test_limits_on_depth_and_parts():
    body = b"Content-Type: text/plain\r\n\r\nx\r\n"
    for i in range(30):
        body = (f'Content-Type: multipart/mixed; boundary="b{i}"\r\n\r\n--b{i}\r\n').encode() + body + f"\r\n--b{i}--\r\n".encode()
    p = parse_message(b"From: a@x.com\r\n" + body)
    assert "too_many_parts" in p.defects                      # depth cap reached, parser still returns
    big = parse_message(raw_mail(body="x" * 10), max_attachment=5)
    assert big.text == "x" * 10


def test_attachment_over_limit_is_dropped_not_stored():
    raw = (b"From: a@x.com\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n--B\r\nContent-Type: text/plain\r\n\r\nt\r\n"
           b'--B\r\nContent-Type: application/zip\r\nContent-Disposition: attachment; filename="../../etc/passwd"\r\n\r\n' + b"z" * 100 + b"\r\n--B--\r\n")
    assert parse_message(raw, max_attachment=10).attachments == []
    p = parse_message(raw)
    assert "/" not in p.attachments[0].name and ".." not in p.attachments[0].name.split("_")[0]   # path separators neutralised


def test_message_id_threading_headers_and_addresses():
    p = parse_message(raw_mail(extra="In-Reply-To: <a@x>\r\nReferences: <r1@x> <r2@x>\r\n"))
    assert p.in_reply_to == "a@x" and p.references == ["r1@x", "r2@x"] and p.message_id == "m1@ext.org"
    assert parse_addresses('"Doe, J" <J@X.com>, bad') == [("Doe, J", "j@x.com")]
    assert valid_address("a@b.co") and not valid_address("a@b") and not valid_address("a b@c.com") and not valid_address("a@b.c\n")
    assert normalise_subject("Re: RE[2]: Fwd: Plan  A") == "plan a"


def test_build_message_rejects_header_injection():
    with pytest.raises(MailError):
        build_message(from_addr="a@x.com", to=["b@y.org"], subject="hi\r\nBcc: evil@x.com", text="t")
    with pytest.raises(MailError):
        build_message(from_addr="a@x.com", to=["b@y.org\r\nBcc: e@x.com"], subject="s", text="t")
    raw = build_message(from_addr="a@x.com", to=["b@y.org"], subject="s", text="t", html="<p>t</p>")
    assert parse_message(raw).html == "<p>t</p>"


@pytest.mark.parametrize("src,absent", [
    ("<script>alert(1)</script><p>ok</p>", "script"),
    ('<p onclick="x()">a</p>', "onclick"),
    ('<img src="http://tracker.example/p.gif" onerror="x()">', "tracker"),
    ('<div style="background:url(http://evil/x)">a</div>', "url("),
    ('<a href="javascript:alert(1)">x</a>', "javascript"),
    ('<a href="  jav&#x09;ascript:alert(1)">x</a>', "ascript:"),
    ('<a href="data:text/html;base64,AAAA">x</a>', "data:"),
    ('<iframe src="http://evil"></iframe>t', "iframe"),
    ('<form action="http://evil"><input name=p></form>t', "form"),
    ('<svg onload="x()"><circle/></svg>t', "svg"),
    ('<style>@import url(http://evil);</style>t', "import"),
    ('<object data="x"></object><embed src="y">t', "embed"),
])
def test_sanitiser_removes_active_content(src, absent):
    out = sanitize_html(src).html
    assert absent not in out.lower()


def test_sanitiser_blocks_remote_images_keeps_cid_and_shows_real_link_host():
    s = sanitize_html('<img src="https://t.example/x.png"><img src="cid:logo@x" alt="logo">'
                      '<a href="https://evil.test/login">https://bank.example/login</a><a href="mailto:a@b.co">mail</a>')
    assert s.blocked_images == 1 and 'src="cid:logo@x"' in s.html and "t.example" not in s.html
    assert "(evil.test)" in s.html and 'rel="noopener noreferrer nofollow"' in s.html and s.hosts == ["evil.test"]
    assert "(" not in sanitize_html('<a href="https://bank.example/x">bank.example</a>').html.split("</a>")[1]


def test_sanitiser_survives_broken_html_and_depth():
    assert sanitize_html("<p><b>unclosed <i>tags").html.endswith("</i></b></p>")
    deep = sanitize_html("<div>" * 500 + "x").html
    assert deep.count("<div>") <= 40
    assert sanitize_html("<![CDATA[ <script>x()</script> ]]>t").html.count("script") == 0
