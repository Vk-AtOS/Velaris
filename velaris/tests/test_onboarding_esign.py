"""ESIGN: ceremony, evidence, seal, verification, tampering, expiry, reminders, and that no administrator can sign for a signer."""
import base64
import json
import os
import stat
from pathlib import Path

import pytest

from velaris.tests.onboarding_helpers import HR1, HR2, MGR, ORG, OTHER_ORG_HR, Clock, FakeSender
from velaris.agents.ESIGN.main import Esign
from velaris.agentkit import onboarding_esign as es
from velaris.agentkit.onboarding_pdf import build_pdf, parse_pdf
from velaris.core import vault
from velaris.core.access import acting_as

IP, UA = "203.0.113.9", "Mozilla/5.0 test"
SIGNERS = [{"name": "Asha Raman", "email": "asha@example.in"}, {"name": "Ravi Kumar", "email": "ravi@example.in", "role": "company"}]
PDF = build_pdf([("h1", "Offer"), ("p", "Please sign")])


def setup(signers=None, doc=PDF, **cfg):
    sender, clock = FakeSender(), Clock()
    e = Esign({"sender": sender, "clock": clock, **cfg})
    with acting_as(HR1):
        r = e.create_request("Offer for Asha", base64.b64encode(doc).decode(), signers or SIGNERS, document_ref="ofr-1")
        assert r["status"] == "ok", r
        rid = r["request"]["id"]
        assert e.send_request(rid)["status"] == "ok"
    return e, sender, clock, rid


def ceremony(e, sender, email, name, otp=False):
    tok = sender.token_for(email)
    assert e.open_signing(tok, email, IP, UA)["status"] == "ok"
    if otp:
        assert e.request_otp(tok, email, IP, UA)["status"] == "ok"
        assert e.verify_otp(tok, email, sender.otp_for(email), IP, UA)["status"] == "ok"
    assert e.give_consent(tok, email, IP, UA, "v1")["status"] == "ok"
    return e.sign_document(tok, email, name, IP, UA)


def sign_all(e, sender):
    ceremony(e, sender, "asha@example.in", "Asha Raman")
    return ceremony(e, sender, "ravi@example.in", "ravi  KUMAR")          # name match ignores case and spacing


def requests_now():
    return dict(Esign().store.state.load()["requests"])


def state_text():
    """What the store holds (opened) plus the raw record files (sealed): a secret must be in neither."""
    disk = b"".join(p.read_bytes() for p in (Path(os.environ["VELARIS_DATA"]) / "agents" / "ESIGN" / "records").rglob("*.rec"))
    return json.dumps(requests_now(), default=str) + disk.decode("latin-1")


def edit_state(fn):
    Esign().store.state.update(lambda d: fn(d["requests"]))


def test_full_ceremony_seal_and_verify():
    e, sender, _, rid = setup()
    first = ceremony(e, sender, "asha@example.in", "Asha Raman")
    assert first["request_status"] == "sent" and "seal" not in first
    last = ceremony(e, sender, "ravi@example.in", "Ravi Kumar")
    assert last["request_status"] == "completed" and last["seal"]["status"] == "ok" and last["seal"]["evidence_page"] == "appended"
    assert last["seal"]["platform_signature"]["status"] == "not_configured"
    with acting_as(HR1):
        v = e.verify(rid)
        assert v["valid"] is True, [c for c in v["checks"] if not c["ok"]]
        assert {c["check"] for c in v["checks"]} >= {"document hash matches", "hash chain recomputes", "seal hash anchored in the trace"}
        doc = e.get_sealed_document(rid)
        sealed = base64.b64decode(doc["sealed_pdf_base64"])
        assert sealed.startswith(PDF) and parse_pdf(sealed)["pages"] == 2
        assert "Certificate of electronic acceptance" in parse_pdf(sealed)["text"][-1]
        assert doc["platform_signed_pdf_base64"] is None
        view = e.get_request(rid)["request"]
        assert view["status"] == "sealed" and [s["state"] for s in view["signers"]] == ["signed", "signed"]


