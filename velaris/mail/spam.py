"""Spam scoring by transparent rules: every rule has a name and a weight, and the result lists the ones that fired.

score >= threshold (org setting spam_threshold, default 5) goes to Quarantine, where it can be read and
rescued. No learning, no hidden state: change a weight here and the behaviour changes exactly that much.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Sequence, Tuple

from velaris.mail.mime import Parsed, domain_of

_EXEC_EXT = re.compile(r"\.(exe|scr|js|jse|vbs|vbe|bat|cmd|com|pif|jar|msi|ps1|hta|lnk)\Z", re.I)
_PHRASES = re.compile(r"\b(viagra|cialis|lottery|you have won|act now|100% free|click here|wire transfer|"
                      r"claim your prize|crypto giveaway|work from home|dear beneficiary)\b", re.I)
_IP_URL = re.compile(r"https?://\d{1,3}(?:\.\d{1,3}){3}")
_ADDR = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")

Rule = Tuple[str, float, Callable[[Parsed, Dict[str, Any]], bool]]

RULES: List[Rule] = [
    ("spf_fail", 3.0, lambda p, a: a.get("spf") == "fail"),
    ("spf_softfail", 1.0, lambda p, a: a.get("spf") == "softfail"),
    ("dkim_fail", 2.0, lambda p, a: "fail" in a.get("dkim", [])),
    ("dmarc_fail", 3.0, lambda p, a: a.get("dmarc") == "fail"),
    ("dmarc_policy_reject", 2.0, lambda p, a: a.get("dmarc") == "fail" and a.get("dmarc_policy") == "reject"),
    ("no_message_id", 1.0, lambda p, a: p.message_id.startswith("no-id-")),
    ("no_date", 1.0, lambda p, a: p.date_ts is None),
    ("no_from", 3.0, lambda p, a: not p.from_addr),
    ("reply_to_differs", 1.0, lambda p, a: bool(p.headers.get("reply-to")) and bool(p.from_addr) and
        (_ADDR.search(p.headers["reply-to"]) is not None) and _ADDR.search(p.headers["reply-to"]).group(1).lower() != domain_of(p.from_addr)),
    ("shouting_subject", 1.0, lambda p, a: len(p.subject) > 8 and p.subject.upper() == p.subject and any(c.isalpha() for c in p.subject)),
    ("spam_phrases", 2.0, lambda p, a: bool(_PHRASES.search(p.subject + " " + p.text[:5000]))),
    ("html_only", 0.5, lambda p, a: bool(p.html) and not p.text),
    ("many_links", 1.0, lambda p, a: len(p.link_hosts) > 15),
    ("ip_address_link", 2.0, lambda p, a: bool(_IP_URL.search(p.html + p.text[:5000]))),
    ("name_spoofs_address", 2.0, lambda p, a: bool(p.from_name) and (m := _ADDR.search(p.from_name)) is not None
        and m.group(1).lower() != domain_of(p.from_addr)),
    ("executable_attachment", 4.0, lambda p, a: any(_EXEC_EXT.search(x.name) for x in p.attachments)),
    ("many_images_blocked", 0.5, lambda p, a: p.blocked_images > 10),
    ("trusted_domain_authenticated", -2.0, lambda p, a: a.get("dmarc") == "pass" and domain_of(p.from_addr) in a.get("trusted", ())),
]


def score(p: Parsed, auth: Dict[str, Any], trusted: Sequence[str] = ()) -> Tuple[float, List[Dict[str, Any]]]:
    """(total, [{"rule", "weight"}...]) for the rules that fired. `auth`: spf, dkim (list of results), dmarc, dmarc_policy."""
    a = {**auth, "trusted": tuple(trusted)}
    report = [{"rule": n, "weight": w} for n, w, fn in RULES if fn(p, a)]
    return round(sum(r["weight"] for r in report), 2), report
