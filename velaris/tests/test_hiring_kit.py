"""INTERVIEW_KIT: rubrics, independent scorecards, aggregation without a verdict, kappa and alpha against hand-computed values, work samples."""
import json

import pytest
from velaris.agentkit.hiring_testkit import ORG, as_, bootstrap, clean_keys, consent, who

from velaris.agentkit import hiring_kit as hk
from velaris.agentkit import hiring_stats as st
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.INTERVIEW_KIT.main import InterviewKit
from velaris.intel.paths import agent_dir

ANCHORS = {str(i): t for i, t in enumerate(["No working code", "Code with major gaps", "Works for the main case", "Works, tested, readable", "Robust, tested, explains trade-offs"], 1)}
NO_VERDICT = ("overall", "total", "composite", "pass", "fail", "hired", "rejected")


# ---- the statistics, against numbers worked out by hand ------------------------------------------------------------------
def test_weighted_kappa_hand_values():
    a, b = [1, 2, 3, 3], [1, 2, 2, 3]
    # one disagreement of one step in four items. Marginals A (.25,.25,.5) B (.25,.5,.25).
    assert st.weighted_kappa(a, b, [1, 2, 3], "none") == pytest.approx(0.4375 / 0.6875)           # po .75, pe .3125
    assert st.weighted_kappa(a, b, [1, 2, 3], "linear") == pytest.approx(5 / 7)                    # 1 - .125/.4375
    assert st.weighted_kappa(a, b, [1, 2, 3], "quadratic") == pytest.approx(0.8)                   # 1 - .0625/.3125
    assert st.weighted_kappa([1, 2, 3], [1, 2, 3], [1, 2, 3]) == 1.0
    assert st.weighted_kappa([1, 3, 1, 3], [3, 1, 3, 1], [1, 2, 3], "linear") == pytest.approx(-1.0)   # systematic opposites
    assert st.weighted_kappa([2, 2, 2], [2, 2, 2], [1, 2, 3]) is None                              # no variation: undefined, not 1
    for bad in (([1], [1, 2], [1, 2]), ([], [], [1]), ([9], [1], [1, 2])):
        with pytest.raises(ValueError):
            st.weighted_kappa(*bad)
    with pytest.raises(ValueError):
        st.weighted_kappa([1], [1], [1, 2], "cubic")


def test_krippendorff_alpha_hand_values_and_the_published_example():
    # three units: [1,1] [2,2] [1,2]. o11=2, o22=2, o12=o21=1; n1=n2=3, n=6. D_o=2/6, D_e=18/30, alpha=1-(1/3)/(3/5)=4/9
    assert st.krippendorff_alpha([[1, 1], [2, 2], [1, 2]], "nominal") == pytest.approx(4 / 9)
    assert st.krippendorff_alpha([[1, 1], [2, 2], [3, 3]], "ordinal") == pytest.approx(1.0)
    assert st.krippendorff_alpha([[1, 5], [5, 1], [1, 5]], "interval") < 0
    assert st.krippendorff_alpha([[3, 3], [3, 3]], "ordinal") is None                              # no variation
    assert st.krippendorff_alpha([[1, None], [None, 2]], "ordinal") is None                        # no unit with two ratings
    N = None                                                                                       # Krippendorff's worked example: 4 raters, 12 units, missing data
    units = list(zip([1, 2, 3, 3, 2, 1, 4, 1, 2, N, N, N], [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, N, 3],
                     [N, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, N], [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, N]))
    assert st.krippendorff_alpha(units, "nominal") == pytest.approx(0.743, abs=5e-4)
    assert st.krippendorff_alpha(units, "ordinal") == pytest.approx(0.815, abs=5e-4)
    assert st.krippendorff_alpha(units, "interval") == pytest.approx(0.849, abs=5e-4)
    with pytest.raises(ValueError):
        st.krippendorff_alpha(units, "ratio")


def test_leniency_offsets_by_hand():
    # x: 5 and 4; y: 3 and 4. x - y = +2 and 0 -> x +1.0; y -1.0. A rater with no shared item has no offset.
    assert st.leniency({"x": {"u1": 5, "u2": 4}, "y": {"u1": 3, "u2": 4}, "z": {"u9": 1}}) == {"x": 1.0, "y": -1.0, "z": None}