def test_evidence_content_and_privacy():
    e, sender, _, rid = setup()
    sign_all(e, sender)
    raw = state_text()
    assert IP not in raw and UA not in raw                         # only keyed hashes are stored
    d = requests_now()[f"{ORG}:{rid}"]
    ev = d["signers"][0]["evidence"]
    assert ev["document_sha256"] == d["document_sha256"] and len(ev["ip_hash"]) == 64 and ev["ip_hash"] != ev["user_agent_hash"]
    assert ev["consent_text_version"] == "v1" and ev["auth_methods"] == ["email_token"] and "I intend to be bound" in ev["intent_statement"]
    assert d["signers"][0]["evidence"]["ip_hash"] == d["signers"][1]["evidence"]["ip_hash"]       # same address, same keyed hash
    for s in d["signers"]:
        assert not any(tok in raw for tok in [sender.token_for(s["email"])])                      # raw tokens are never stored


def test_legal_notice_on_every_output():
    e, sender, clock, rid = setup()
    outs = [e.health_check()]
    outs += [e.open_signing("x" * 30, "a@b.in", IP, UA), e.sign_document("short", "a@b.in", "n", IP, UA)]
    tok = sender.token_for("asha@example.in")
    outs += [e.open_signing(tok, "asha@example.in", IP, UA), e.give_consent(tok, "asha@example.in", IP, UA, "v1")]
    with acting_as(HR1):
        outs += [e.get_request(rid), e.list_requests(), e.verify(rid), e.get_sealed_document(rid), e.process_due(), e.send_reminders(),
                 e.void_request("sig-none", "x")]
    with acting_as(MGR):
        outs += [e.create_request("t", "", [])]
    outs += [e.create_request("t", "", [])]                          # unauthenticated
    health = outs[0]
    assert health["legal_notice"] == es.LEGAL_NOTICE
    for o in outs[1:]:
        assert o["legal_notice"] == es.LEGAL_NOTICE, o
    assert "s.3A" in es.LEGAL_NOTICE and "lawyer" in es.LEGAL_NOTICE and "10A" in es.LEGAL_NOTICE


def test_an_administrator_cannot_sign_for_a_signer():
    e, sender, _, rid = setup()
    seen = []
    with acting_as(HR1):                                           # an HR administrator, creator of the request
        seen += [e.get_request(rid), e.list_requests(), e.send_reminders(), e.process_due()]
        for guess in ("A" * 43, "asha", "", None, 12345, rid):
            r = e.sign_document(guess, "asha@example.in", "Asha Raman", IP, UA)
            assert r["status"] in ("invalid_token", "invalid_input"), r
        r = e.open_signing(rid, "asha@example.in", IP, UA)
        assert r["status"] == "invalid_token"
    real = sender.token_for("asha@example.in")
    blob = json.dumps(seen, default=str) + state_text()
    assert real not in blob and "token_sha256" not in json.dumps(seen)       # no method hands out or stores a token
    assert not [t for t in (sender.token_for("asha@example.in"), sender.token_for("ravi@example.in")) if t in json.dumps(seen)]
    with acting_as(HR1):                                           # even holding the admin role AND the right email, no token = no signature
        assert e.sign_document("B" * 43, "asha@example.in", "Asha Raman", IP, UA)["status"] == "invalid_token"
    view = requests_now()[f"{ORG}:{rid}"]
    assert [s["state"] for s in view["signers"]] == ["sent", "sent"] and view["signed_order"] == []


def test_token_belongs_to_one_signer_and_needs_their_email():
    e, sender, _, rid = setup()
    tok_a = sender.token_for("asha@example.in")
    assert e.open_signing(tok_a, "ravi@example.in", IP, UA)["status"] == "identity_mismatch"
    assert e.open_signing(tok_a, None, IP, UA)["status"] == "identity_mismatch"
    for _ in range(12):
        e.open_signing(tok_a, "ravi@example.in", IP, UA)
    assert e.open_signing(tok_a, "asha@example.in", IP, UA)["status"] == "locked"       # too many wrong attempts
    with acting_as(HR1):
        tok_b = sender.token_for("ravi@example.in")
    assert e.open_signing(tok_b, "ravi@example.in", IP, UA)["status"] == "ok"


