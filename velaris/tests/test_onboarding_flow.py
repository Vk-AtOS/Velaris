"""ONBOARDING_FLOW: tasks, dependencies, blocked reporting, minimal-data capture, encryption at rest, masking, access, org scoping."""
import base64
import json
import os
from pathlib import Path

from velaris.tests.onboarding_helpers import HR1, HR2, MGR, ORG, OTHER_ORG_HR, PAYROLL, Clock, FakeOffers, FakePolicyAcks, person
from velaris.agents.ONBOARDING_FLOW.main import OnboardingFlow
import pytest
from velaris.core.access import AccessDenied, Caller, acting_as
from velaris.intel import trace

EMP = person("E7")
IT = Caller("it1", ORG, frozenset())
PAN, AADHAAR, ACCOUNT = "ABCDE1234F", "234123412346", "123456789012"


def make(**cfg):
    clock = Clock()
    return OnboardingFlow({"clock": clock, **cfg}), clock


def start(o, **kw):
    args = dict(subject_id="E7", name="Asha Raman", email="asha@example.in", join_date="2026-12-01", role_group="engineering",
                location="chennai", manager_id="mgr1", it_owner_id="it1")
    args.update(kw)
    with acting_as(HR1):
        r = o.start_onboarding(**args)
    assert r["status"] == "ok", r
    return r["case"]["id"]


def unblock(o, cid):
    with acting_as(HR1):
        assert o.complete_task(cid, "confirm_offer_accepted")["status"] == "ok"


def data_text():
    return "".join(p.read_text(errors="ignore") for p in Path(os.environ["VELARIS_DATA"]).rglob("*")
                   if p.is_file() and p.name != "onboarding_field.key" and not p.name.endswith(".key"))


def test_start_builds_tasks_with_owners_due_dates_and_org_stamp():
    o, _ = make()
    with acting_as(HR1):
        r = o.start_onboarding("E7", "Asha Raman", "asha@example.in", "2026-12-01", "engineering", "chennai", "mgr1", it_owner_id="it1")
    cid = r["case"]["id"]
    assert r["case"]["org"] == ORG and r["status_report"]["completion_percent"] == 0.0
    tasks = {t["key"]: t for t in r["status_report"]["tasks"]}
    assert tasks["source_control_access"]["owner"] == "it" and tasks["source_control_access"]["assignee"] == "it1"
    assert tasks["office_access_card"]["due_date"] == "2026-12-01" and tasks["confirm_offer_accepted"]["due_date"] == "2026-11-24"
    assert tasks["assign_buddy"]["assignee"] == "mgr1" and tasks["collect_pan"]["assignee"] == "E7"
    assert tasks["collect_pan"]["state"] == "blocked" and tasks["confirm_offer_accepted"]["state"] == "ready"
    stored = json.loads((Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "state.json").read_text())
    assert stored["records"]["cases"][f"{ORG}:{cid}"]["org"] == ORG


def test_start_denied_invalid_and_duplicate():
    o, _ = make()
    assert o.start_onboarding("E7", "A", "a@b.in", "2026-12-01", "x", "y", "m")["status"] == "unauthenticated"
    with acting_as(MGR):
        assert o.start_onboarding("E7", "A", "a@b.in", "2026-12-01", "x", "y", "m")["status"] == "denied"
    with acting_as(HR1):
        for kw in (dict(join_date="2026-13-01"), dict(subject_id=""), dict(name=""), dict(manager_id=""), dict(role_group="")):
            args = dict(subject_id="E7", name="A", email="a@b.in", join_date="2026-12-01", role_group="x", location="y", manager_id="m")
            args.update(kw)
            assert o.start_onboarding(**args)["status"] == "invalid_input", kw
    start(o)
    with acting_as(HR1):
        assert o.start_onboarding("E7", "A", "a@b.in", "2026-12-01", "x", "y", "m")["status"] == "conflict"


