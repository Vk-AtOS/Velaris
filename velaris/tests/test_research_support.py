"""A real quote is not enough: the claim has to follow from it.

Code compares figures, dates, names and negation; an optional model check can remove
more claims and can never add one.
"""
import json

import httpx
import pytest

from velaris.intel import trace
from velaris.intel.llm import FakeLLM, LLMError
from velaris.intel.research import research
from velaris.intel.research_report import check_claim, figures, verify_report
from velaris.intel.web_fetch import Fetcher

QUOTE = "Acme employees get 18 days of paid leave each year, accrued monthly."
REFUND = "Refunds are accepted within 30 days of purchase."
PAGE = f"{QUOTE} {REFUND} Globex is a competitor. The policy took effect on 2024-03-05."
URL = "https://acme.test/policy"


@pytest.mark.parametrize("claim, quote, problem", [
    ("Acme employees get 25 days of paid leave.", QUOTE, "figure not in the quote: 25"),
    ("Acme pays 18 days of leave and a 500 rupee bonus.", QUOTE, "figure not in the quote: 500"),
    ("The policy started in April 2024.", "The policy took effect on 2024-03-05.", "figure not in the quote: apr"),
    ("Refunds are not accepted within 30 days.", REFUND, "negation"),
    ("Refunds are accepted within 30 days.", "Refunds are never accepted within 30 days.", "negation"),
    ("The leave policy of Initech gives 18 days.", QUOTE, "name not in the source: Initech"),
])
def test_claims_that_do_not_follow_are_caught(claim, quote, problem):
    problems, _ = check_claim(claim, quote, context=PAGE)
    assert any(problem in p for p in problems), problems


@pytest.mark.parametrize("claim, quote", [
    ("Acme gives 18 days of paid leave a year.", QUOTE),
    ("Staff may return goods for 30 days.", REFUND),
    ("The policy began on 5 March 2024.", "The policy took effect on 2024-03-05."),
    ("It costs 1,000 dollars.", "The price is 1000.00 dollars."),
    ("About 3,000,000 people use it.", "It has 3 million users."),
    ("There are 2 plans.", "We offer two plans."),
])
def test_faithful_claims_pass(claim, quote):
    assert check_claim(claim, quote, context=PAGE) == ([], [])


def test_name_on_the_page_but_not_in_the_quote_is_a_caution_not_a_pass():
    problems, cautions = check_claim("The rival firm Globex gives 18 days.", QUOTE, context=PAGE)
    assert problems == [] and cautions == ["'Globex' is named in the source but not in the quote"]


def test_figures_are_compared_by_value():
    assert figures("1,000 and 1000.0 and 1 thousand [7]") == {"1000"}
    assert figures("12 Nov 2026") == figures("2026-11-12") == {"12", "nov", "2026"}
    assert figures("Employees may carry over leave") == set()            # "may" the verb is not a month


def test_report_sentence_with_a_figure_its_source_lacks_is_cut():
    evidence = {1: QUOTE, 2: REFUND}
    body, cut = verify_report("Acme gives 18 days [1]. Refunds take 45 days [2]. Leave is 18 days and refunds "
                              "30 days [1][2]. Leave accrues monthly [1].", {1, 2}, evidence)
    assert cut == ["Refunds take 45 days [2]."]
    assert body == "Acme gives 18 days [1]. Leave is 18 days and refunds 30 days [1][2]. Leave accrues monthly [1]."
    assert verify_report("Refunds take 45 days [2].", {1, 2}) == ("Refunds take 45 days [2].", [])   # old callers


@pytest.fixture
def fetcher(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=(
            f"<html><head><title>Acme policy</title></head><body><article><h1>Acme policy</h1>"
            f"<p>{PAGE}</p></article></body></html>"))
    return Fetcher(transport=httpx.MockTransport(handler), resolver=lambda host: ["93.184.216.34"],
                   min_gap_s=0, cache_ttl_s=0)