def test_a_signer_locked_by_a_leaked_link_is_unlocked_by_time_or_by_a_new_code():
    """KAN-64: the failed counter never reset, so anyone with the link could lock the signer out for good."""
    e, sender, clock, rid = setup()
    tok = sender.token_for("asha@example.in")
    for _ in range(12):
        e.open_signing(tok, "ravi@example.in", IP, UA)
    assert e.open_signing(tok, "asha@example.in", IP, UA)["status"] == "locked"
    clock.advance(minutes=31)
    assert e.open_signing(tok, "asha@example.in", IP, UA)["status"] == "ok"             # the lock decayed
    for _ in range(12):
        e.open_signing(tok, "ravi@example.in", IP, UA)
    assert e.open_signing(tok, "asha@example.in", IP, UA)["status"] == "locked"
    clock.advance(hours=49)                                                                # a reminder issues a new code and clears it
    with acting_as(HR1):
        assert e.send_reminders()["status"] == "ok"
    assert e.open_signing(sender.token_for("asha@example.in"), "asha@example.in", IP, UA)["status"] == "ok"


def test_ceremony_order_and_name_check():
    e, sender, _, rid = setup()
    tok, em = sender.token_for("asha@example.in"), "asha@example.in"
    assert e.give_consent(tok, em, IP, UA, "v1")["status"] == "out_of_order"
    assert e.sign_document(tok, em, "Asha Raman", IP, UA)["status"] == "out_of_order"
    e.open_signing(tok, em, IP, UA)
    assert e.give_consent(tok, em, IP, UA, "v0")["status"] == "invalid_input"
    e.give_consent(tok, em, IP, UA, "v1")
    assert e.sign_document(tok, em, "Someone Else", IP, UA)["status"] == "name_mismatch"
    assert e.sign_document(tok, em, 5, IP, UA)["status"] == "name_mismatch"
    assert e.sign_document(tok, em, "Asha Raman", "", UA)["status"] == "invalid_input"
    assert e.sign_document(tok, em, "Asha Raman", IP, UA)["signer_state"] == "signed"
    assert e.sign_document(tok, em, "Asha Raman", IP, UA)["status"] == "invalid_token"      # a token is good for one signature


def test_otp_flow_and_limits():
    e, sender, clock, rid = setup([{"name": "Asha Raman", "email": "asha@example.in", "otp_required": True, "phone": "+919000000000"}])
    tok, em = sender.token_for("asha@example.in"), "asha@example.in"
    e.open_signing(tok, em, IP, UA)
    assert e.give_consent(tok, em, IP, UA, "v1")["status"] == "otp_required"
    assert e.verify_otp(tok, em, "123456", IP, UA)["status"] == "otp_unavailable"
    assert e.request_otp(tok, em, IP, UA)["delivery"] == "sent"
    code = sender.otp_for("+919000000000")                         # sent to the phone, not the e-mail
    wrong = "000000" if code != "000000" else "111111"
    assert e.verify_otp(tok, em, wrong, IP, UA)["status"] == "otp_wrong"
    assert e.verify_otp(tok, em, code, IP, UA)["status"] == "ok"
    assert e.give_consent(tok, em, IP, UA, "v1")["status"] == "ok"
    out = e.sign_document(tok, em, "Asha Raman", IP, UA)
    assert out["seal"]["status"] == "ok"
    ev = requests_now()[f"{ORG}:{rid}"]["signers"][0]["evidence"]
    assert ev["auth_methods"] == ["email_token", "one_time_code"]
    assert code not in state_text()


def test_otp_expires_locks_and_is_refused_when_not_required():
    e, sender, clock, rid = setup([{"name": "Asha Raman", "email": "asha@example.in", "otp_required": True},
                                   {"name": "Ravi Kumar", "email": "ravi@example.in"}])
    tok, em = sender.token_for("asha@example.in"), "asha@example.in"
    e.open_signing(tok, em, IP, UA)
    e.request_otp(tok, em, IP, UA)
    clock.advance(minutes=11)
    assert e.verify_otp(tok, em, sender.otp_for(em), IP, UA)["status"] == "otp_unavailable"
    e.request_otp(tok, em, IP, UA)
    for _ in range(5):
        e.verify_otp(tok, em, "999999" if sender.otp_for(em) != "999999" else "888888", IP, UA)
    assert e.verify_otp(tok, em, sender.otp_for(em), IP, UA)["status"] == "otp_unavailable"      # five tries used up
    rtok = sender.token_for("ravi@example.in")
    e.open_signing(rtok, "ravi@example.in", IP, UA)
    assert e.request_otp(rtok, "ravi@example.in", IP, UA)["status"] == "invalid_input"


