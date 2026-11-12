"""MRF family and the agreement check: rubric scoring, revision instructions, the draft-check-revise loop,
self-consistency. Model paths use FakeLLM only."""
import json

import pytest

from velaris.agents.META_REASONING_CORE.main import META_REASONING_COREAgent
from velaris.agents.MRF_EVAL.main import MRF_EVALAgent
from velaris.agents.MRF_REFLECT.main import MRF_REFLECTAgent
from velaris.agents.SELF_CONSISTENCY.main import SELF_CONSISTENCYAgent
from velaris.intel.llm import FakeLLM

RUBRIC = {"required": ["GSTIN", "due date"], "forbidden": ["guaranteed"], "max_chars": 120}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    for key in ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK"):
        monkeypatch.delenv(key, raising=False)


def test_eval_scores_each_check():
    e = MRF_EVALAgent()
    good = e.evaluate("Please quote your GSTIN; the due date is 1 Dec.", RUBRIC)
    assert good["passed"] is True and good["score"] == 1.0 and len(good["checks"]) == 4
    bad = e.evaluate("Payment is guaranteed. Due date: soon.", RUBRIC)
    assert bad["passed"] is False and bad["score"] == 0.5
    assert {(f["check"], f["detail"]) for f in bad["failures"]} == {("required", "GSTIN"), ("forbidden", "guaranteed")}


def test_eval_json_fields_and_pattern():
    e = MRF_EVALAgent()
    rubric = {"fields": ["invoice", "amount"], "pattern": r"INV-\d+"}
    assert e.evaluate({"invoice": "INV-9", "amount": 5}, rubric)["passed"] is True
    assert e.evaluate('Here you go: {"invoice": "INV-9"}', rubric)["score"] == pytest.approx(2 / 3, abs=1e-4)
    assert e.evaluate("no json", {"fields": ["a"]})["passed"] is False


@pytest.mark.parametrize("rubric", [{}, {"colour": "red"}, {"required": "GSTIN"}, {"max_chars": -1},
                                    {"pattern": "("}, None])
def test_eval_bad_rubric(rubric):
    assert MRF_EVALAgent().evaluate("text", rubric)["status"] == "invalid_input"


def test_eval_bad_output():
    assert MRF_EVALAgent().evaluate(None, RUBRIC)["passed"] is False
    assert MRF_EVALAgent().evaluate("x" * 60_000, RUBRIC)["status"] == "invalid_input"


def test_reflect_turns_failures_into_instructions():
    ev = MRF_EVALAgent().evaluate("It is guaranteed! " * 10, RUBRIC)
    r = MRF_REFLECTAgent().reflect(ev)
    assert r["needs_revision"] is True
    assert r["instructions"] == ["Mention 'GSTIN'.", "Mention 'due date'.", "Remove 'guaranteed'.",
                                 "Shorten to at most 120 characters."]
    passed = MRF_EVALAgent().evaluate("GSTIN and due date", RUBRIC)
    assert MRF_REFLECTAgent().reflect(passed)["instructions"] == []
    assert MRF_REFLECTAgent().reflect({"x": 1})["status"] == "invalid_input"


def test_revise_needs_a_model_and_validates_its_reply():
    ev = MRF_EVALAgent().evaluate("Payment guaranteed.", RUBRIC)
    assert MRF_REFLECTAgent().revise("Payment guaranteed.", ev)["status"] == "not_configured"
    llm = FakeLLM({"Rewrite": json.dumps({"revised": "Send your GSTIN before the due date."})})
    r = MRF_REFLECTAgent().revise("Payment guaranteed.", ev, llm=llm)
    assert r["revised"] == "Send your GSTIN before the due date." and r["proposed_by_model"] is True
    assert "Remove 'guaranteed'." in llm.calls[0]["prompt"]
    empty = MRF_REFLECTAgent().revise("Payment guaranteed.", ev, llm=FakeLLM({"Rewrite": '{"revised": ""}'}))
    assert empty["status"] == "rejected"


