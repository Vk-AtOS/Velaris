"""Receiving mail from the internet: the delivery pipeline and a small asyncio listener.

Pipeline (InboundPipeline.deliver), per message: size and loop checks, parse, SPF, DKIM, DMARC, an
Authentication-Results line, spam score, then one copy per local recipient into its Inbox, or into
Quarantine when the score reaches the org threshold or DMARC fails with p=quarantine/reject (recoverable: nothing
is bounced for a policy verdict). Then rules and the vacation responder run on Inbox mail. Temporary
trouble is a 451 so the sender retries; redelivery is harmless because storage de-duplicates by Message-ID.

Run the listener (NOT started by importing this module or by any test):

    python3.11 -m velaris.mail.inbound [--bind 127.0.0.1] [--port 2525] [--hostname mx.example.com]

--bind defaults to 127.0.0.1. Binding a public address, and port 25, is the operator's decision (and port 25
needs a privileged port, a public IP, reverse DNS and a TLS-terminating front, none of which are done here).
Without dnspython installed SPF/DKIM/DMARC cannot be checked and every verdict is temperror (nothing passes).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
from typing import Any, Optional, Tuple

from velaris.core.access import deployment_org
from velaris.mail import dkim, dsn, rules, spam
from velaris.mail.common import DnsError, MailError, audit
from velaris.mail.dnsauth import DmarcResult, SpfResult, UnavailableResolver, authentication_results, check_dmarc, check_spf
from velaris.mail.mime import domain_of, parse_message
from velaris.mail.smtp import Envelope, SmtpSession
from velaris.mail.store import MailStore

logger = logging.getLogger("velaris.mail.inbound")
MAX_HOPS = 30


class InboundPipeline:
    def __init__(self, store: MailStore, resolver: Any = None, *, outbound: Any = None, authserv: str = "velaris.local") -> None:
        self.store, self.resolver, self.outbound, self.authserv = store, resolver or UnavailableResolver(), outbound, authserv

    def _org(self) -> str:
        return deployment_org() or ""

    def max_size(self) -> int:
        org = self._org()
        return self.store.org_settings(org)["max_message_bytes"] if org else 25 * 1024 * 1024

    def rcpt_check(self, addr: str) -> str:
        """"ok" | "relay" (not our domain: never relayed) | "nouser" | "full"."""
        mb = self.store.deliverable_mailbox(addr)
        if mb is not None:
            if self.store.used_bytes(mb["id"]) >= mb["quota_bytes"]:
                return "full"
            return "ok"
        org = self._org()
        if org and domain_of(addr) in self.store.org_settings(org)["local_domains"]:
            return "nouser"
        return "relay"

    def session(self, peer_ip: str, hostname: str = "velaris.local") -> SmtpSession:
        return SmtpSession(hostname=hostname, peer_ip=peer_ip, rcpt_check=self.rcpt_check, max_size=self.max_size(), on_message=self.deliver)

    def authenticate(self, env: Envelope, p: Any, now: float) -> Tuple[SpfResult, list, DmarcResult, str]:
        try:
            spf = check_spf(self.resolver, env.peer_ip, env.mail_from, env.helo)
            dk = dkim.verify_all(env.data, self.resolver, now)
        except DnsError:
            spf, dk = SpfResult("temperror", domain_of(env.mail_from)), [dkim.DkimResult("temperror")]
        from_domain = domain_of(p.from_addr)
        dm = check_dmarc(self.resolver, from_domain, spf, dk) if from_domain else DmarcResult("none")
        return spf, dk, dm, authentication_results(self.authserv, spf, env.mail_from, dk, dm, from_domain)

    def deliver(self, env: Envelope) -> Tuple[int, str]:
        now = self.store.clock()
        boxes = [mb for mb in (self.store.deliverable_mailbox(r) for r in env.rcpts) if mb is not None]
        if not boxes:
            return 550, "5.1.1 no such mailbox here"
        settings = self.store.org_settings(boxes[0]["org"])
        p = parse_message(env.data, max_attachment=settings["max_attachment_bytes"], fallback_ts=now)
        if p.received_count > MAX_HOPS:
            return 554, "5.4.6 too many hops: mail loop"
        spf, dk, dm, ar = self.authenticate(env, p, now)
        auth = {"spf": spf.result, "dkim": [d.result for d in dk], "dmarc": dm.result, "dmarc_policy": dm.policy}
        total, report = spam.score(p, auth, settings["local_domains"] + settings["allowlisted_domains"])
        quarantine = total >= settings["spam_threshold"] or (dm.result == "fail" and dm.policy in ("quarantine", "reject"))
        temp = perm = False
        for mb in boxes:
            try:
                pk = self.store.deliver(mb["id"], p, folder_role="quarantine" if quarantine else "inbox", auth_results=ar, spam_score=total, spam_report=report)
            except MailError as e:
                perm = perm or e.code == "quota_exceeded"
                temp = temp or e.code != "quota_exceeded"
                continue
            except sqlite3.Error as e:
                logger.warning("delivery storage failed: %s", type(e).__name__)
                temp = True
                continue
            if pk:
                try:        # a bounce of something we sent marks that submission, whatever the spam verdict on the report: it only
                    dsn.apply(self.store, mb, env.data)       # counts if it quotes the random Message-ID of one of our own sent messages
                except (MailError, sqlite3.Error, ValueError, KeyError) as e:
                    logger.warning("bounce handling failed: %s", type(e).__name__)
            if pk and not quarantine:
                try:
                    rules.apply_inbound(self.store, self.outbound, mb, pk)
                except (MailError, sqlite3.Error, ValueError, KeyError) as e:       # a rule problem must never lose mail
                    logger.warning("rules failed: %s", type(e).__name__)
        audit("inbound.delivered", "smtp", boxes[0]["org"], recipients=len(boxes), size=len(env.data), quarantined=quarantine,
              spf=spf.result, dmarc=dm.result, score=total)
        if temp:
            return 451, "4.3.0 temporary local problem, try again later"
        if perm and len(boxes) == 1:
            return 552, "5.2.2 mailbox full"
        return 250, "2.0.0 queued"

    def deliver_local(self, mb: Any, raw: bytes, mail_from: str) -> Optional[str]:
        """Mail from this deployment's own outbox to a local mailbox: no SPF/DKIM/spam, but rules and vacation apply."""
        p = parse_message(raw, fallback_ts=self.store.clock())
        pk = self.store.deliver(mb["id"], p, auth_results=f"{self.authserv}; internal=trusted", source="inbound")
        if pk:
            try:
                dsn.apply(self.store, mb, raw)
                rules.apply_inbound(self.store, self.outbound, mb, pk)
            except (MailError, sqlite3.Error, ValueError, KeyError) as e:
                logger.warning("rules failed: %s", type(e).__name__)
        return pk


