"""Parse mail from outside into a safe model, and build mail to send. Standard `email` package only.

parse_message() never raises on odd input: malformed headers, unknown charsets, broken base64 and
absurd nesting become `defects` and best-effort text. Limits (parts, depth, sizes) are enforced while
walking. HTML is sanitised (velaris.mail.sanitize); attachments are kept as bytes with their sha256.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from email import policy
from email.errors import HeaderParseError
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, make_msgid, parsedate_to_datetime
from typing import Dict, List, Optional, Sequence, Tuple

from velaris.mail.common import MailError, clip, sha256
from velaris.mail.sanitize import html_to_text, sanitize_html

MAX_PARTS, MAX_DEPTH, MAX_TEXT = 200, 12, 2_000_000
_ADDR = re.compile(r"[A-Za-z0-9._%+'!#$&*=?^`{|}~/-]{1,64}@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\Z")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CTYPE = re.compile(r"[a-z0-9][a-z0-9!#$&^_.+-]{0,60}/[a-z0-9][a-z0-9!#$&^_.+-]{0,60}\Z")
_KEEP_HEADERS = ("list-id", "list-unsubscribe", "auto-submitted", "precedence", "x-auto-response-suppress",
                 "return-path", "x-velaris-forwarded", "reply-to", "sender", "x-mailer", "user-agent")


@dataclass
class Attachment:
    name: str
    content_type: str
    size: int
    sha256: str
    data: bytes = field(default=b"", repr=False)
    content_id: str = ""
    inline: bool = False


@dataclass
class Parsed:
    message_id: str = ""
    in_reply_to: str = ""
    references: List[str] = field(default_factory=list)
    from_addr: str = ""
    from_name: str = ""
    to: List[str] = field(default_factory=list)
    cc: List[str] = field(default_factory=list)
    subject: str = ""
    date_ts: Optional[float] = None
    text: str = ""
    html: str = ""
    attachments: List[Attachment] = field(default_factory=list)
    size: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    received_count: int = 0
    blocked_images: int = 0
    link_hosts: List[str] = field(default_factory=list)
    defects: List[str] = field(default_factory=list)

    @property
    def body_for_reading(self) -> str:
        return self.text or html_to_text(self.html)

    @property
    def snippet(self) -> str:
        return " ".join(self.body_for_reading.split())[:200]


def valid_address(addr: str) -> bool:
    return isinstance(addr, str) and len(addr) <= 254 and bool(_ADDR.match(addr))


def domain_of(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].lower() if "@" in addr else ""


def parse_addresses(value: str) -> List[Tuple[str, str]]:
    """[(display name, lower-case address)] for the valid ones; bad ones are dropped, never guessed."""
    out = []
    for name, addr in getaddresses([value]):
        addr = addr.strip().lower()
        if valid_address(addr):
            out.append((name.strip()[:200], addr))
    if not out:                                   # the strict reading found nothing: take address-shaped words, never guess further
        out = [("", a.lower()) for a in re.findall(r"[A-Za-z0-9._%+'-]{1,64}@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}", value) if valid_address(a.lower())]
    return out[:200]


def _raw_header(msg: Message, name: str) -> str:
    """The header as stored, decoded as far as it will go, for when the strict parser refuses it."""
    for k, v in msg.raw_items():
        if k.lower() == name.lower():
            try:
                return str(make_header(decode_header(str(v))))
            except (ValueError, LookupError, UnicodeError, HeaderParseError):
                return str(v)
    return ""


def _hdr(msg: Message, name: str, defects: List[str]) -> str:
    try:
        v = msg.get(name)
        return _CTRL.sub("", str(v)).strip() if v is not None else ""
    except (ValueError, TypeError, LookupError, IndexError, AttributeError, UnicodeError):
        defects.append(f"bad_header:{name.lower()}")
        return _CTRL.sub("", _raw_header(msg, name)).strip()


def _text_of(part: Message) -> str:
    try:
        return str(part.get_content())
    except (LookupError, UnicodeError, ValueError, KeyError, AttributeError, TypeError):
        pass
    try:
        payload = part.get_payload(decode=True) or b""
    except (ValueError, TypeError, AttributeError):
        return ""
    cs = None
    try:
        cs = part.get_content_charset()
    except (ValueError, TypeError, AttributeError):
        cs = None
    for enc in (cs, "utf-8", "latin-1"):
        if enc:
            try:
                return payload.decode(enc, "replace")
            except LookupError:
                continue
    return ""


def _filename(part: Message) -> str:
    try:
        n = part.get_filename() or ""
    except (ValueError, TypeError, AttributeError, LookupError):
        n = ""
    n = re.sub(r"[\x00-\x1f\x7f/\\]", "_", str(n)).strip(" .")[:200]
    return n or "attachment"


def _ctype(part: Message) -> str:
    try:
        c = part.get_content_type()
    except (ValueError, TypeError, AttributeError):
        return "application/octet-stream"
    return c if _CTYPE.match(c) else "application/octet-stream"


def parse_message(raw: bytes, *, max_attachment: int = 10_000_000, fallback_ts: Optional[float] = None) -> Parsed:
    p = Parsed(size=len(raw))
    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
    except (ValueError, TypeError, AttributeError, RecursionError):
        p.defects.append("unparsable")
        p.message_id = "no-id-" + sha256(raw)[:32] + "@local"
        return p
    d = p.defects
    p.defects.extend(f"parser:{type(x).__name__}" for x in list(msg.defects)[:5])
    p.message_id = _clean_id(_hdr(msg, "Message-ID", d)) or "no-id-" + sha256(raw)[:32] + "@local"
    p.in_reply_to = _clean_id(_hdr(msg, "In-Reply-To", d))
    p.references = [x[:255] for x in re.findall(r"<([^<>\s]{1,255})>", _hdr(msg, "References", d))][-50:]
    frm = parse_addresses(_hdr(msg, "From", d))
    p.from_name, p.from_addr = frm[0] if frm else ("", "")
    p.to = [a for _, a in parse_addresses(_hdr(msg, "To", d))]
    p.cc = [a for _, a in parse_addresses(_hdr(msg, "Cc", d))]
    p.subject = _hdr(msg, "Subject", d)[:998]
    try:
        p.date_ts = parsedate_to_datetime(_hdr(msg, "Date", d)).timestamp()
    except (TypeError, ValueError, IndexError, OverflowError):
        p.date_ts = fallback_ts
    p.headers = {h: _hdr(msg, h, d)[:500] for h in _KEEP_HEADERS if _hdr(msg, h, d)}
    try:
        p.received_count = len(msg.get_all("Received") or [])
    except (ValueError, TypeError):
        p.received_count = 0
    text_parts: List[str] = []
    html_parts: List[str] = []
    count = [0]

    def walk(part: Message, depth: int) -> None:
        count[0] += 1
        if count[0] > MAX_PARTS or depth > MAX_DEPTH:
            if "too_many_parts" not in d:
                d.append("too_many_parts")
            return
        ctype = _ctype(part)
        if part.is_multipart():
            try:
                kids = list(part.iter_parts())
            except (ValueError, TypeError, AttributeError):
                d.append("bad_multipart")
                return
            for kid in kids:
                walk(kid, depth + 1)
            return
        if ctype.startswith("multipart/"):               # declared multipart but the parser found no parts (bad boundary)
            d.append("bad_multipart")
            raw_body = part.get_payload()
            if isinstance(raw_body, str):
                text_parts.append(_CTRL.sub("", raw_body)[:MAX_TEXT])
            return
        try:
            disp = part.get_content_disposition()
        except (ValueError, TypeError, AttributeError):
            disp = None
        named = bool(_filename(part) != "attachment" or disp == "attachment")
        if ctype in ("text/plain", "text/html") and not named:
            (text_parts if ctype == "text/plain" else html_parts).append(_CTRL.sub("", _text_of(part))[:MAX_TEXT])
            return
        try:
            data = part.get_payload(decode=True) if not ctype.startswith("message/") else part.as_bytes()
        except (ValueError, TypeError, AttributeError, KeyError):
            data = None
        if not isinstance(data, (bytes, bytearray)):
            d.append("empty_attachment")
            return
        if len(data) > max_attachment:
            d.append("attachment_too_large")
            return
        cid = _hdr(part, "Content-ID", d).strip("<> ")[:200]
        p.attachments.append(Attachment(_filename(part), ctype, len(data), sha256(bytes(data)), bytes(data), cid,
                                        disp == "inline" or bool(cid)))

    walk(msg, 0)
    p.text = "\n\n".join(t.replace("\r\n", "\n").replace("\r", "\n") for t in text_parts if t)[:MAX_TEXT].strip("\n")
    if html_parts:
        s = sanitize_html("\n".join(html_parts).replace("\r\n", "\n").replace("\r", "\n").strip("\n"))
        p.html, p.blocked_images, p.link_hosts = s.html, s.blocked_images, s.hosts
        if s.truncated:
            d.append("html_truncated")
    return p


def _clean_id(v: str) -> str:
    m = re.search(r"<([^<>\s]{1,255})>", v)
    return m.group(1) if m else ""


def normalise_subject(subject: str) -> str:
    s = subject.strip().lower()
    while True:
        n = re.sub(r"^(re|fwd?|aw|sv|antw)\s*(\[\d+\])?\s*:\s*", "", s)
        if n == s:
            break
        s = n
    return " ".join(s.split())[:200]


def is_reply_subject(subject: str) -> bool:
    return bool(re.match(r"\s*(re|fwd?|aw|sv|antw)\s*(\[\d+\])?\s*:", subject, re.I))


def build_message(*, from_addr: str, to: Sequence[str], cc: Sequence[str] = (), subject: str, text: str,
                  html: str = "", attachments: Sequence[Attachment] = (), message_id: str = "", in_reply_to: str = "",
                  references: Sequence[str] = (), extra: Optional[Dict[str, str]] = None,
                  sender: str = "", now: Optional[float] = None) -> bytes:
    """MIME bytes ready for DKIM and the relay. Every address is validated and no header may hold a newline."""
    for a in [from_addr, *to, *cc] + ([sender] if sender else []):
        if not valid_address(a):
            raise MailError("bad_address", "an address is not valid")
    if not to and not cc:
        raise MailError("no_recipients", "a message needs at least one recipient")
    if re.search(r"[\r\n]", subject) or any(re.search(r"[\r\n]", v) for v in (extra or {}).values()):
        raise MailError("bad_header", "a header may not contain a line break")
    m = EmailMessage(policy=policy.SMTP)
    m["From"], m["To"] = from_addr, ", ".join(to)
    if cc:
        m["Cc"] = ", ".join(cc)
    if sender and sender != from_addr:
        m["Sender"] = sender
    m["Subject"] = subject
    m["Date"] = formatdate(now if now is not None else time.time(), usegmt=True)
    m["Message-ID"] = f"<{message_id}>" if message_id else make_msgid(domain=domain_of(from_addr))
    if in_reply_to:
        m["In-Reply-To"] = f"<{in_reply_to}>"
    if references:
        m["References"] = " ".join(f"<{r}>" for r in list(references)[-20:])
    for k, v in (extra or {}).items():
        m[k] = v
    m.set_content(text or "")
    if html:
        m.add_alternative(html, subtype="html")
    for a in attachments:
        main, _, sub = (a.content_type if _CTYPE.match(a.content_type) else "application/octet-stream").partition("/")
        m.add_attachment(a.data, maintype=main, subtype=sub, filename=a.name)
    return m.as_bytes()

