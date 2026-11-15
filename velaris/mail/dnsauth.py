"""SPF (RFC 7208), DMARC (RFC 7489) and the Authentication-Results header (RFC 8601), over an injected resolver.

The resolver has four methods, each returning a list and raising DnsError only for a temporary failure
(timeout, SERVFAIL); a name that does not exist or has no such record returns []:

    txt(name) -> [str]    a(name) -> [ipv4 str]    aaaa(name) -> [ipv6 str]    mx(name) -> [host str]

Limits that are the RFC's own are enforced: 10 DNS-querying terms, 2 void lookups, 10 MX names, 10 deep
includes. Anything that cannot be decided is temperror or permerror, never pass. Not implemented: the
`ptr` mechanism (deprecated; it never matches here), `exp=` explanations. The organisational domain for
DMARC uses a short built-in list of two-label public suffixes (ponytail: swap in the full Public Suffix
List when a deployment needs one).
"""
from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass
from typing import Any, List, Optional

from velaris.mail.common import DnsError
from velaris.mail.dkim import DkimResult

DOMAIN = re.compile(r"(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z]{2,63}\Z")
_TWO_LABEL = frozenset("co.uk org.uk ac.uk gov.uk me.uk com.au net.au org.au edu.au gov.au co.in net.in org.in gov.in ac.in "
                       "firm.in gen.in ind.in co.jp ne.jp or.jp co.nz org.nz com.br com.cn com.sg com.hk co.za".split())
_QUAL = {"+": "pass", "-": "fail", "~": "softfail", "?": "neutral"}
_MECH = re.compile(r"(?P<mech>[a-z0-9]+)(?::(?P<dom>[^/\s]*))?(?:/(?P<c4>\d{1,2}))?(?://(?P<c6>\d{1,3}))?\Z", re.I)


class UnavailableResolver:
    """The default until a deployment supplies one: everything is a temporary failure, so nothing passes."""

    def _no(self, name: str) -> Any:
        raise DnsError("no resolver configured")

    txt = a = aaaa = mx = _no


@dataclass
class SpfResult:
    result: str                       # none neutral pass fail softfail temperror permerror
    domain: str = ""
    reason: str = ""


class _Perm(Exception):
    pass


class _Ctx:
    def __init__(self, resolver: Any, ip: Any, sender: str, helo: str) -> None:
        self.r, self.ip, self.sender, self.helo = resolver, ip, sender, helo
        self.lookups = 0
        self.voids = 0

    def count(self) -> None:
        self.lookups += 1
        if self.lookups > 10:
            raise _Perm("too many DNS lookups")

    def got(self, values: List[Any]) -> List[Any]:
        if not values:
            self.voids += 1
            if self.voids > 2:
                raise _Perm("too many void lookups")
        return values


def org_domain(domain: str) -> str:
    labels = domain.lower().strip(".").split(".")
    n = 3 if len(labels) >= 3 and ".".join(labels[-2:]) in _TWO_LABEL else 2
    return ".".join(labels[-n:])


def _macro(ctx: _Ctx, spec: str, domain: str) -> str:
    local, _, odom = ctx.sender.rpartition("@")
    ip = ctx.ip
    vals = {"s": ctx.sender, "l": local or "postmaster", "o": odom, "d": domain, "h": ctx.helo, "p": "unknown",
            "i": ".".join(ip.exploded.replace(":", "")) if ip.version == 6 else str(ip),
            "v": "ip6" if ip.version == 6 else "in-addr", "c": str(ip), "r": "unknown", "t": str(int(time.time()))}

    def sub(m: "re.Match[str]") -> str:
        v = vals[m.group(1).lower()]
        parts = re.split("[" + re.escape(m.group(4) or ".") + "]", v)
        if m.group(3):
            parts.reverse()
        if m.group(2):
            parts = parts[-int(m.group(2)):] if int(m.group(2)) else parts
        return ".".join(parts)

    out = re.sub(r"%\{([slodiphcrtv])(\d*)(r?)([.\-+,/_=]*)\}", sub, spec, flags=re.I)
    return out.replace("%%", "%").replace("%_", " ").replace("%-", "%20")