def dnspython_resolver() -> Any:
    """A resolver on dnspython when it is installed (optional), else the one that answers temperror to everything."""
    try:
        import dns.exception
        import dns.resolver
    except ImportError:
        return UnavailableResolver()

    class _R:
        def _q(self, name: str, rtype: str) -> list:
            try:
                return list(dns.resolver.resolve(name, rtype, lifetime=5.0))
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                return []
            except (dns.exception.Timeout, dns.resolver.NoNameservers, dns.exception.DNSException):
                raise DnsError(name) from None

        def txt(self, name: str) -> list:
            return ["".join(s.decode("utf-8", "replace") for s in r.strings) for r in self._q(name, "TXT")]

        def a(self, name: str) -> list:
            return [r.address for r in self._q(name, "A")]

        def aaaa(self, name: str) -> list:
            return [r.address for r in self._q(name, "AAAA")]

        def mx(self, name: str) -> list:
            return [str(r.exchange).rstrip(".") for r in self._q(name, "MX")]

    return _R()


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, pipeline: InboundPipeline, hostname: str, idle: float) -> None:
    peer = (writer.get_extra_info("peername") or ("0.0.0.0",))[0]
    s = pipeline.session(peer, hostname)
    try:
        writer.write(s.greeting())
        while not s.closed:
            data = await asyncio.wait_for(reader.read(65536), idle)
            if not data:
                break
            for line in await asyncio.to_thread(s.feed, data):
                writer.write(line)
            await writer.drain()
    except (asyncio.TimeoutError, ConnectionError, OSError):
        pass
    finally:
        writer.close()


async def serve(pipeline: InboundPipeline, host: str = "127.0.0.1", port: int = 2525, hostname: str = "velaris.local",
                idle: float = 300.0, max_connections: int = 100) -> None:
    sem = asyncio.Semaphore(max_connections)

    async def handler(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        async with sem:
            await _handle(r, w, pipeline, hostname, idle)

    server = await asyncio.start_server(handler, host, port)
    logger.info("inbound SMTP listening on %s:%s", host, port)
    async with server:
        await server.serve_forever()


def main(argv: Optional[list] = None) -> None:                  # pragma: no cover
    ap = argparse.ArgumentParser(description="Velaris inbound SMTP listener (not started automatically).")
    ap.add_argument("--bind", default="127.0.0.1", help="address to listen on (default 127.0.0.1; public addresses are your decision)")
    ap.add_argument("--port", type=int, default=2525)
    ap.add_argument("--hostname", default="velaris.local")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve(InboundPipeline(MailStore(), dnspython_resolver(), authserv=a.hostname), a.bind, a.port, a.hostname))


if __name__ == "__main__":                                       # pragma: no cover
    main()