# ---- the agent ---------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def env():
    ats, kit = AtsCore(), InterviewKit()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        for comp in ("coding", "communication"):
            assert kit.define_rubric(competency=comp, description=f"How well the candidate shows {comp}", anchors=ANCHORS)["status"] == "ok"
        qs = [kit.add_question(text="Walk me through a bug you fixed.", competency="coding", follow_ups=["What did you try first?"])["question"]["id"],
              kit.add_question(text="Explain a design to a non-engineer.", competency="communication")["question"]["id"]]
        k = kit.create_kit(requisition_id=rid, competencies=["coding", "communication"], question_ids=qs)
        assert k["status"] == "ok"
    return ats, kit, rid, c, qs


def candidate(ats, rid, c, i):
    with as_(c["rec"]):
        return ats.add_candidate(name=f"Cand Number{i}", email=f"c{i}@example.com", phone=f"+91 9{i}111 2222{i}", source="careers_page", requisition_id=rid,
                                 consent=consent())["application"]["id"]


def card(coding, comm, qs=None, ev="Described the bug in detail and the fix they chose."):
    return [{"competency": "coding", "score": coding, "evidence": ev, "question_id": qs[0] if qs else None},
            {"competency": "communication", "score": comm, "evidence": ev + " Clear.", "question_id": None}]


def test_bank_rubric_and_kit_validation(env):
    ats, kit, rid, c, qs = env
    with as_(c["rec"]):
        assert kit.define_rubric(competency="coding", description="dup", anchors=ANCHORS)["status"] == "conflict"
        assert kit.define_rubric(competency="x", description="d", anchors={"1": "a", "2": "b"})["status"] == "invalid_input"
        assert kit.add_question(text="Why?", competency="telepathy")["status"] == "not_found"
        assert kit.create_kit(requisition_id=rid, competencies=["coding"], question_ids=qs[:1])["status"] == "conflict"        # one per requisition
        got = kit.get_kit(requisition_id=rid)
        assert [r["competency"] for r in got["rubrics"]] == ["coding", "communication"] and got["rubrics"][0]["anchors"]["1"] == "No working code"
        assert got["kit"]["org"] == ORG and "No automated judgement" in got["statement"]
    with as_(who("interviewer")):
        assert kit.define_rubric(competency="z", description="d", anchors=ANCHORS)["status"] == "denied"
        assert kit.get_kit(requisition_id=rid)["status"] == "ok"


def test_scorecards_are_independent_locked_and_complete(env):
    ats, kit, rid, c, qs = env
    app = candidate(ats, rid, c, 1)
    i1, i2 = who("interviewer", id="iv-1"), who("interviewer", id="iv-2")
    with as_(c["rec"]):
        assert kit.assign_panel(application_id=app, interviewer_ids=["iv-1", "iv-2"])["status"] == "ok"
    with as_(who("interviewer", id="iv-9")):
        assert kit.submit_scorecard(application_id=app, ratings=card(3, 3))["status"] == "denied"             # not on the panel
    with as_(i1):
        before = kit.scorecards(application_id=app)
        assert before["visible"] is False and before["submitted_by"] == []
        for bad in ([], card(3, 3)[:1], card(6, 3), card(0, 3), card(3.5, 3), card(True, 3), card(3, 3, ev="ok"), card(3, 3, qs=["q-nope"]),
                    [*card(3, 3), {"competency": "coding", "score": 1, "evidence": "twice again and again"}]):
            assert kit.submit_scorecard(application_id=app, ratings=bad)["status"] == "invalid_input", bad
        assert kit.submit_scorecard(application_id=app, ratings=card(4, 3, qs))["locked"] is True
        assert kit.submit_scorecard(application_id=app, ratings=card(1, 1))["status"] == "conflict"                # locked on submit
        assert kit.scorecards(application_id=app)["visible"] is True                                           # own card submitted
    with as_(i2):
        assert kit.scorecards(application_id=app)["visible"] is False                                          # has not submitted: sees nobody's scores
    with as_(c["mgr"]):
        hidden = kit.scorecards(application_id=app)
        assert hidden["visible"] is False and hidden["submitted_by"] == ["iv-1"] and "competencies" not in hidden   # panel incomplete
    with as_(i2):
        assert kit.submit_scorecard(application_id=app, ratings=card(2, 3))["submitted"] == 2
    with as_(c["mgr"]):
        full = kit.scorecards(application_id=app)
    assert full["visible"] is True and full["panel_complete"] is True
    coding = next(x for x in full["competencies"] if x["competency"] == "coding")
    assert [(r["interviewer"], r["score"]) for r in coding["ratings"]] == [("iv-1", 4), ("iv-2", 2)] and all(r["evidence"] for r in coding["ratings"])
    assert coding["mean"] == 3.0 and coding["working"] == "(4 + 2) / 2 = 3.00" and coding["spread"] == 2 and "talk it through" in coding["discuss"]
    comm = next(x for x in full["competencies"] if x["competency"] == "communication")
    assert comm["spread"] == 0 and comm["discuss"] is None
    assert "No automated judgement of a person" in full["statement"] and "No overall number" in full["note"]
    clean_keys(full, NO_VERDICT)                                                                           # no overall number, no verdict, no ranking
    assert "No automated judgement" in kit.health_check()["statement"]