def test_offer_must_be_accepted_when_checked():
    o, _ = make(offers=FakeOffers("sent"))
    with acting_as(HR1):
        assert o.start_onboarding("E7", "A", "a@b.in", "2026-12-01", "x", "y", "m", offer_id="ofr-1")["status"] == "conflict"
    o2, _ = make(offers=FakeOffers("accepted"))
    with acting_as(HR1):
        r = o2.start_onboarding("E7", "A", "a@b.in", "2026-12-01", "x", "y", "m", offer_id="ofr-1")
    assert r["status"] == "ok" and r["case"]["offer_check"] == "accepted"


def test_dependencies_blocked_report_and_completion_percent():
    o, clock = make()
    cid = start(o)
    with acting_as(HR1):
        st = o.case_status(cid)
        blocked = {b["task"]: b for b in st["blocked"]}
        assert blocked["provision_accounts"]["waiting_for"] == ["confirm_offer_accepted"] and st["completion_percent"] == 0.0
    with acting_as(IT):
        r = o.complete_task(cid, "provision_accounts")
        assert r["status"] == "blocked" and r["waiting_for"] == ["confirm_offer_accepted"]
    unblock(o, cid)
    with acting_as(IT):
        assert o.complete_task(cid, "provision_accounts")["status"] == "ok"
        assert o.complete_task(cid, "provision_accounts")["status"] == "conflict"           # already done
        assert o.complete_task(cid, "assign_buddy")["status"] == "denied"                    # not theirs
    with acting_as(HR1):
        st = o.case_status(cid)
        assert 0 < st["completion_percent"] < 100 and st["required_done"] == 2
    clock.advance(days=25)                                                                    # 2026-12-08: past most due dates
    with acting_as(HR1):
        assert "collect_pan" in o.case_status(cid)["overdue"]


ACKS = FakePolicyAcks({"code_of_conduct": 2, "information_security": 1}, [("E7", "code_of_conduct", 2, "h-good")])


def test_complete_task_rules():
    o, _ = make(policy_acks=ACKS)
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        assert o.complete_task(cid, "collect_pan")["status"] == "conflict"                   # completes on submission
        assert o.complete_task(cid, "tax_declaration")["status"] == "conflict"
    with acting_as(IT):
        o.complete_task(cid, "provision_accounts")
    with acting_as(EMP):
        assert o.complete_task(cid, "ack_code_of_conduct")["status"] == "invalid_input"      # needs the POLICY_ACKS evidence
        assert o.complete_task(cid, "ack_code_of_conduct", evidence_ref="h-good")["status"] == "ok"
        assert o.complete_task(cid, "nope")["status"] == "not_found"
        assert o.waive_task(cid, "assign_buddy", "x")["status"] == "denied"
    with acting_as(HR1):
        assert o.waive_task(cid, "collect_aadhaar", "")["status"] == "invalid_input"
        assert o.waive_task(cid, "collect_aadhaar", "no purpose applies")["status"] == "ok"
        view = {t["key"]: t["state"] for t in o.case_status(cid)["tasks"]}
        assert view["collect_aadhaar"] == "waived"


def _ack_case(o, sid="E7"):
    cid = start(o, subject_id=sid)
    unblock(o, cid)
    with acting_as(IT):
        assert o.complete_task(cid, "provision_accounts")["status"] == "ok"
    return cid


def test_policy_ack_task_needs_a_real_current_acknowledgement_by_the_subject():
    acks = FakePolicyAcks({"code_of_conduct": 2, "information_security": 1},
                          [("E7", "code_of_conduct", 1, "h-old"), ("E9", "code_of_conduct", 2, "h-other"),
                           ("E7", "information_security", 1, "h-sec")])
    o, _ = make(policy_acks=acks)
    cid = _ack_case(o)
    with acting_as(EMP):
        assert o.complete_task(cid, "ack_code_of_conduct", evidence_ref="made-up")["status"] == "not_acknowledged"   # only an old version
        assert o.complete_task(cid, "ack_code_of_conduct", evidence_ref="h-old")["status"] == "not_acknowledged"
        assert o.complete_task(cid, "ack_code_of_conduct", evidence_ref="h-other")["status"] == "not_acknowledged"   # someone else's ack
        assert o.complete_task(cid, "ack_infosec_policy", evidence_ref="made-up")["status"] == "evidence_mismatch"
        assert o.complete_task(cid, "ack_infosec_policy", evidence_ref="h-code")["status"] == "evidence_mismatch"
        assert o.complete_task(cid, "ack_infosec_policy")["status"] == "invalid_input"
    with acting_as(HR1):
        assert o.complete_task(cid, "ack_infosec_policy", evidence_ref="made-up")["status"] == "evidence_mismatch"   # HR is no exception
        assert o.complete_task(cid, "ack_infosec_policy", evidence_ref="h-sec")["status"] == "ok"
        t = {x["key"]: x for x in o.case_status(cid)["tasks"]}
    assert t["ack_infosec_policy"]["state"] == "done" and t["ack_code_of_conduct"]["state"] == "ready"