def test_tampering_is_detected_by_verify():
    def tampered(mutate):
        e, sender, _, rid = setup()
        sign_all(e, sender)
        mutate(rid)
        with acting_as(HR1):
            v = e.verify(rid)
        return v["valid"], {c["check"] for c in v["checks"] if not c["ok"]}

    valid, _ = tampered(lambda rid: None)
    assert valid is True

    def evidence_name(rid):
        edit_state(lambda reqs: reqs[f"{ORG}:{rid}"]["signers"][0]["evidence"].__setitem__("name", "Mallory"))

    def evidence_time(rid):
        edit_state(lambda reqs: reqs[f"{ORG}:{rid}"]["signers"][1]["evidence"].__setitem__("signed_at", "2020-01-01T00:00:00Z"))

    def chain(rid):
        edit_state(lambda reqs: reqs[f"{ORG}:{rid}"]["seal"]["chain"].__setitem__(1, "0" * 64))

    def order(rid):
        edit_state(lambda reqs: reqs[f"{ORG}:{rid}"].__setitem__("signed_order", reqs[f"{ORG}:{rid}"]["signed_order"][::-1]))

    def document(rid):
        edit_state(lambda reqs: None)
        for f in (Path(os.environ["VELARIS_DATA"]) / "agents" / "ESIGN" / "documents").iterdir():
            f.write_bytes(f.read_bytes() + b"tampered")

    def sealed_file(rid):
        f = Path(os.environ["VELARIS_DATA"]) / "agents" / "ESIGN" / "sealed" / f"{rid}.pdf"
        raw = f.read_bytes()                                  # sealed at rest: flip a byte of the ciphertext
        f.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))

    def sealed_missing(rid):
        (Path(os.environ["VELARIS_DATA"]) / "agents" / "ESIGN" / "sealed" / f"{rid}.pdf").unlink()

    for mutate in (evidence_name, evidence_time, chain, order, document, sealed_file, sealed_missing):
        valid, failed = tampered(mutate)
        assert valid is False and failed, mutate.__name__


def test_documents_and_sealed_pdfs_are_encrypted_and_bound_to_their_file():
    """KAN-69 SV2-04: contracts and offers were stored in plain text; a sealed file must not open as another one."""
    e, sender, _, rid = setup()
    sign_all(e, sender)
    base = Path(os.environ["VELARIS_DATA"]) / "agents" / "ESIGN"
    docs = list((base / "documents").iterdir())
    pdf = base / "sealed" / f"{rid}.pdf"
    assert all(vault.is_bound(f.read_bytes()) for f in docs) and vault.is_bound(pdf.read_bytes())
    assert b"%PDF" not in pdf.read_bytes()
    docs[0].write_bytes(pdf.read_bytes())                     # a valid sealed file moved over the document
    with acting_as(HR1):
        assert e.verify(rid)["valid"] is False


def test_trace_anchor_missing_is_reported():
    e, sender, _, rid = setup()
    sign_all(e, sender)
    (Path(os.environ["VELARIS_DATA"]) / "trace.jsonl").write_text("")
    with acting_as(HR1):
        v = e.verify(rid)
    assert v["valid"] is False and [c["check"] for c in v["checks"] if not c["ok"]] == ["seal hash anchored in the trace"]


def test_non_pdf_document_gets_a_separate_certificate():
    e, sender, _, rid = setup(doc=b"plain text contract")
    sign_all(e, sender)
    with acting_as(HR1):
        v = e.verify(rid)
        assert v["valid"] is True
        sealed = base64.b64decode(e.get_sealed_document(rid)["sealed_pdf_base64"])
    assert parse_pdf(sealed)["title"] == "Certificate of electronic acceptance"
    assert requests_now()[f"{ORG}:{rid}"]["seal"]["evidence_page"] == "separate_file"


class GoodSigner:
    def sign_pdf(self, pdf, digest):
        return pdf + b"\n%signed:" + digest.encode()


class BrokenSigner:
    def sign_pdf(self, pdf, digest):
        raise RuntimeError("hsm offline")


class JunkSigner:
    def sign_pdf(self, pdf, digest):
        return b"junk"


