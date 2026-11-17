"""Round 3 (KAN-87): CRK_CHAIN seals seq and check, EAC_CORE.history, CSM register bounds and owner ordering."""
import copy

import pytest

from velaris.agents.CRK_CHAIN.main import CRK_CHAINAgent
from velaris.agents.CSM_CORE.main import CSMCoreAgent
from velaris.agents.CSM_LINKER.main import CSMLinkerAgent
from velaris.agents.EAC_CORE.main import EAC_COREAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


STEPS = [{"id": "p", "claim": "A", "kind": "premise"},
         {"id": "c", "claim": "B", "kind": "conclusion", "depends_on": ["p"], "check": {"left": 1, "op": "<", "right": 2}}]


def test_chain_detects_renumbering_edited_check_and_smuggled_fields():
    a = CRK_CHAINAgent()
    chain = a.build([{**STEPS[0], "note": "unsealed"}, STEPS[1]])
    assert "note" not in chain["steps"][0] and a.verify(chain)["intact"] is True
    swapped = copy.deepcopy(chain)
    swapped["steps"][0]["seq"], swapped["steps"][1]["seq"] = 2, 1
    assert a.verify(swapped)["status"] == "tampered"
    edited = copy.deepcopy(chain)
    edited["steps"][1]["check"] = {"left": 2, "op": "<", "right": 1}
    assert a.verify(edited)["status"] == "tampered"
    assert a.build([{**STEPS[0], "check": "text"}])["status"] == "invalid_chain"


def test_eac_history_finds_a_subject_given_with_spaces_and_checks_limit_first():
    core = EAC_COREAgent()
    core.assess("inv-1 ", {"x": 1}, [{"id": "c1", "check": "present", "field": "x"}])
    assert core.history("  inv-1")["status"] == "ok"
    assert core.history("", 5)["status"] == "invalid_input" and core.history("inv-1", True)["status"] == "invalid_input"


def test_csm_owner_is_checked_before_the_goal_is_stored_and_history_survives_reset():
    c = CSMCoreAgent()
    assert c.set_goal("g", 10, 10, owner="g")["status"] == "invalid_input"
    assert c.goals() == {}                                       # nothing half-stored
    assert c.set_goal("g", 10, 10, owner="asha")["status"] == "ok"
    c.review("g", 2, 1)
    c.set_goal("g", 20, 10)
    assert c.review("g", 3, 2)["reviews"] == 2


def test_csm_linker_is_bounded_and_path_still_works(monkeypatch):
    monkeypatch.setitem(CSMLinkerAgent.link.__globals__, "MAX_LINKS", 2)     # the module the class really runs in
    l = CSMLinkerAgent()
    assert l.link("a", "b")["linked"] and l.link("b", "c")["linked"]
    assert l.link("c", "d")["status"] == "full"
    assert l.path("a", "c")["path"] == ["a", "b", "c"]
