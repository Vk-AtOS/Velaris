"""The SMTP receive side as a pure state machine: bytes in, reply lines out. No sockets, no threads, no clock.

feed(data) takes whatever arrived (any chunking) and returns the reply lines to send. The session never
relays: RCPT TO is accepted only for addresses `rcpt_check` says are ours ("ok"); anything else is refused
("relay" 550 5.7.1, "nouser" 550 5.1.1, "full" 452). There is no AUTH and no STARTTLS here: this is an
inbound-only edge; put TLS in front of it or let the listener's operator terminate it.

DATA ends only at CRLF "." CRLF (a bare LF never ends it, which closes the "SMTP smuggling" gap). Messages
over `max_size` are read and discarded, then refused with 552. When a complete message arrives `on_message`
returns the one reply for the whole transaction; a failure inside it becomes a temporary 451, because losing
mail is worse than asking the sender to retry.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from velaris.mail.mime import valid_address

logger = logging.getLogger("velaris.mail.smtp")

MAX_COMMAND = 1000
_PATH = re.compile(r"\s*(FROM|TO):\s*<([^<>]*)>\s*(.*)\Z", re.I | re.S)


@dataclass
class Envelope:
    helo: str
    peer_ip: str
    mail_from: str
    rcpts: List[str]
    data: bytes = field(default=b"", repr=False)


class SmtpSession:
    def __init__(self, *, hostname: str, peer_ip: str, rcpt_check: Callable[[str], str], max_size: int,
                 on_message: Callable[[Envelope], Tuple[int, str]], max_rcpts: int = 100, max_errors: int = 10) -> None:
        self.hostname, self.peer_ip, self.rcpt_check, self.max_size = hostname, peer_ip, rcpt_check, max_size
        self.on_message, self.max_rcpts, self.max_errors = on_message, max_rcpts, max_errors
        self.closed = False
        self._buf = b""
        self._helo: Optional[str] = None
        self._from: Optional[str] = None
        self._rcpts: List[str] = []
        self._data: Optional[bytearray] = None
        self._over = False
        self._errors = 0

    def greeting(self) -> bytes:
        return f"220 {self.hostname} ESMTP ready\r\n".encode()

    def _reset(self) -> None:
        self._from, self._rcpts, self._data, self._over = None, [], None, False

    def _err(self, code: int, text: str) -> bytes:
        self._errors += 1
        return f"{code} {text}\r\n".encode()

    def feed(self, data: bytes) -> List[bytes]:
        out: List[bytes] = []
        self._buf += data
        while self._buf and not self.closed:
            if self._data is not None:
                out += self._take_data()
                if self._data is not None:
                    break                                              # need more of the message
                continue
            line, sep, rest = self._buf.partition(b"\r\n")
            if not sep:
                if len(self._buf) > MAX_COMMAND:
                    self._buf = b""
                    out.append(self._err(500, "5.5.2 line too long"))
                break
            self._buf = rest
            out.append(self._command(line))
            if self._errors >= self.max_errors and not self.closed:
                out.append(b"421 4.7.0 too many errors, closing\r\n")
                self.closed = True
        return out

    # ── commands ─────────────────────────────────────────────────────────────
    def _command(self, raw: bytes) -> bytes:
        if len(raw) > MAX_COMMAND:
            return self._err(500, "5.5.2 line too long")
        line = raw.decode("ascii", "replace").strip()
        verb, _, arg = line.partition(" ")
        verb = verb.upper()
        if verb in ("HELO", "EHLO"):
            if not arg.strip() or len(arg) > 255:
                return self._err(501, "5.5.4 a host name is required")
            self._helo = arg.strip()
            self._reset()
            if verb == "HELO":
                return f"250 {self.hostname}\r\n".encode()
            return (f"250-{self.hostname} hello\r\n250-SIZE {self.max_size}\r\n250 8BITMIME\r\n").encode()
        if verb == "MAIL":
            return self._mail(arg)
        if verb == "RCPT":
            return self._rcpt(arg)
        if verb == "DATA":
            if self._from is None or not self._rcpts:
                return self._err(503, "5.5.1 need MAIL and at least one RCPT first")
            self._data, self._over = bytearray(b"\r\n"), False          # the leading CRLF lets an empty body end properly
            return b"354 end data with <CR><LF>.<CR><LF>\r\n"
        if verb == "RSET":
            self._reset()
            return b"250 2.0.0 ok\r\n"
        if verb == "NOOP":
            return b"250 2.0.0 ok\r\n"
        if verb == "QUIT":
            self.closed = True
            return f"221 2.0.0 {self.hostname} closing\r\n".encode()
        if verb in ("VRFY", "EXPN", "HELP", "STARTTLS", "AUTH"):
            return self._err(502, "5.5.1 not available")
        return self._err(500, "5.5.1 command not recognised")

    def _mail(self, arg: str) -> bytes:
        if self._helo is None:
            return self._err(503, "5.5.1 say HELO or EHLO first")
        if self._from is not None:
            return self._err(503, "5.5.1 a transaction is already open")
        m = _PATH.match(arg)
        if not m or m.group(1).upper() != "FROM":
            return self._err(501, "5.5.4 syntax: MAIL FROM:<address>")
        addr = m.group(2).strip().lower()
        if addr and not valid_address(addr):
            return self._err(501, "5.1.7 bad sender address")
        for param in m.group(3).split():
            k, _, v = param.partition("=")
            if k.upper() == "SIZE" and v.isdigit():
                if int(v) > self.max_size:
                    return self._err(552, "5.3.4 message size exceeds the limit")
            elif k.upper() == "BODY" and v.upper() in ("7BIT", "8BITMIME"):
                continue
            else:
                return self._err(555, "5.5.4 parameter not supported")
        self._from, self._rcpts = addr, []
        return b"250 2.1.0 ok\r\n"

    def _rcpt(self, arg: str) -> bytes:
        if self._from is None:
            return self._err(503, "5.5.1 need MAIL first")
        m = _PATH.match(arg)
        if not m or m.group(1).upper() != "TO" or m.group(3).strip():
            return self._err(501, "5.5.4 syntax: RCPT TO:<address>")
        addr = m.group(2).strip().lower()
        if not valid_address(addr):
            return self._err(501, "5.1.3 bad recipient address")
        if len(self._rcpts) >= self.max_rcpts:
            return self._err(452, "4.5.3 too many recipients")
        verdict = self.rcpt_check(addr)
        if verdict == "ok":
            if addr not in self._rcpts:
                self._rcpts.append(addr)
            return b"250 2.1.5 ok\r\n"
        if verdict == "full":
            return self._err(452, "4.2.2 mailbox full, try later")
        if verdict == "nouser":
            return self._err(550, "5.1.1 no such mailbox here")
        return self._err(550, "5.7.1 relaying is not allowed")

    # ── message data ─────────────────────────────────────────────────────────
    def _take_data(self) -> List[bytes]:
        assert self._data is not None
        buf, self._buf = self._buf, b""
        self._data += buf
        end = self._data.find(b"\r\n.\r\n")
        if end < 0:
            if len(self._data) > self.max_size + 16:
                self._over = True
                self._data = bytearray(self._data[-4:])                 # keep only enough to spot the terminator
            return []
        body = bytes(self._data[2:end + 2])
        self._buf = bytes(self._data[end + 5:])
        env = Envelope(self._helo or "", self.peer_ip, self._from or "", list(self._rcpts))
        self._reset()
        if self._over or len(body) > self.max_size:
            return [self._err(552, "5.3.4 message size exceeds the limit")]
        env.data = (b"\r\n" + body).replace(b"\r\n..", b"\r\n.")[2:]          # undo dot-stuffing
        try:
            code, text = self.on_message(env)
        except Exception as e:                                          # any failure: ask the sender to retry
            logger.warning("delivery failed: %s", type(e).__name__)
            code, text = 451, "4.3.0 local error, try again later"
        return [f"{code} {text}\r\n".encode()]