@pytest.mark.parametrize("signer,status", [(GoodSigner(), "signed"), (BrokenSigner(), "failed"), (JunkSigner(), "failed"), (None, "not_configured")])
def test_platform_signature_hook(signer, status):
    e, sender, _, rid = setup(pdf_signer=signer)
    out = sign_all(e, sender)
    assert out["seal"]["status"] == "ok" and out["seal"]["platform_signature"]["status"] == status
    with acting_as(HR1):
        assert e.verify(rid)["valid"] is True                      # the hash-chain seal stands whatever the hook did
        signed = e.get_sealed_document(rid)["platform_signed_pdf_base64"]
    assert (signed is not None) == (status == "signed")


def test_decline_void_and_expiry_close_the_request_and_kill_tokens():
    e, sender, clock, rid = setup()
    tok = sender.token_for("asha@example.in")
    assert e.decline_signing(tok, "asha@example.in", "not interested", IP, UA)["request_status"] == "declined"
    other = sender.token_for("ravi@example.in")
    assert e.open_signing(other, "ravi@example.in", IP, UA)["status"] == "invalid_token"
    with acting_as(HR1):
        assert e.get_request(rid)["request"]["status"] == "declined" and e.void_request(rid, "x")["status"] == "conflict"
    e2, s2, c2, rid2 = setup()
    t2 = s2.token_for("asha@example.in")
    with acting_as(HR2):                                           # another HR administrator may void it
        assert e2.void_request(rid2, "wrong document")["status"] == "ok"
    assert e2.open_signing(t2, "asha@example.in", IP, UA)["status"] == "invalid_token"
    e3, s3, c3, rid3 = setup()
    t3 = s3.token_for("asha@example.in")
    c3.advance(days=15)
    assert e3.open_signing(t3, "asha@example.in", IP, UA)["status"] == "not_open"
    with acting_as(HR1):
        assert e3.process_due()["expired"] == [rid3]
        assert e3.get_request(rid3)["request"]["status"] == "expired"
    assert e3.open_signing(t3, "asha@example.in", IP, UA)["status"] == "invalid_token"


def test_sealed_request_cannot_be_voided():
    e, sender, _, rid = setup()
    sign_all(e, sender)
    with acting_as(HR1):
        assert e.void_request(rid, "oops")["status"] == "conflict"


def test_reminders_rotate_the_token():
    e, sender, clock, rid = setup()
    old = sender.token_for("asha@example.in")
    with acting_as(HR1):
        assert e.send_reminders()["reminders"] == []              # too soon
    clock.advance(hours=49)
    with acting_as(HR1):
        r = e.send_reminders()
    assert {x["signer"] for x in r["reminders"]} == {"s1", "s2"} and all(x["delivery"] == "sent" for x in r["reminders"])
    new = sender.token_for("asha@example.in")
    assert new != old
    assert e.open_signing(old, "asha@example.in", IP, UA)["status"] == "invalid_token"
    assert e.open_signing(new, "asha@example.in", IP, UA)["status"] == "ok"
    for _ in range(5):
        clock.advance(hours=49)
        with acting_as(HR1):
            e.send_reminders()
    assert len([m for m in sender.messages if m["subject"].startswith("Reminder")]) <= 6     # at most 3 per signer


def test_without_a_sender_messages_are_queued_in_an_owner_only_outbox():
    e = Esign({"clock": Clock()})
    with acting_as(HR1):
        rid = e.create_request("Doc", base64.b64encode(PDF).decode(), SIGNERS)["request"]["id"]
        r = e.send_request(rid)
    assert r["status"] == "ok" and set(r["delivery"].values()) == {"queued_in_outbox"}
    assert "signing code" not in json.dumps(r) and "token_sha256" not in json.dumps(r)
    box = Path(os.environ["VELARIS_DATA"]) / "agents" / "ESIGN" / "outbox" / "outbox.jsonl"
    assert stat.S_IMODE(box.stat().st_mode) == 0o600 and stat.S_IMODE(box.parent.stat().st_mode) == 0o700
    assert "signing code" not in box.read_text() and "@" not in box.read_text()                 # sealed: no code, no address in the file
    from velaris.agentkit.state import read_lines
    from velaris.agents.ESIGN.main import OUTBOX_SEAL
    lines = read_lines(box, encrypted=OUTBOX_SEAL)
    assert len(lines) == 2 and "signing code" in lines[0]["body"]
    token = lines[0]["body"].split("signing code", 1)[1].split(": ", 1)[1].split()[0]
    assert e.open_signing(token, lines[0]["to"], IP, UA)["status"] == "ok"             # the operator's relay can deliver it