def test_policy_ack_task_fails_closed_without_a_checker_or_a_policy():
    o, _ = make()                                                                     # no policy_acks configured
    cid = _ack_case(o)
    with acting_as(EMP):
        assert o.complete_task(cid, "ack_code_of_conduct", evidence_ref="h-good")["status"] == "not_configured"
    class Broken:
        def ack_evidence(self, *a):
            raise OSError("store down")
    o2, _ = make(policy_acks=Broken())
    cid2 = _ack_case(o2, "E8")
    with acting_as(person("E8")):
        assert o2.complete_task(cid2, "ack_code_of_conduct", evidence_ref="h-good")["status"] == "not_configured"
    o3, _ = make(policy_acks=FakePolicyAcks({}, []))                                  # policy never published
    cid3 = _ack_case(o3, "E9")
    with acting_as(person("E9")):
        assert o3.complete_task(cid3, "ack_code_of_conduct", evidence_ref="h-good")["status"] == "no_current_policy"


def test_plain_tasks_take_no_unverifiable_evidence_reference():
    o, _ = make(policy_acks=ACKS)
    cid = start(o)
    with acting_as(HR1):
        assert o.complete_task(cid, "confirm_offer_accepted", evidence_ref="trust-me")["status"] == "invalid_input"
        assert o.complete_task(cid, "confirm_offer_accepted")["status"] == "ok"


def test_real_policy_acks_reader_resolves_through_the_public_api():
    from velaris.agentkit.onboarding_adapters import PolicyAcksReader
    from velaris.agents.POLICY_ACKS.main import PolicyAcks
    clock = Clock()
    pa = PolicyAcks({"clock": clock})
    with acting_as(HR1):
        assert pa.publish_policy("code_of_conduct", "CoC", "text v1", "2026-11-01")["status"] == "ok"
    view = PolicyAcksReader({"clock": clock})
    assert view.ack_evidence(ORG, "E7", "code_of_conduct") is None               # no caller: nothing
    with acting_as(HR1):
        assert view.ack_evidence(ORG, "E7", "code_of_conduct") == {"current_version": 1, "acks": []}
        assert view.ack_evidence(ORG, "E7", "nope")["current_version"] is None
        assert view.ack_evidence("globex", "E7", "code_of_conduct") is None      # never another organisation's data


def test_case_completes_when_every_required_task_is_done():
    o, _ = make()
    cid = start(o, role_group="other", location="other", it_owner_id="it1")
    with acting_as(HR1):
        case = o.case_status(cid)
    required = [t for t in case["tasks"] if t["required"]]
    assert required
    with acting_as(HR1):
        for _ in range(10):
            for t in o.case_status(cid)["tasks"]:
                if t["required"] and t["state"] in ("ready", "overdue"):
                    o.waive_task(cid, t["key"], "test")
        st = o.case_status(cid)
    assert st["complete"] and st["completion_percent"] == 100.0 and st["case"]["status"] == "complete"
    with acting_as(HR1):
        assert o.complete_task(cid, "orientation")["status"] == "conflict"


def test_nothing_is_collected_before_the_offer_is_confirmed():
    o, _ = make()
    cid = start(o)
    with acting_as(EMP):
        for kind, val, kw in (("pan", PAN, {}), ("aadhaar", AADHAAR, {"purpose": "UAN seeding"}), ("bank_account", ACCOUNT, {"ifsc": "HDFC0001234"})):
            r = o.submit_identifier(cid, kind, val, **kw)
            assert r["status"] == "blocked", (kind, r)
        assert o.submit_form(cid, "emergency_contact", {"name": "R", "relation": "father", "phone": "9"})["status"] == "ok"      # not behind the offer check
        assert o.collect_document(cid, "identity_proof", "id.png", base64.b64encode(b"x").decode())["status"] == "blocked"
    assert PAN not in data_text()


