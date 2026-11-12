"""DKIM (RFC 6376) signing and verification, written from the RFC. rsa-sha256 and ed25519-sha256 (RFC 8463);
rsa-sha1 is refused (RFC 8301). Uses `cryptography`, which is a runtime requirement.

The org signing key is an RSA-2048 key kept owner-only under VELARIS_DATA/mail/dkim-<selector>.pem and
created on first use; dns_record() gives the TXT value to publish at <selector>._domainkey.<domain>.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from velaris.mail.common import DnsError
from velaris.intel.paths import data_dir, private_dir, read_private, write_private

SIGN_HEADERS = ("from", "to", "cc", "subject", "date", "message-id", "in-reply-to", "references", "mime-version",
                "content-type", "content-transfer-encoding", "sender")
MAX_SIGS = 5


@dataclass
class DkimResult:
    result: str                      # pass fail none temperror permerror
    domain: str = ""
    selector: str = ""
    reason: str = ""


def split_message(raw: bytes) -> Tuple[List[Tuple[str, str]], bytes]:
    """([(name, raw value after the colon, folds kept, no final CRLF)], body)."""
    head, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        head, body = raw.rstrip(b"\r\n"), b""
    out: List[Tuple[str, str]] = []
    for line in head.decode("latin-1").split("\r\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] = (out[-1][0], out[-1][1] + "\r\n" + line)
        elif ":" in line:
            n, _, v = line.partition(":")
            out.append((n, v))
    return out, body


def canon_header(name: str, value: str, relaxed: bool) -> str:
    if not relaxed:
        return f"{name}:{value}\r\n"
    v = re.sub(r"[ \t]+", " ", value.replace("\r\n", "")).strip(" \t")
    return f"{name.lower().strip()}:{v}\r\n"


def canon_body(body: bytes, relaxed: bool) -> bytes:
    lines = body.split(b"\r\n")
    if relaxed:
        lines = [re.sub(rb"[ \t]+", b" ", ln).rstrip(b" ") for ln in lines]
    while lines and lines[-1] == b"":
        lines.pop()
    if not lines:
        return b"" if relaxed else b"\r\n"
    return b"\r\n".join(lines) + b"\r\n"


def _select(headers: List[Tuple[str, str]], names: List[str]) -> List[Tuple[str, str]]:
    """RFC 6376 5.4.2: each name picks the next unused instance from the bottom."""
    used: Dict[str, int] = {}
    out = []
    for want in names:
        w = want.strip().lower()
        idx = [i for i, (n, _) in enumerate(headers) if n.strip().lower() == w]
        k = used.get(w, 0)
        if k < len(idx):
            out.append(headers[idx[len(idx) - 1 - k]])
        used[w] = k + 1
    return out


def _b64(s: str) -> bytes:
    return base64.b64decode(re.sub(r"\s+", "", s) + "=" * (-len(re.sub(r"\s+", "", s)) % 4), validate=False)


# ── keys ─────────────────────────────────────────────────────────────────────

def load_or_create_key(selector: str) -> rsa.RSAPrivateKey:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", selector):
        raise ValueError("bad selector")
    path = private_dir(data_dir() / "mail") / f"dkim-{selector}.pem"
    try:
        pem = read_private(path)
    except FileNotFoundError:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        try:
            write_private(path, pem, exclusive=True)
        except FileExistsError:
            pem = read_private(path)
    key = serialization.load_pem_private_key(pem, None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("the DKIM key is not RSA")
    return key


def dns_record(key: rsa.RSAPrivateKey) -> str:
    der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return "v=DKIM1; k=rsa; p=" + base64.b64encode(der).decode()


# ── signing ──────────────────────────────────────────────────────────────────

def sign(raw: bytes, key: rsa.RSAPrivateKey, domain: str, selector: str, *, now: Optional[float] = None) -> bytes:
    """`raw` with a DKIM-Signature header (relaxed/relaxed, rsa-sha256) put on top."""
    headers, body = split_message(raw)
    present = [n.lower() for n, _ in headers]
    names = [h for h in SIGN_HEADERS if h in present]
    if "from" not in names:
        raise ValueError("a message without From cannot be signed")
    bh = base64.b64encode(hashlib.sha256(canon_body(body, True)).digest()).decode()
    t = int(time.time() if now is None else now)
    value = (f" v=1; a=rsa-sha256; c=relaxed/relaxed; d={domain}; s={selector}; t={t};\r\n\th={':'.join(names)};\r\n\tbh={bh};\r\n\tb=")
    data = "".join(canon_header(n, v, True) for n, v in _select(headers, names)) + canon_header("DKIM-Signature", value, True).rstrip("\r\n")
    sig = base64.b64encode(key.sign(data.encode("latin-1"), padding.PKCS1v15(), hashes.SHA256())).decode()
    folded = "\r\n\t".join(sig[i:i + 64] for i in range(0, len(sig), 64))
    return b"DKIM-Signature:" + (value + folded).encode("latin-1") + b"\r\n" + raw


# ── verification ─────────────────────────────────────────────────────────────

def _tags(value: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in value.replace("\r\n", "").split(";"):
        k, _, v = part.partition("=")
        k = k.strip()
        if k and k not in out:
            out[k] = v.strip()
    return out


def _key_for(resolver: Any, selector: str, domain: str) -> Tuple[str, Any]:
    recs = resolver.txt(f"{selector}._domainkey.{domain}")
    for rec in recs:
        t = _tags(rec)
        if t.get("v", "DKIM1") != "DKIM1" or t.get("k", "rsa") not in ("rsa", "ed25519"):
            continue
        if not t.get("p"):
            raise ValueError("the key was revoked")
        try:
            blob = _b64(t["p"])
            if t.get("k", "rsa") == "ed25519":
                return "ed25519", Ed25519PublicKey.from_public_bytes(blob)
            pub = serialization.load_der_public_key(blob)
        except (ValueError, binascii.Error):
            raise ValueError("the key could not be read") from None
        if not isinstance(pub, rsa.RSAPublicKey) or pub.key_size < 1024:
            raise ValueError("the key is too weak")
        return "rsa", pub
    raise LookupError("no key")


def _verify_one(raw_headers: List[Tuple[str, str]], body: bytes, sig_value: str, resolver: Any, now: float) -> DkimResult:
    t = _tags(sig_value)
    d, s = t.get("d", "").lower(), t.get("s", "")
    res = lambda r, why="": DkimResult(r, d, s, why)          # noqa: E731
    algo = t.get("a", "").lower()
    if t.get("v") != "1" or not all(t.get(k) for k in ("a", "b", "bh", "d", "s", "h")):
        return res("permerror", "malformed signature")
    if algo not in ("rsa-sha256", "ed25519-sha256"):
        return res("permerror", "unsupported algorithm")
    if "from" not in [h.strip().lower() for h in t["h"].split(":")]:
        return res("permerror", "From is not signed")
    if t.get("x", "").isdigit() and now > int(t["x"]):
        return res("fail", "signature expired")
    if t.get("i") and not t["i"].lower().rsplit("@", 1)[-1].endswith(d):
        return res("permerror", "i= is outside d=")
    c = t.get("c", "simple/simple").lower().split("/")
    hrelaxed, brelaxed = c[0] == "relaxed", (c[1] if len(c) > 1 else "simple") == "relaxed"
    cbody = canon_body(body, brelaxed)
    if t.get("l", "").isdigit():
        cbody = cbody[:int(t["l"])]
    try:
        bh_ok = _b64(t["bh"]) == hashlib.sha256(cbody).digest()
    except binascii.Error:
        return res("permerror", "malformed body hash")
    if not bh_ok:
        return res("fail", "body hash did not verify")
    try:
        kind, pub = _key_for(resolver, s, d)
    except DnsError:
        return res("temperror", "temporary DNS failure")
    except LookupError:
        return res("permerror", "no key published")
    except ValueError as e:
        return res("permerror", str(e))
    if (kind == "ed25519") != (algo == "ed25519-sha256"):
        return res("permerror", "key type does not match the algorithm")
    own = next(v for n, v in raw_headers if n.lower() == "dkim-signature" and _tags(v).get("b") == t["b"])
    stripped = re.sub(r"(^|;)(\s*b\s*=)[^;]*", r"\1\2", own, count=1)
    data = ("".join(canon_header(n, v, hrelaxed) for n, v in _select(raw_headers, t["h"].split(":")))
            + canon_header("DKIM-Signature", stripped, hrelaxed).rstrip("\r\n")).encode("latin-1")
    try:
        sig = _b64(t["b"])
        if kind == "rsa":
            pub.verify(sig, data, padding.PKCS1v15(), hashes.SHA256())
        else:
            pub.verify(sig, hashlib.sha256(data).digest())
    except (InvalidSignature, binascii.Error, ValueError):
        return res("fail", "signature did not verify")
    return res("pass")


def verify_all(raw: bytes, resolver: Any, now: Optional[float] = None) -> List[DkimResult]:
    headers, body = split_message(raw)
    now = time.time() if now is None else now
    sigs = [v for n, v in headers if n.strip().lower() == "dkim-signature"][:MAX_SIGS]
    return [_verify_one(headers, body, v, resolver, now) for v in sigs] or [DkimResult("none")]
