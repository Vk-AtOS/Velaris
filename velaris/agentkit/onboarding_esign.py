"""Evidence, seal and verification for click-to-sign requests. Pure functions over bytes and dicts.

WHAT A SIGNATURE IS HERE
------------------------
The signer's "signature" is EVIDENCE: they proved control of an e-mail token (and optionally a one-time code), saw
the document's SHA-256, accepted a versioned consent text, typed their name under an intent statement, and we kept
the time, a keyed hash of their IP address and of their user agent. That can help prove a contract was formed
(IT Act 2000 s.10A: a contract is not unenforceable only because it was formed electronically) and who accepted it.
It is NOT a secure electronic signature or digital signature under IT Act s.3 / s.3A (Aadhaar eSign or a DSC),
and it does not carry the statutory presumption those carry. LEGAL_NOTICE says so and is attached to every
result. Whether this is enough for a given document (offer letter, appointment letter, anything stamped,
anything affecting property) needs a lawyer; stamp duty in Tamil Nadu is a separate question for the same lawyer.

THE SEAL
--------
When the last signer has signed, the platform seals the document:
  * an evidence page is appended to the PDF (an incremental update, so the original bytes stay a prefix);
  * a hash chain is computed:  h0 = SHA256("velaris-seal-v1\\n" + document_sha256),
                               h_i = SHA256(h_(i-1) + evidence_sha256_i)   (evidence in the order signed),
    seal_hash = h_n. The seal hash is also written to the tamper-evident trace (velaris.intel.trace), which
    is what makes the chain anchored outside this agent's own state file.
  * the PLATFORM-CERTIFICATE PDF signature (PAdES) is a HOOK: platform_signature() returns `not_configured`
    unless a PdfSigner is injected. Nothing pretends to be cryptographically signed when it is not.

PLUGGING IN A REAL SIGNATURE
----------------------------
pyHanko (MIT, not installed here): implement PdfSigner.sign_pdf(pdf, evidence_digest) with pyhanko.sign.signers:
load the organisation's key and certificate (ideally an HSM/PKCS#11 token), call `sign_pdf` on an
IncrementalPdfFileWriter over the sealed bytes with a PdfSignatureMetadata (PAdES baseline B-B, optionally B-T with
an RFC 3161 timestamp authority) and return the output bytes. With a self-signed certificate readers show a warning;
with a CA-issued one they show it trusted. Aadhaar eSign (needs a licensed ASP and the CCA eSign API): pyHanko's
interrupted signing prepares the document and returns the digest of the byte range; the digest goes to the ASP
(the signer authenticates with Aadhaar OTP there), the ASP returns a CMS container, and pyHanko embeds it. In that
route the signer, not the platform, holds the s.3A-grade signature and a request would carry `signature_level:
"aadhaar_esign"`. Neither is built here.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from velaris.agentkit.onboarding_common import canonical, sha256_hex
from velaris.agentkit.onboarding_adapters import PdfSigner
from velaris.agentkit.onboarding_pdf import Line, PdfError, append_page, build_pdf, parse_pdf

logger = logging.getLogger("velaris.agentkit.onboarding_esign")

LEGAL_NOTICE = ("NOT A LEGAL OPINION. Click-to-accept evidence (e-mail token, consent, time, hashed IP, document hash) "
                "can help show a contract was formed electronically (IT Act 2000 s.10A). It is NOT a secure "
                "electronic signature or digital signature under IT Act s.3/s.3A (Aadhaar eSign or a DSC) and "
                "does not carry their legal presumption. Whether it is enough for a particular document, and "
                "stamp duty, need a lawyer.")

CONSENT_TEXTS = {"v1": ("I agree to review and accept this document by electronic means. I understand that my "
                        "acceptance is recorded with my e-mail address, the time, and a hash of my network address "
                        "and browser, and that this is an electronic acceptance, not a digital signature certificate.")}
CURRENT_CONSENT = "v1"
INTENT_TEXTS = {"v1": "I, {name}, have read the document with SHA-256 {hash} and I intend to be bound by it."}
CURRENT_INTENT = "v1"

SIGNER_FLOW = {"sent": ("viewed", "declined"), "viewed": ("consented", "declined"), "consented": ("signed", "declined")}


def may_move(frm: str, to: str) -> bool:
    return to in SIGNER_FLOW.get(frm, ())


def intent_statement(version: str, name: str, doc_hash: str) -> str:
    return INTENT_TEXTS[version].format(name=name, hash=doc_hash)


def norm_name(name: str) -> str:
    return " ".join(str(name).casefold().split())


def evidence_hash(evidence: Dict[str, Any]) -> str:
    return sha256_hex(canonical(evidence))


def chain(doc_hash: str, evidence_hashes: List[str]) -> List[str]:
    """[h0, h1, ..., hn]; the last element is the seal hash."""
    h = hashlib.sha256(b"velaris-seal-v1\n" + doc_hash.encode()).hexdigest()
    out = [h]
    for e in evidence_hashes:
        h = hashlib.sha256((h + e).encode()).hexdigest()
        out.append(h)
    return out


def evidence_lines(title: str, doc_hash: str, evidence: List[Dict[str, Any]], hashes: List[str], seal_hash: str,
                   created_at: str) -> List[Line]:
    lines: List[Line] = [("h1", "Certificate of electronic acceptance"), ("p", title), ("gap", ""),
                         ("b", "Document SHA-256"), ("p", doc_hash), ("b", "Seal hash (chain over the evidence below)"),
                         ("p", seal_hash), ("p", f"Request created {created_at}"), ("gap", "")]
    for ev, h in zip(evidence, hashes):
        lines += [("h2", f"Signer: {ev['name']}"), ("p", f"E-mail {ev['email']} | role {ev['role']}"),
                  ("p", f"Authentication: {', '.join(ev['auth_methods'])} | viewed {ev['viewed_at']} | consented "
                        f"{ev['consent_at']} (text {ev['consent_text_version']}) | signed {ev['signed_at']}"),
                  ("p", f"Intent: {ev['intent_statement']}"),
                  ("p", f"IP hash {ev['ip_hash'][:16]}... | user-agent hash {ev['user_agent_hash'][:16]}..."),
                  ("p", f"Evidence SHA-256 {h}"), ("gap", "")]
    lines += [("b", "Legal notice"), ("p", LEGAL_NOTICE)]
    return lines


def seal(original: bytes, title: str, evidence: List[Dict[str, Any]], created_at: str, sealed_at: str) -> Dict[str, Any]:
    """Compute the chain and the sealed PDF. {"chain", "seal_hash", "evidence_hashes", "sealed_pdf", "evidence_page", ...}.

    evidence_page is "appended" when the original was a PDF this module can extend, else "separate_file" and
    sealed_pdf is a standalone certificate PDF (the original is then still hashed in the chain, unchanged).
    """
    doc_hash = sha256_hex(original)
    hashes = [evidence_hash(e) for e in evidence]
    links = chain(doc_hash, hashes)
    lines = evidence_lines(title, doc_hash, evidence, hashes, links[-1], created_at)
    try:
        if not original.startswith(b"%PDF-"):
            raise PdfError("not a PDF")
        sealed, how = append_page(original, lines), "appended"
    except PdfError as e:
        logger.info("evidence page kept as a separate file: %s", e)
        sealed, how = build_pdf(lines, title="Certificate of electronic acceptance"), "separate_file"
    return {"document_sha256": doc_hash, "evidence_hashes": hashes, "chain": links, "seal_hash": links[-1],
            "sealed_pdf": sealed, "sealed_sha256": sha256_hex(sealed), "evidence_page": how, "sealed_at": sealed_at}


def platform_signature(pdf: bytes, seal_hash: str, signer: Optional[PdfSigner]) -> Dict[str, Any]:
    """The platform-certificate signature hook. `not_configured` unless a PdfSigner is injected; never faked."""
    if signer is None:
        return {"status": "not_configured", "signed_pdf": None,
                "reason": "no PdfSigner is configured (pyHanko or an Aadhaar eSign hash-out would be injected; see "
                          "velaris/agentkit/onboarding_esign.py). The document is sealed by hash chain only."}
    try:
        signed = signer.sign_pdf(pdf, seal_hash)
    except Exception as e:     # the signer is third-party code: any failure leaves the hash-chain seal intact
        logger.warning("platform signature failed: %s", e)
        return {"status": "failed", "signed_pdf": None, "reason": f"the signer raised {type(e).__name__}"}
    if not isinstance(signed, bytes) or not signed.startswith(pdf[:5]):
        return {"status": "failed", "signed_pdf": None, "reason": "the signer returned something that is not a PDF"}
    return {"status": "signed", "signed_pdf": signed, "signed_sha256": sha256_hex(signed), "reason": ""}


def verify_seal(original: Optional[bytes], doc_hash: str, evidence: List[Dict[str, Any]], seal_rec: Dict[str, Any],
                sealed_pdf: Optional[bytes], anchored: bool) -> List[Dict[str, Any]]:
    """Recompute everything. A list of {"check", "ok", "detail"}; the document is valid only if every check is ok."""
    checks: List[Dict[str, Any]] = []

    def add(name: str, good: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(good), "detail": detail})

    add("original document present", original is not None)
    add("document hash matches", original is not None and sha256_hex(original) == doc_hash,
        "the stored document no longer hashes to the recorded value" if original is not None and sha256_hex(original) != doc_hash else "")
    hashes = [evidence_hash(e) for e in evidence]
    add("evidence hashes match the seal", hashes == seal_rec.get("evidence_hashes"))
    add("every evidence record names this document", all(e.get("document_sha256") == doc_hash for e in evidence))
    add("consent text matches its version", all(e.get("consent_text_sha256") == sha256_hex(CONSENT_TEXTS.get(e.get("consent_text_version", ""), "").encode())
                                                 and CONSENT_TEXTS.get(e.get("consent_text_version", "")) for e in evidence))
    add("intent statement matches", all(e.get("intent_statement") == intent_statement(e.get("intent_version", ""), e.get("typed_name", ""), doc_hash)
                                        for e in evidence if e.get("intent_version") in INTENT_TEXTS) and
        all(e.get("intent_version") in INTENT_TEXTS for e in evidence))
    links = chain(doc_hash, hashes)
    add("hash chain recomputes", links == seal_rec.get("chain") and links[-1] == seal_rec.get("seal_hash"))
    add("sealed PDF present", sealed_pdf is not None)
    if sealed_pdf is not None:
        add("sealed PDF hash matches", sha256_hex(sealed_pdf) == seal_rec.get("sealed_sha256"))
        try:
            parsed = parse_pdf(sealed_pdf)
            add("sealed PDF structure parses", True, f"{parsed['pages']} pages")
            add("evidence page shows the seal hash", seal_rec.get("seal_hash", "?") in "".join(parsed["text"][-1:]).replace("\n", ""))
        except PdfError as e:
            add("sealed PDF structure parses", False, str(e))
        if seal_rec.get("evidence_page") == "appended" and original is not None:
            add("original bytes are a prefix of the sealed PDF", sealed_pdf.startswith(original))
    add("seal hash anchored in the trace", anchored, "" if anchored else "no matching esign.sealed entry in the trace")
    return checks


_HEX = re.compile(r"^[0-9a-f]{64}$")


def is_hash(v: Any) -> bool:
    return isinstance(v, str) and bool(_HEX.match(v))