def test_identifiers_are_sealed_at_rest_masked_everywhere_and_never_in_the_trace():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        r = o.submit_identifier(cid, "pan", "abcde1234f")
        assert r["masked"] == "******234F" and r["verified"] is False and r["format_valid"] is True
        b = o.submit_identifier(cid, "bank_account", "1234 5678 9012", ifsc="hdfc0001234")
        assert b["masked"] == "********9012"
        a = o.submit_identifier(cid, "aadhaar", AADHAAR, purpose="UAN seeding")
        assert a["masked"] == "XXXX XXXX 2346"
    text = data_text() + (Path(os.environ["VELARIS_DATA"]) / "trace.jsonl").read_text()
    for secret in (PAN, "ABCDE1234F", ACCOUNT, AADHAAR, "HDFC0001234", "2341 2341 2346"):
        assert secret not in text, secret
    state = json.loads((Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "state.json").read_text())["records"]["cases"][f"{ORG}:{cid}"]
    assert set(state["identifiers"]["aadhaar"]) >= {"last4", "digest"} and "sealed" not in state["identifiers"]["aadhaar"]
    assert state["identifiers"]["aadhaar"]["last4"] == "2346" and state["identifiers"]["pan"]["sealed"].startswith("v1.")
    # masked in every ordinary read, for everyone who may see the case
    for who in (HR1, EMP, MGR):
        with acting_as(who):
            blob = json.dumps([o.case_status(cid), o.get_identifiers(cid), o.list_cases()])
            assert PAN not in blob and ACCOUNT not in blob and AADHAAR not in blob and "234F" in blob
    assert trace.verify()["ok"]


def test_reveal_goes_through_authorize_read_by_category():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        o.submit_identifier(cid, "pan", PAN)
        o.submit_identifier(cid, "bank_account", ACCOUNT, ifsc="HDFC0001234")
        o.submit_identifier(cid, "aadhaar", AADHAAR, purpose="UAN")
        own = o.get_identifiers(cid, reveal=True)["identifiers"]
        assert own["pan"]["value"] == PAN and own["bank_account"]["value"] == ACCOUNT and own["bank_account"]["ifsc"] == "HDFC0001234"
        assert "value" not in own["aadhaar"] and "never stored" in own["aadhaar"]["note"]
    with acting_as(HR1):                                           # identity yes, bank no (only payroll may read bank)
        hr = o.get_identifiers(cid, reveal=True)["identifiers"]
        assert hr["pan"]["value"] == PAN and hr["bank_account"]["value"] is None and "denied" in hr["bank_account"]
    with acting_as(PAYROLL):                                       # payroll admin is not a participant: cannot even see the case
        assert o.get_identifiers(cid, reveal=True)["status"] == "not_found"
    with acting_as(MGR):                                           # a manager sees the case but never clear identifiers
        mg = o.get_identifiers(cid, reveal=True)["identifiers"]
        assert mg["pan"]["value"] is None and mg["pan"]["denied"] and mg["bank_account"]["value"] is None
    with acting_as(person("E8")):
        assert o.get_identifiers(cid, reveal=True)["status"] == "not_found"
    reads = [e for e in trace.entries() if e["action"].startswith("sensitive_read")]
    assert {e["action"] for e in reads} == {"sensitive_read.granted", "sensitive_read.denied"}


def test_payroll_admin_with_case_access_reads_bank_but_not_pan():
    o, _ = make()
    cid = start(o, it_owner_id="pay1")                            # makes pay1 an assignee, so they may see the case
    unblock(o, cid)
    with acting_as(EMP):
        o.submit_identifier(cid, "pan", PAN)
        o.submit_identifier(cid, "bank_account", ACCOUNT, ifsc="HDFC0001234")
    with acting_as(PAYROLL):
        ids = o.get_identifiers(cid, reveal=True)["identifiers"]
    assert ids["bank_account"]["value"] == ACCOUNT and ids["pan"]["value"] is None


