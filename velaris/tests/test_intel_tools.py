"""tools.py: the tool registry built on the allowlist and flow.py (KAN-29). Fake model only."""
import json

import pytest

from velaris.backend.engine import backend
from velaris.core.access import AccessDenied, Caller
from velaris.intel import tools
from velaris.intel.flow import Flow
from velaris.intel.llm import FakeLLM

SAMPLES = {"hr": "LEAVE_MANAGEMENT.apply", "finance": "TREASURIX.runway_months", "_connectors": "JIRA.create_issue",
           "it_infrastructure": "ITSM_ENGINE.list_tickets", "data_knowledge": "DOCUMENT_LIBRARY.search"}


@pytest.fixture(autouse=True)
def registry():
    tools.clear()
    tools.register_allowlist(backend)
    yield
    tools.clear()


def test_every_allowlisted_method_becomes_a_tool_in_its_department():
    from velaris.api.allowlist import METHODS
    assert len(tools.list()) == sum(len(m) for m in METHODS.values())
    for dept, name in SAMPLES.items():
        spec = tools.get(name)
        assert spec is not None and spec.department == dept and spec.description
        assert spec in tools.list(dept) and spec not in tools.list("nonexistent")


def test_side_effects_and_sensitivity_fail_closed():
    assert tools.get("TREASURIX.runway_months").side_effects == "none"
    assert tools.get("LEAVE_MANAGEMENT.apply").side_effects == "internal"
    assert tools.get("OFFER_LETTERS.send_offer").side_effects == "external"
    assert tools.get("LEAVE_MANAGEMENT.get_balance").sensitivity == "restricted"       # not on the reviewed list
    assert tools.get("ADVANCED_SEARCH_ENGINE.web_search").sensitivity == "public"
    assert all(t.side_effects != "none" for t in tools.list() if t.kind == "act")
    with pytest.raises(tools.ToolError):
        tools.ToolSpec("A.b", "A", "b", {}, side_effects="none", kind="act")


def test_the_actor_parameter_is_never_offered_to_a_model():
    spec = tools.get("LEAVE_MANAGEMENT.approve")
    assert spec.actor_param == "reviewed_by" and "reviewed_by" not in spec.params["properties"]
    assert spec.required_roles


def test_schema_comes_from_the_signature_and_exports_in_both_tool_formats():
    spec = tools.get("TREASURIX.runway_months")
    assert spec.params["type"] == "object" and spec.params["additionalProperties"] is False
    assert spec.params["required"] and all(v.get("type") == "number" for v in spec.params["properties"].values())
    o, a = tools.to_openai(spec), tools.to_anthropic(spec)
    assert o["type"] == "function" and o["function"]["name"] == "TREASURIX__runway_months"
    assert o["function"]["parameters"] == a["input_schema"] == spec.params and a["description"] == spec.description


def test_register_is_idempotent_and_refuses_a_different_tool_under_a_known_name():
    spec = tools.get("TREASURIX.runway_months")
    assert tools.register(spec) is spec
    other = tools.ToolSpec(spec.name, spec.agent, spec.method, {"type": "object"}, side_effects="none", kind="read")
    with pytest.raises(tools.ToolError):
        tools.register(other)


def test_invalid_arguments_are_rejected_before_the_agent_is_called():
    spec = tools.get("TREASURIX.runway_months")
    assert tools.validate(spec, {}) and tools.validate(spec, {"nope": 1}) and tools.validate(spec, [])
    first = next(iter(spec.params["properties"]))
    assert tools.validate(spec, {**{k: 1 for k in spec.params["required"]}, first: "x"})      # text where a number goes
    assert tools.validate(spec, {**{k: 1 for k in spec.params["required"]}, first: True})     # a bool is not a number
    calls = []
    t = tools.flow_tool(spec, lambda **a: calls.append(a))
    flow = Flow([t], llm=FakeLLM(lambda p, m: json.dumps({"tool": spec.name, "args": {"bogus": 1}}) if "NOT DONE" not in p
                                  else json.dumps({"final": "gave up"})), path=":memory:")
    # the flow itself refuses an argument the tool does not list; a wrong TYPE reaches checked() and is refused there
    r = flow.start("x")
    assert r.status == "done" and calls == []
    with pytest.raises(ValueError):
        t.fn(**{k: "text" for k in spec.params["required"]})
    assert calls == []


def test_unauthorised_caller_is_denied_by_the_allowlist_rule():
    spec = tools.get("LEAVE_MANAGEMENT.approve")
    nobody = Caller("u1", "acme", frozenset({"employee"}))
    with pytest.raises(AccessDenied):
        tools.runner(backend, spec, nobody)(leave_id=1)
    other_org = Caller("u1", "other", frozenset({"hr_admin"}))
    import os
    os.environ["VELARIS_ORG"] = "acme"
    try:
        with pytest.raises(AccessDenied):
            tools.runner(backend, spec, other_org)(leave_id=1)
    finally:
        del os.environ["VELARIS_ORG"]


def test_a_read_tool_runs_and_a_side_effecting_tool_is_blocked_without_approval(tmp_path):
    read, act = tools.get("TREASURIX.runway_months"), tools.get("LEAVE_MANAGEMENT.apply")
    ran = []
    assert tools.flow_tool(read, lambda **a: ran.append(a)).needs_approval is False
    t_act = tools.flow_tool(act, lambda **a: ran.append(a))
    assert t_act.needs_approval is True and t_act.idempotent is False
    args = {k: "x" for k in act.params["required"]}
    flow = Flow([t_act], llm=FakeLLM(lambda p, m: json.dumps({"tool": act.name, "args": args})), path=str(tmp_path / "f.db"))
    r = flow.start("apply for leave")
    assert r.status == "waiting_approval" and ran == [] and r.pending["tool"] == act.name