def test_pick_best_without_a_model():
    core = META_REASONING_COREAgent()
    r = core.pick_best(["Guaranteed payment.", "Share GSTIN by the due date.", "GSTIN please"], RUBRIC)
    assert r["best_index"] == 1 and r["passed"] is True
    tie = core.pick_best(["GSTIN, due date, long version here", "GSTIN due date"], RUBRIC)
    assert tie["best_index"] == 1                                       # same score: shorter wins
    assert core.pick_best([], RUBRIC)["status"] == "invalid_input"
    assert core.pick_best(["a"], {"bogus": 1})["best"] is None


def test_solve_loops_until_the_rubric_passes():
    replies = iter([json.dumps({"answer": "Payment is guaranteed."}),
                    json.dumps({"revised": "Send the GSTIN."}),
                    json.dumps({"revised": "Send the GSTIN before the due date."})])
    llm = FakeLLM(lambda prompt, model: next(replies))
    r = META_REASONING_COREAgent().solve("Write a reminder to a vendor", RUBRIC, llm=llm, max_rounds=3)
    assert r["status"] == "ok" and r["passed"] is True and r["rounds"] == 3
    assert r["answer"] == "Send the GSTIN before the due date."
    assert [a["score"] for a in r["attempts"]] == [0.25, 0.75, 1.0]


def test_solve_keeps_the_best_attempt_and_reports_not_passed():
    replies = iter([json.dumps({"answer": "GSTIN"}), json.dumps({"revised": "guaranteed!"})])
    r = META_REASONING_COREAgent().solve("Write it", RUBRIC, llm=FakeLLM(lambda p, m: next(replies)), max_rounds=2)
    assert r["status"] == "not_passed" and r["answer"] == "GSTIN" and r["passed"] is False


def test_solve_without_a_model_or_with_bad_input():
    core = META_REASONING_COREAgent()
    assert core.solve("Write it", RUBRIC)["status"] == "not_configured"
    assert core.solve("", RUBRIC, llm=FakeLLM({}))["status"] == "invalid_input"
    assert core.solve("Write it", RUBRIC, llm=FakeLLM({}), max_rounds=9)["status"] == "invalid_input"
    assert core.solve("Write it", RUBRIC, llm=FakeLLM({"Do the task": "nothing"}))["status"] == "model_error"


def test_agreement_measures_majority_share():
    c = SELF_CONSISTENCYAgent()
    r = c.agreement(["1,200", "1200.0", " 1200 ", "1500", "1200."])
    assert r["agreement"] == 0.8 and r["majority"] == "1,200" and r["consistent"] is True and r["distinct"] == 2
    split = c.agreement(["Chennai", "Mumbai", "Delhi"])
    assert split["consistent"] is False and split["agreement"] == pytest.approx(1 / 3, abs=1e-4)
    assert c.agreement(["yes"])["consistent"] is False                  # one answer proves nothing
    assert c.agreement(["Yes.", "yes", "YES"])["agreement"] == 1.0


def test_agreement_bad_input_and_legacy_check():
    c = SELF_CONSISTENCYAgent()
    assert c.agreement([])["status"] == "invalid_input"
    assert c.agreement([{"a": 1}])["status"] == "invalid_input"
    assert c.agreement(["a", "a"], threshold=2)["status"] == "invalid_input"
    assert c.check({"name": "Velaris"}) is False
    assert c.check({"answers": ["42", "42", "41"]}) is True


def test_sample_asks_n_times_and_measures():
    answers = iter(["42", "42", "forty-two", "42"])
    llm = FakeLLM(lambda p, m: json.dumps({"answer": next(answers)}))
    r = SELF_CONSISTENCYAgent().sample("How many leave days remain?", n=4, llm=llm)
    assert len(llm.calls) == 4 and r["agreement"] == 0.75 and r["consistent"] is True and r["majority"] == "42"
    assert SELF_CONSISTENCYAgent().sample("Q?")["status"] == "not_configured"
    assert SELF_CONSISTENCYAgent().sample("Q?", n=1, llm=llm)["status"] == "invalid_input"
    junk = SELF_CONSISTENCYAgent().sample("Q?", n=3, llm=FakeLLM(lambda p, m: "no"))
    assert junk["status"] == "model_error" and junk["consistent"] is False