def test_aadhaar_needs_purpose_valid_number_and_can_only_be_compared():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        assert o.submit_identifier(cid, "aadhaar", AADHAAR)["status"] == "invalid_input"                       # purpose required
        assert o.submit_identifier(cid, "aadhaar", "234123412345", purpose="x")["status"] == "invalid_input"    # bad check digit
        assert o.check_aadhaar(cid, AADHAAR)["status"] == "not_found"
        assert o.submit_identifier(cid, "aadhaar", AADHAAR, purpose="UAN seeding")["status"] == "ok"
        assert o.check_aadhaar(cid, AADHAAR)["matches"] is True
        assert o.check_aadhaar(cid, "2341 2341 2346")["matches"] is True
        assert o.check_aadhaar(cid, "234123412345")["status"] == "invalid_input"
    with acting_as(MGR):
        assert o.check_aadhaar(cid, AADHAAR)["status"] == "denied"


def _aadhaar_case(o):
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        assert o.submit_identifier(cid, "aadhaar", AADHAAR, purpose="UAN seeding")["status"] == "ok"
    return cid


def test_check_aadhaar_is_rate_limited_per_case_and_locks_out():
    o, clock = make()
    cid = _aadhaar_case(o)
    with acting_as(EMP):
        r = [o.check_aadhaar(cid, AADHAAR) for _ in range(3)]
        assert [x["status"] for x in r] == ["ok"] * 3 and r[-1]["attempts_left_today"] == 0
        assert o.check_aadhaar(cid, AADHAAR)["status"] == "locked"      # a correct number is locked out too
    with acting_as(HR1):
        assert o.check_aadhaar(cid, AADHAAR)["status"] == "locked"      # the limit is per case, so HR is locked out as well
    clock.advance(days=1)
    with acting_as(EMP):
        assert o.check_aadhaar(cid, AADHAAR)["matches"] is True         # the lockout ends with the day
    acts = [e["action"] for e in trace.entries() if e["action"].startswith("aadhaar.")]
    assert acts.count("aadhaar.check_attempt") == 4 and acts.count("aadhaar.check_locked") == 2
    assert AADHAAR not in json.dumps(list(trace.entries()))


def test_check_aadhaar_limit_is_per_caller_across_cases_and_persisted():
    o, _ = make()
    cids = []
    for sid in ("E1", "E2"):
        cid = start(o, subject_id=sid)
        unblock(o, cid)
        with acting_as(person(sid)):
            o.submit_identifier(cid, "aadhaar", AADHAAR, purpose="x")
        cids.append(cid)
    with acting_as(HR1):
        for i in range(5):
            assert o.check_aadhaar(cids[i % 2], AADHAAR)["status"] == "ok"
        assert o.check_aadhaar(cids[0], AADHAAR)["status"] == "locked"   # 5 per caller per day, whichever case
    o2, _ = make()                                                      # a new process: the counters are on disk
    with acting_as(HR1):
        assert o2.check_aadhaar(cids[1], AADHAAR)["status"] == "locked"


def test_check_aadhaar_needs_identity_access_and_never_leaks_a_partial_match():
    from velaris.agentkit import onboarding_crypto as crypto
    o, _ = make()
    cid = _aadhaar_case(o)
    with acting_as(PAYROLL):
        assert o.check_aadhaar(cid, AADHAAR)["status"] == "not_found"
    stored = json.loads((Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "state.json").read_text())
    rec = stored["records"]["cases"][f"{ORG}:{cid}"]["identifiers"]["aadhaar"]
    same_last4 = "999999992346"
    assert crypto.aadhaar_digest(same_last4)["last4"] == rec["last4"]
    assert crypto.aadhaar_matches(same_last4, rec) is False and crypto.aadhaar_matches(AADHAAR, rec) is True
    with acting_as(EMP):
        r = o.check_aadhaar(cid, "234123412346")
    assert set(r) == {"status", "matches", "attempts_left_today"}


