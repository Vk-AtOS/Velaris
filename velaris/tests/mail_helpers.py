"""Shared fixtures for the test_mail_* files: a controllable clock, fake DNS, a recording relay, mailboxes."""
from typing import Any, Dict, List

from velaris.core.access import Caller
from velaris.mail.common import DnsError
from velaris.mail.inbound import InboundPipeline
from velaris.mail.outbound import Outbound
from velaris.mail.store import MailStore

ORG = "acme"
ADMIN = Caller("admin", ORG, frozenset({"mail_admin"}))
ALICE = Caller("alice", ORG)
BOB = Caller("bob", ORG)
CAROL = Caller("carol", ORG, frozenset({"mail_approver"}))


class Clock:
    def __init__(self, t: float = 1_800_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class FakeResolver:
    """zone: {"name": ["txt", ...]} for TXT; a/aaaa/mx dicts; names in `down` raise a temporary failure."""

    def __init__(self, txt: Dict[str, List[str]] = None, a: Dict[str, List[str]] = None, aaaa: Dict[str, List[str]] = None,
                 mx: Dict[str, List[str]] = None, down: tuple = ()) -> None:
        self.z = {"txt": txt or {}, "a": a or {}, "aaaa": aaaa or {}, "mx": mx or {}}
        self.down, self.queries = set(down), 0

    def _get(self, kind: str, name: str) -> List[str]:
        self.queries += 1
        if name in self.down:
            raise DnsError(name)
        return list(self.z[kind].get(name, []))

    def txt(self, n): return self._get("txt", n)
    def a(self, n): return self._get("a", n)
    def aaaa(self, n): return self._get("aaaa", n)
    def mx(self, n): return self._get("mx", n)


class FakeRelay:
    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []
        self.fail: Any = None

    def send(self, mail_from, rcpts, raw):
        if self.fail:
            raise self.fail
        self.sent.append({"from": mail_from, "rcpts": list(rcpts), "raw": raw})
        return {}


def raw_mail(frm="x@ext.org", to="a@acme.com", subject="hello", body="hi there", mid="m1@ext.org", extra="", ctype="text/plain; charset=utf-8") -> bytes:
    return (f"From: {frm}\r\nTo: {to}\r\nSubject: {subject}\r\nMessage-ID: <{mid}>\r\nDate: Tue, 10 Nov 2026 10:00:00 +0000\r\n"
            f"{extra}MIME-Version: 1.0\r\nContent-Type: {ctype}\r\n\r\n{body}\r\n").encode()


def verify_domain(store, caller, domain):
    """Claim a domain and prove it with a fake DNS that holds the challenge TXT record."""
    tok = store.claim_domain(caller, domain)["record"]["value"]
    return store.verify_domain(caller, domain, FakeResolver(txt={f"_velaris.{domain}": [tok]}))


def make_world(clock=None, relay=None, resolver=None, settings=None):
    """(store, outbound, inbound, clock, relay) with an admin-configured org, mailboxes alice@ and bob@acme.com."""
    clock = clock or Clock()
    store = MailStore(clock=clock)
    verify_domain(store, ADMIN, "acme.com")
    store.set_org_settings(ADMIN, {"local_domains": ["acme.com"], **(settings or {})})
    relay = relay if relay is not None else FakeRelay()
    ob = Outbound(store, relay=relay, clock=clock)
    ib = InboundPipeline(store, resolver or FakeResolver(), outbound=ob)
    ob.local_delivery = ib.deliver_local
    boxes = {n: store.create_mailbox(ADMIN, f"{n}@acme.com", owner_id=n) for n in ("alice", "bob")}
    return store, ob, ib, clock, relay, boxes