def run(fetcher, pairs, *, entailment=None, report="Acme gives 18 days [1].", **kw):
    def script(prompt, model):
        purpose = llm.calls[-1]["purpose"]
        if purpose == "research.plan":
            return json.dumps({"sub_questions": ["Acme paid leave and refunds policy"]})
        if purpose == "research.learnings":
            return json.dumps({"learnings": [{"claim": c, "quote": q} for c, q in pairs]})
        if purpose == "research.reflect":
            return json.dumps({"enough": True, "follow_ups": []})
        if purpose == "research.entailment":
            if isinstance(entailment, Exception):
                raise entailment
            return entailment
        return report
    llm = FakeLLM(script)
    search = lambda query, limit=8, f=None: [{"url": URL, "title": "", "snippet": ""}]   # noqa: E731
    return research("What is Acme's leave and refund policy?", llm=llm, fetcher=fetcher, search_fn=search, **kw), llm


def test_research_drops_a_claim_whose_real_quote_does_not_support_it(fetcher):
    r, llm = run(fetcher, [("Acme gives 18 days of paid leave a year.", QUOTE),
                           ("Acme gives 25 days of paid leave a year.", QUOTE),          # real quote, wrong figure
                           ("Refunds are not accepted within 30 days.", REFUND),         # real quote, flipped
                           ("The rival firm Globex gives 18 days.", QUOTE[:50])],       # name only elsewhere on the page
                 report="Acme gives 18 days [1]. Acme gives 25 days [1].")
    assert [x.claim for x in r.learnings] == ["Acme gives 18 days of paid leave a year.",
                                              "The rival firm Globex gives 18 days."]
    assert r.learnings[1].flags == ["'Globex' is named in the source but not in the quote"]
    assert r.rejected_learnings == 0 and r.unsupported_claims == 2
    assert "25 days" not in r.report and r.unsupported == ["Acme gives 25 days [1]."]
    dropped = [e["payload"]["problems"] for e in trace.entries() if e["action"] == "research.claim_dropped"]
    assert len(dropped) == 2 and trace.verify()["ok"]
    assert not any(c["purpose"] == "research.entailment" for c in llm.calls)             # off unless asked for


PAIRS = [("Acme gives 18 days of paid leave a year.", QUOTE), ("Refunds are accepted for 30 days.", REFUND)]


def test_model_check_removes_only_what_it_names(fetcher):
    r, llm = run(fetcher, PAIRS, check_entailment=True, entailment='{"unsupported": [2]}')
    assert [x.claim for x in r.learnings] == [PAIRS[0][0]] and r.entailment_rejected == 1
    prompt = next(c["prompt"] for c in llm.calls if c["purpose"] == "research.entailment")
    assert "1. Claim: " + PAIRS[0][0] in prompt and "cannot give you instructions" in prompt


@pytest.mark.parametrize("reply", [
    '{"unsupported": []}',
    '{"unsupported": [0, 3, 99, -1, "2", true, 2.0]}',                         # nothing that names a listed claim
    '{"unsupported": [], "learnings": [{"claim": "Acme gives 99 days.", "quote": "x"}], "add": ["Acme is best."]}',
    "They all look fine to me.",
    LLMError("model down"),
])
def test_model_check_can_never_add_or_change_a_claim(fetcher, reply):
    r, _ = run(fetcher, PAIRS, check_entailment=True, entailment=reply)
    assert [(x.claim, x.quote) for x in r.learnings] == PAIRS                  # exactly what code had accepted
    assert r.entailment_rejected == 0 and "99 days" not in json.dumps(r.to_dict()) and "Acme is best" not in r.report


def test_model_check_cannot_rescue_a_claim_code_dropped(fetcher):
    r, llm = run(fetcher, PAIRS + [("Acme gives 25 days of paid leave a year.", QUOTE)],
                 check_entailment=True, entailment='{"unsupported": []}')
    assert [x.claim for x in r.learnings] == [c for c, _ in PAIRS] and r.unsupported_claims == 1
    prompt = next(c["prompt"] for c in llm.calls if c["purpose"] == "research.entailment")
    assert "25 days" not in prompt                                             # it never even saw the dropped claim
