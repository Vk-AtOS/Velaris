"""Shared helpers for the test_hiring_* files (not a test module)."""
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Tuple

from velaris.agentkit import hiring_common as hc
from velaris.core.access import Caller, acting_as
from velaris.intel.paths import data_dir

ORG = "acme"
FORBIDDEN_KEYS = ("likelihood", "cheat", "authentic", "recommend", "verdict", "rank", "ai_", "hire_score", "reject_score", "fit_score", "probability")


def who(*roles: str, id: str = "", org: str = ORG) -> Caller:
    return Caller(id=id or (roles[0] if roles else "nobody") + "-1", org=org, roles=frozenset(roles))


@contextmanager
def as_(caller):
    with acting_as(caller):
        yield caller


def clean_keys(result: Any, extra: Iterable[str] = ()) -> None:
    bad = hc.check_keys_clean(result, FORBIDDEN_KEYS + tuple(extra))
    assert not bad, f"forbidden keys in result: {bad}"


def trace_text() -> str:
    p = data_dir() / "trace.jsonl"
    return p.read_text() if p.exists() else ""


def bootstrap(ats, resumes=None) -> Tuple[str, Dict[str, Any]]:
    """An open requisition (python must, docker nice). Returns (requisition_id, callers)."""
    rec, mgr, adm = who("recruiter"), who("hiring_manager"), who("hr_admin")
    with as_(rec):
        r = ats.create_requisition(title="Backend Engineer", location={"city": "Chennai"}, openings=2,
                                   requirements={"must": [{"skill": "python", "min_years": 2}, "sql"], "nice": ["docker"], "min_total_years": 3},
                                   description="Build services for IT clients.")
        assert r["status"] == "ok", r
    rid = r["requisition"]["id"]
    with as_(mgr):
        assert ats.approve_requisition(requisition_id=rid)["status"] == "ok"
    with as_(rec):
        assert ats.open_requisition(requisition_id=rid)["status"] == "ok"
    return rid, {"rec": rec, "mgr": mgr, "adm": adm}


CONSENT = {"purpose": "recruitment for Backend Engineer", "notice_version": "v1", "retention_until": None, "channel": "web_form"}


def consent(days: int = 90, **kw) -> Dict[str, Any]:
    return {**CONSENT, "retention_until": hc.iso(hc.now() + days * hc.DAY)[:10], **kw}


def advance(monkeypatch, seconds: float) -> None:
    """Move the wall clock forward for everything (hiring modules read time.time through hiring_common.now)."""
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + seconds)


def tiny_pdf(text: str) -> bytes:
    """A one-page PDF that pypdf can read (hand-built, no library needed to write it)."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"]
    stream = ("BT /F1 12 Tf 72 720 Td (%s) Tj ET" % text).encode()
    objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