def test_check_aadhaar_refused_when_identity_access_is_denied_and_does_not_count(monkeypatch):
    import velaris.agents.ONBOARDING_FLOW.main as m
    from velaris.core.access import AccessDenied
    o, _ = make()
    cid = _aadhaar_case(o)

    def deny(*a, **k):
        raise AccessDenied("no identity access")
    with monkeypatch.context() as mp:
        mp.setattr(m, "authorize_read", deny)
        with acting_as(EMP):
            assert [o.check_aadhaar(cid, AADHAAR)["status"] for _ in range(6)] == ["denied"] * 6
    with acting_as(EMP):
        assert o.check_aadhaar(cid, AADHAAR)["attempts_left_today"] == 2


def test_identifier_input_and_access_rules():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        for kind, val, kw in (("pan", "bad", {}), ("pan", 5, {}), ("bank_account", "123", {"ifsc": "HDFC0001234"}), ("bank_account", ACCOUNT, {"ifsc": "bad"}),
                              ("bank_account", ACCOUNT, {}), ("passport", "x", {}), ("pan", PAN, {"purpose": "x" * 500})):
            assert o.submit_identifier(cid, kind, val, **kw)["status"] == "invalid_input", (kind, val)
    with acting_as(MGR):
        assert o.submit_identifier(cid, "pan", PAN)["status"] == "denied"                # a manager cannot submit for the joiner
    with acting_as(person("E8")):
        assert o.submit_identifier(cid, "pan", PAN)["status"] == "not_found"
    assert o.submit_identifier(cid, "pan", PAN)["status"] == "unauthenticated"
    with acting_as(HR1):                                           # HR may enter it on the joiner's behalf
        assert o.submit_identifier(cid, "pan", PAN)["status"] == "ok"
        assert o.submit_identifier(cid, "pan", "FGHIJ5678K")["status"] == "ok"          # a correction while the case is open


def test_tampered_sealed_identifier_fails_closed():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        o.submit_identifier(cid, "pan", PAN)
    p = Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "state.json"
    d = json.loads(p.read_text())
    d["records"]["cases"][f"{ORG}:{cid}"]["identifiers"]["pan"]["sealed"] = d["records"]["cases"][f"{ORG}:{cid}"]["identifiers"]["pan"]["sealed"][:-4] + "AAAA"
    p.write_text(json.dumps(d))
    with acting_as(EMP):
        r = o.get_identifiers(cid, reveal=True)["identifiers"]["pan"]
    assert r["value"] is None and "integrity" in r["denied"]


def test_forms_and_nominations():
    o, _ = make()
    cid = start(o)
    with acting_as(EMP):
        assert o.submit_form(cid, "tax_declaration", {"regime": "weird"})["status"] == "invalid_input"
        assert o.submit_form(cid, "bogus", {})["status"] == "invalid_input"
        bad = o.submit_form(cid, "pf_nomination", {"nominees": [{"name": "A", "relation": "wife", "share_percent": 50}]})
        assert bad["status"] == "invalid_input" and "add up to 100" in bad["problems"][0]
        good = o.submit_form(cid, "pf_nomination", {"nominees": [{"name": "A", "relation": "wife", "share_percent": 100}]})
        assert good["status"] == "ok" and good["captured_not_filed"] is True
        assert o.submit_form(cid, "tax_declaration", {"regime": "new"})["status"] == "ok"
        assert o.get_form(cid, "pf_nomination")["fields"]["nominees"][0]["name"] == "A"
        assert "tax_declaration" in o.case_status(cid)["case"]["forms_submitted"]
    with acting_as(MGR):
        assert o.get_form(cid, "pf_nomination")["status"] == "denied"
        assert "nominees" not in json.dumps(o.case_status(cid))