def _in(ip: Any, addr: str, c4: Optional[str], c6: Optional[str]) -> bool:
    try:
        a = ipaddress.ip_address(addr)
        if a.version != ip.version:
            return False
        bits = int((c4 if a.version == 4 else c6) or (32 if a.version == 4 else 128))
        return ip in ipaddress.ip_network(f"{a}/{bits}", strict=False)
    except ValueError:
        raise _Perm("bad address or prefix") from None


def _addresses(ctx: _Ctx, name: str) -> List[str]:
    ctx.count()
    return ctx.got(ctx.r.a(name) if ctx.ip.version == 4 else ctx.r.aaaa(name))


def _check(ctx: _Ctx, domain: str, depth: int) -> str:
    if depth > 10 or not DOMAIN.match(domain.lower()):
        raise _Perm("bad domain")
    records = [t for t in ctx.r.txt(domain) if re.match(r"v=spf1(\s|$)", t.strip(), re.I)]
    if not records:
        return "none"
    if len(records) > 1:
        raise _Perm("multiple SPF records")
    redirect = None
    for raw in records[0].split()[1:]:
        low = raw.lower()
        if low.startswith("redirect="):
            redirect = raw[9:]
            continue
        if re.match(r"[a-z][a-z0-9_.-]*=", low):
            continue                                              # exp= and unknown modifiers
        qual, term = ("+", raw) if raw[0] not in _QUAL else (raw[0], raw[1:])
        hit = False
        ipm = re.match(r"(ip4|ip6):([^\s/]+)(?:/(\d{1,3}))?\Z", term, re.I)
        if ipm:
            hit = _in(ctx.ip, ipm.group(2), ipm.group(3), ipm.group(3))
        else:
            m = _MECH.match(term)
            if not m:
                raise _Perm("bad term")
            mech, dom = m.group("mech").lower(), m.group("dom")
            target = _macro(ctx, dom, domain) if dom else domain
            if mech == "all":
                hit = True
            elif mech == "include":
                if not dom:
                    raise _Perm("include needs a domain")
                ctx.count()
                sub = _check(ctx, target, depth + 1)
                if sub in ("none", "permerror"):
                    raise _Perm("include of a domain without a usable record")
                if sub == "temperror":
                    raise DnsError("include")
                hit = sub == "pass"
            elif mech == "a":
                hit = any(_in(ctx.ip, x, m.group("c4"), m.group("c6")) for x in _addresses(ctx, target))
            elif mech == "mx":
                ctx.count()
                hosts = ctx.got(ctx.r.mx(target))
                if len(hosts) > 10:
                    raise _Perm("too many MX names")
                hit = any(_in(ctx.ip, x, m.group("c4"), m.group("c6")) for h in hosts
                          for x in (ctx.r.a(h) if ctx.ip.version == 4 else ctx.r.aaaa(h)))
            elif mech == "exists":
                ctx.count()
                hit = bool(ctx.got(ctx.r.a(target)))
            elif mech == "ptr":
                ctx.count()
            else:
                raise _Perm("unknown mechanism")
        if hit:
            return _QUAL[qual]
    if redirect:
        ctx.count()
        sub = _check(ctx, _macro(ctx, redirect, domain), depth + 1)
        if sub == "none":
            raise _Perm("redirect to a domain without a record")
        return sub
    return "neutral"


def check_spf(resolver: Any, ip: str, mail_from: str, helo: str) -> SpfResult:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return SpfResult("none", "", "no usable client address")
    if addr.version == 6 and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    sender = mail_from.lower() if "@" in mail_from else f"postmaster@{helo.lower()}"
    domain = sender.rsplit("@", 1)[1]
    if not DOMAIN.match(domain):
        return SpfResult("none", domain, "sender domain is not a domain name")
    ctx = _Ctx(resolver, addr, sender, helo)
    try:
        return SpfResult(_check(ctx, domain, 0), domain)
    except _Perm as e:
        return SpfResult("permerror", domain, str(e))
    except DnsError:
        return SpfResult("temperror", domain, "temporary DNS failure")