def test_agreement_with_hand_computed_kappa_and_alpha(env):
    ats, kit, rid, c, qs = env
    a_scores, b_scores = [1, 2, 3, 3, 4], [1, 2, 2, 3, 4]
    for i in range(5):
        app = candidate(ats, rid, c, i)
        with as_(c["rec"]):
            kit.assign_panel(application_id=app, interviewer_ids=["iv-a", "iv-b"])
        with as_(who("interviewer", id="iv-a")):
            kit.submit_scorecard(application_id=app, ratings=card(a_scores[i], 3))
        with as_(who("interviewer", id="iv-b")):
            kit.submit_scorecard(application_id=app, ratings=card(b_scores[i], 3 if i != 4 else 4))
    with as_(c["mgr"]):
        r = kit.agreement_report(competency="coding")
    # coding: pairs (1,1)(2,2)(3,2)(3,3)(4,4), quadratic weights over 1..5: D_o = (1/16)/5, D_e = 53/16/25, kappa = 1 - 0.0125/0.1325
    assert r["rated_items"] == 5 and r["raters"] == ["iv-a", "iv-b"]
    assert r["pairs"][0]["weighted_kappa"] == pytest.approx(1 - 0.0125 / 0.1325, abs=1e-3) == pytest.approx(0.906, abs=1e-3)
    assert r["pairs"][0]["paired_ratings"] == 5
    expected_alpha = st.krippendorff_alpha([[x, y] for x, y in zip(a_scores, b_scores)], "ordinal")
    assert r["krippendorff_alpha_ordinal"] == round(expected_alpha, 3) and r["krippendorff_alpha_ordinal"] > 0.667 and "acceptable" in r["alpha_reading"]
    assert r["rater_leniency_offset"] == {"iv-a": 0.2, "iv-b": -0.2}                                         # a is one step above b on one of five items: 1/5
    with as_(c["mgr"]):
        cal = kit.calibration_report()
        both = kit.agreement_report()
    comp = {x["competency"]: x for x in cal["competencies"]}
    assert comp["coding"]["krippendorff_alpha_ordinal"] == r["krippendorff_alpha_ordinal"] and comp["communication"]["rated_items"] == 5
    assert both["rated_items"] == 10 and "calibration aid, not a ranking of people" in both["leniency_note"]
    clean_keys(cal, NO_VERDICT)
    with as_(who("interviewer", id="iv-a")):
        assert kit.agreement_report()["status"] == "denied" and kit.calibration_report()["status"] == "denied"


def test_too_little_data_is_reported_not_invented(env):
    ats, kit, rid, c, qs = env
    app = candidate(ats, rid, c, 1)
    with as_(c["rec"]):
        kit.assign_panel(application_id=app, interviewer_ids=["iv-a", "iv-b"])
    for iv, s in (("iv-a", 3), ("iv-b", 2)):
        with as_(who("interviewer", id=iv)):
            kit.submit_scorecard(application_id=app, ratings=card(s, 3))
    with as_(c["rec"]):
        r = kit.agreement_report(competency="coding")
    assert r["pairs"][0]["weighted_kappa"] is None and "not enough data" in r["pairs"][0]["note"]
    with as_(c["rec"]):
        assert kit.agreement_report(competency="nothing")["krippendorff_alpha_ordinal"] is None