def test_documents_are_sealed_hashed_and_dated():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    content = b"%PDF fake identity scan with PLAINTEXT-MARKER"
    with acting_as(EMP):
        r = o.collect_document(cid, "identity_proof", "id.pdf", base64.b64encode(content).decode())
        assert r["status"] == "ok" and len(r["document"]["sha256"]) == 64 and r["document"]["delete_after"] == "2027-12-01"
        did = r["document"]["id"]
        assert o.collect_document(cid, "selfie", "x", base64.b64encode(b"x").decode())["status"] == "invalid_input"
        assert o.collect_document(cid, "other", "x", "!!!")["status"] == "invalid_input"
        assert o.collect_document(cid, "other", "x", "")["status"] == "invalid_input"
        got = o.get_document(cid, did)
        assert base64.b64decode(got["content_base64"]) == content
    assert "PLAINTEXT-MARKER" not in data_text()
    with acting_as(MGR):
        assert o.get_document(cid, did)["status"] == "denied"
    f = Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "docs" / f"{did}.sealed"
    assert oct(f.stat().st_mode & 0o777) == "0o600"
    f.write_text(f.read_text()[:-3] + "AAA")
    with acting_as(EMP):
        assert o.get_document(cid, did)["status"] == "integrity"


def test_reminders_are_drafted_for_hr_only():
    o, clock = make()
    cid = start(o)
    clock.advance(days=20)
    with acting_as(HR1):
        r = o.reminders_due(2)
        assert r["sent"] is False and r["reminders"] and {"case", "task", "to", "due_date"} <= set(r["reminders"][0])
        assert any(x["task"] == "confirm_offer_accepted" and x["days_overdue"] > 0 for x in r["reminders"])
        assert o.reminders_due(-1)["status"] == "invalid_input"
    with acting_as(MGR):
        assert o.reminders_due()["status"] == "denied"


def test_cancel_and_listing_visibility():
    o, _ = make()
    cid = start(o)
    with acting_as(MGR):
        assert [c["id"] for c in o.list_cases()["cases"]] == [cid]
    with acting_as(person("E9")):
        assert o.list_cases()["cases"] == [] and o.case_status(cid)["status"] == "not_found"
    with acting_as(MGR):
        assert o.cancel_case(cid, "x")["status"] == "denied"
    with acting_as(HR1):
        assert o.cancel_case(cid, "offer withdrawn")["case"]["status"] == "cancelled"
        assert o.cancel_case(cid, "again")["status"] == "conflict"
        assert o.complete_task(cid, "confirm_offer_accepted")["status"] == "conflict"
        assert o.list_cases()["cases"] == [] and len(o.list_cases(status="")["cases"]) == 1


def test_organisation_scoping_and_deployment_org(monkeypatch):
    o, _ = make()
    cid = start(o)
    with acting_as(OTHER_ORG_HR):
        assert o.case_status(cid)["status"] == "not_found" and o.list_cases()["cases"] == []
        assert o.cancel_case(cid, "x")["status"] == "not_found" and o.get_identifiers(cid)["status"] == "not_found"
        assert o.start_onboarding("E7", "B", "b@x.in", "2026-12-01", "x", "y", "m")["status"] == "ok"        # same subject id, other org: no clash
    monkeypatch.setenv("VELARIS_ORG", "acme")
    with acting_as(OTHER_ORG_HR):
        assert o.list_cases()["status"] == "denied"


def test_dsr_export_masked_and_erase_follows_retention():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        o.submit_identifier(cid, "pan", PAN)
        o.submit_form(cid, "tax_declaration", {"regime": "new"})
        o.submit_form(cid, "emergency_contact", {"name": "R", "relation": "father", "phone": "9"})
        o.collect_document(cid, "identity_proof", "id.pdf", base64.b64encode(b"scan").decode())
    with acting_as(HR1):
        exp = o.dsr_export(ORG, "E7")
        assert PAN not in json.dumps(exp) and exp["onboarding_cases"][0]["identifiers"]["pan"]["masked"] == "******234F"
        res = o.dsr_erase(ORG, "E7")
        assert any("identifiers" in x for x in res["erased"]) and any("emergency_contact" in x for x in res["erased"])
        assert [h["what"].split(":")[-1] for h in res["held"]] == ["tax_declaration"] and res["held"][0]["status"] == "needs_review"
        after = o.dsr_export(ORG, "E7")["onboarding_cases"][0]
        assert after["identifiers"] == {} and after["name"] == "erased" and after["documents"] == [] and after["forms_submitted"] == ["tax_declaration"]
        assert not list((Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "docs").glob("*"))
    with acting_as(HR1), pytest.raises(AccessDenied):
        o.dsr_erase("globex", "E7")                                       # another organisation than the caller's