@dataclass
class DmarcResult:
    result: str                        # pass fail none temperror permerror
    policy: str = "none"               # none quarantine reject: what the owner asks for when result is fail
    domain: str = ""
    spf_aligned: bool = False
    dkim_aligned: bool = False
    reason: str = ""


# Suffixes where "last two labels" really is the registrable domain. Without the full Public Suffix
# List we cannot know that for other suffixes (e.g. com.br, co.jp), so relaxed alignment there is
# limited to a domain and its own subdomains: fail closed, never treat two unrelated registrants
# under an unknown suffix as one organisation.
_SIMPLE_TLDS = frozenset("com org net edu gov mil int info biz io dev app ai in us eu de fr nl se no ch".split())


def _aligned(a: str, b: str, mode: str) -> bool:
    a, b = a.lower().strip("."), b.lower().strip(".")
    if a == b:
        return True
    if mode == "s":
        return False
    la, lb = a.split("."), b.split(".")
    if la[-1] in _SIMPLE_TLDS and lb[-1] in _SIMPLE_TLDS and ".".join(la[-2:]) not in _TWO_LABEL \
            and ".".join(lb[-2:]) not in _TWO_LABEL:
        return org_domain(a) == org_domain(b)            # known suffix: the registrable domain is the last two labels
    short, long_ = (a, b) if len(la) < len(lb) else (b, a)
    return len(short.split(".")) >= 2 and short not in _TWO_LABEL and long_.endswith("." + short)


def _dmarc_record(resolver: Any, domain: str) -> Optional[dict]:
    recs = [t for t in resolver.txt(f"_dmarc.{domain}") if re.match(r"v=DMARC1\s*(;|$)", t.strip(), re.I)]
    if len(recs) != 1:
        return None
    tags = {}
    for part in recs[0].split(";"):
        k, _, v = part.partition("=")
        if k.strip():
            tags.setdefault(k.strip().lower(), v.strip())
    return tags if tags.get("p", "").lower() in ("none", "quarantine", "reject") else None


def check_dmarc(resolver: Any, from_domain: str, spf: SpfResult, dkim: List[DkimResult]) -> DmarcResult:
    from_domain = from_domain.lower()
    if not DOMAIN.match(from_domain):
        return DmarcResult("none", reason="the From domain is not a domain name")
    try:
        tags, found_at = _dmarc_record(resolver, from_domain), from_domain
        if tags is None and org_domain(from_domain) != from_domain:
            found_at = org_domain(from_domain)
            tags = _dmarc_record(resolver, found_at)
    except DnsError:
        return DmarcResult("temperror", domain=from_domain, reason="temporary DNS failure")
    if tags is None:
        return DmarcResult("none", domain=from_domain, reason="no DMARC record")
    spf_ok = spf.result == "pass" and _aligned(spf.domain, from_domain, tags.get("aspf", "r").lower()[:1])
    dkim_ok = any(d.result == "pass" and _aligned(d.domain, from_domain, tags.get("adkim", "r").lower()[:1]) for d in dkim)
    policy = tags["p"].lower()
    if from_domain != found_at and tags.get("sp", "").lower() in ("none", "quarantine", "reject"):
        policy = tags["sp"].lower()
    return DmarcResult("pass" if spf_ok or dkim_ok else "fail", policy, from_domain, spf_ok, dkim_ok)


def _tok(v: str) -> str:
    return re.sub(r"[^A-Za-z0-9@._+-]", "_", v)[:100]


def authentication_results(authserv: str, spf: SpfResult, mail_from: str, dkim: List[DkimResult], dmarc: DmarcResult,
                           from_domain: str) -> str:
    """The Authentication-Results value we record. Nothing from the message is trusted into its structure."""
    parts = [_tok(authserv), f"spf={spf.result} smtp.mailfrom={_tok(mail_from or '')}"]
    parts += [f"dkim={d.result} header.d={_tok(d.domain)} header.s={_tok(d.selector)}" for d in dkim] or ["dkim=none"]
    parts.append(f"dmarc={dmarc.result} header.from={_tok(from_domain)}" + (f" policy.dmarc={dmarc.policy}" if dmarc.result == "fail" else ""))
    return "; ".join(parts)