def test_erasure_keeps_numbers_for_calibration_and_drops_text_and_identity(env):
    ats, kit, rid, c, qs = env
    app = candidate(ats, rid, c, 1)
    cid = json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"][app]["candidate_id"]
    with as_(c["rec"]):
        kit.assign_panel(application_id=app, interviewer_ids=["iv-a", "iv-b"])
    for iv, s in (("iv-a", 3), ("iv-b", 2)):
        with as_(who("interviewer", id=iv)):
            kit.submit_scorecard(application_id=app, ratings=card(s, 3, ev="Said her mother in Madurai was unwell during the project."))
    with as_(c["adm"]):
        assert ats.erase_candidates(candidate_ids=[cid], reason="erasure_request")["removed_by_module"]["hiring_kit"] == 2
        r = kit.agreement_report(competency="coding")
    stored = (agent_dir("INTERVIEW_KIT") / "kit.json").read_text()
    assert "Madurai" not in stored and cid not in stored
    assert r["rated_items"] == 1 and r["raters"] == ["iv-a", "iv-b"]                                       # the anonymous numbers still count


def test_work_samples_are_checklists_with_counts_never_pass_or_fail(env):
    ats, kit, rid, c, qs = env
    app = candidate(ats, rid, c, 1)
    with as_(c["rec"]):
        assert kit.create_work_sample(title="Refactor", brief="x", checklist=["only one"])["status"] == "invalid_input"
        ws = kit.create_work_sample(title="Refactor a function", brief="Here is a 60-line function. Make it testable.", checklist=["Adds tests", "Keeps behaviour", "Explains trade-offs"],
                                    ai_tools_allowed=True)["work_sample"]
        kit.assign_panel(application_id=app, interviewer_ids=["iv-1"])
    ev = lambda i, met: {"index": i, "met": met, "evidence": f"saw it in the diff, item {i}"}
    with as_(who("interviewer", id="iv-1")):
        assert kit.review_work_sample(application_id=app, work_sample_id=ws["id"], checks=[ev(0, True)])["status"] == "invalid_input"        # every item needs a check
        r = kit.review_work_sample(application_id=app, work_sample_id=ws["id"], checks=[ev(0, True), ev(1, True), ev(2, False)], notes="n")
        assert r["items_met"] == "2 of 3" and r["status"] == "ok" and "No automated judgement" in r["statement"]
        assert kit.review_work_sample(application_id=app, work_sample_id=ws["id"], checks=[ev(0, True), ev(1, True), ev(2, False)])["status"] == "conflict"
    with as_(c["mgr"]):
        reviews = kit.work_sample_reviews(application_id=app)["reviews"]
    assert reviews[0]["reviewer_id"] == "iv-1" and reviews[0]["org"] == ORG
    clean_keys(r, NO_VERDICT)
    assert ws["ai_tools_allowed"] is True


def test_denied_and_org_scoped(env):
    ats, kit, rid, c, qs = env
    assert kit.list_questions()["status"] == "unauthenticated"
    with as_(who("recruiter", org="other")):
        assert kit.list_questions()["questions"] == [] and kit.get_kit(requisition_id=rid)["status"] == "not_found"
        assert kit.define_rubric(competency="coding", description="d", anchors=ANCHORS)["status"] == "ok"        # another org has its own namespace
    app = candidate(ats, rid, c, 1)
    with as_(who("interviewer", id="iv-1")):
        assert kit.assign_panel(application_id=app, interviewer_ids=["iv-1"])["status"] == "denied"
        assert kit.scorecards(application_id=app)["status"] == "not_found"                                   # no panel yet


def test_work_sample_review_needs_a_seat_on_the_applications_panel(env):
    ats, kit, rid, c, qs = env
    app, other = candidate(ats, rid, c, 1), candidate(ats, rid, c, 2)
    with as_(c["rec"]):
        ws = kit.create_work_sample(title="T", brief="b", checklist=["one thing", "another"])["work_sample"]
        kit.assign_panel(application_id=app, interviewer_ids=["iv-1"])
    checks = [{"index": i, "met": True, "evidence": "seen in the diff"} for i in range(2)]
    with as_(who("interviewer", id="iv-9")):                                  # right role, not on the panel
        assert kit.review_work_sample(application_id=app, work_sample_id=ws["id"], checks=checks)["status"] == "denied"
    with as_(who("interviewer", id="iv-1")):                                  # on a panel, but not this application's (none exists)
        assert kit.review_work_sample(application_id=other, work_sample_id=ws["id"], checks=checks)["status"] == "denied"
        assert kit.review_work_sample(application_id=app, work_sample_id=ws["id"], checks=checks)["status"] == "ok"