def test_a_non_ascii_email_is_a_mismatch_not_a_server_error():
    e, sender, _, rid = setup()
    token = sender.token_for(SIGNERS[0]["email"])
    r = e.open_signing(token, "joséé@exämple.com", IP, UA)
    assert r["status"] == "identity_mismatch"


def test_create_request_input_and_access():
    e = Esign({"clock": Clock()})
    doc = base64.b64encode(PDF).decode()
    with acting_as(HR1):
        for args in [("", doc, SIGNERS), ("t", "!!!", SIGNERS), ("t", "", SIGNERS), ("t", doc, []), ("t", doc, [{"name": "A", "email": "bad"}]),
                     ("t", doc, [{"name": "A", "email": "a@b.in"}, {"name": "B", "email": "A@B.in"}]), ("t", doc, "nope"),
                     ("t", doc, [{"name": "", "email": "a@b.in"}]), ("t", doc, [{"name": "A", "email": "a@b.in"}] * 11)]:
            assert e.create_request(*args)["status"] == "invalid_input", args
        assert e.create_request("t", doc, SIGNERS, valid_days=0)["status"] == "invalid_input"
        assert e.send_request("sig-none")["status"] == "not_found"
        rid = e.create_request("t", doc, SIGNERS)["request"]["id"]
        assert e.send_request(rid)["status"] == "ok" and e.send_request(rid)["status"] == "conflict"
    with acting_as(MGR):
        assert e.create_request("t", doc, SIGNERS)["status"] == "denied"
        assert e.get_request(rid)["status"] == "not_found"          # not the drafter, not HR
        assert e.list_requests()["requests"] == []
    assert e.send_request(rid)["status"] == "unauthenticated"


def test_organisation_scoping(monkeypatch):
    e, sender, _, rid = setup()
    with acting_as(OTHER_ORG_HR):
        assert e.get_request(rid)["status"] == "not_found" and e.verify(rid)["status"] == "not_found"
        assert e.list_requests()["requests"] == [] and e.void_request(rid, "x")["status"] == "not_found"
        assert e.get_sealed_document(rid)["status"] == "not_found"
    assert requests_now()[f"{ORG}:{rid}"]["org"] == ORG
    monkeypatch.setenv("VELARIS_ORG", "globex")                    # a deployment of another organisation: the token is not honoured
    assert e.open_signing(sender.token_for("asha@example.in"), "asha@example.in", IP, UA)["status"] == "invalid_token"


def test_verify_refuses_unsealed():
    e, sender, _, rid = setup()
    with acting_as(HR1):
        assert e.verify(rid)["status"] == "not_sealed"


def test_verify_applies_the_same_visibility_as_get_request():
    e, sender, _, rid = setup()
    sign_all(e, sender)
    with acting_as(MGR):                                            # same org, neither drafter nor HR
        assert e.get_request(rid)["status"] == "not_found"
        v = e.verify(rid)
        assert v["status"] == "not_found" and "signers" not in v and "platform_signature" not in v
        assert e.get_sealed_document(rid)["status"] == "not_found" and e.void_request(rid, "x")["status"] == "denied"
        assert e.list_requests()["requests"] == []
    with acting_as(HR2):
        assert e.verify(rid)["valid"] is True


def test_real_esign_reader_gives_status_and_document_ref_only():
    from velaris.agentkit.onboarding_adapters import EsignReader
    e, sender, _, rid = setup()
    view = EsignReader({"clock": Clock()})
    assert view.request_info(rid, ORG) is None                                   # no caller: nothing
    with acting_as(HR1):
        info = view.request_info(rid, ORG)
        assert info["status"] == "sent" and info["document_ref"] == "ofr-1" and info["signer_email_sha256"] == []     # nobody has signed yet
        assert len(info["document_sha256"]) == 64 and "@" not in str(info)                                           # hashes only, no addresses
        assert view.request_info(rid, "globex") is None and view.request_info("sig-none", ORG) is None
    with acting_as(OTHER_ORG_HR):                                                # another organisation's caller cannot look in
        assert view.request_info(rid, ORG) is None
