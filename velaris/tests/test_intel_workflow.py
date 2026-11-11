"""workflow.py: import, analysis, plan and permissions for an n8n-style export."""
import copy
import json

import pytest

from velaris.intel import workflow
from velaris.intel.workflow import WorkflowError, analyse, load, required_permissions, to_plan

BASE = "n8n-nodes-base."
LC = "@n8n/n8n-nodes-langchain."
URL_KEY = "sk-live1234567890abcdefghijklmnop"
HEADER_KEY = "ghp_" + "a1B2" * 9
SLACK_TOKEN = "xoxb-123456789012-abcdefghijklmnop"


def _node(name, type_, **rest):
    return {"id": name.lower().replace(" ", "-"), "name": name, "type": type_, "typeVersion": 1,
            "position": [0, 0], "parameters": {}, **rest}


def _to(*targets):
    return [{"node": t, "type": "main", "index": i} for t, i in targets]


# An order intake board: a webhook, a priority branch, a CRM lookup feeding an AI agent (model
# and tool attached), a ticket call that is retried through a wait loop, a merge, a Slack
# notification, a disabled legacy step and a node nobody wired up.
FIXTURE = {
    "name": "Order intake",
    "active": False,
    "settings": {"executionOrder": "v1"},
    "nodes": [
        _node("Order Webhook", BASE + "webhook", parameters={"httpMethod": "POST", "path": "orders"},
              webhookId="wh-1"),
        _node("Is Priority?", BASE + "if",
              parameters={"conditions": {"string": [{"value1": "={{ $json.tier }}", "value2": "gold"}]}}),
        _node("Fetch Customer", BASE + "httpRequest", typeVersion=4.2,
              parameters={"method": "GET",
                          "url": f"https://api.crm.example.com/v1/customers?api_key={URL_KEY}",
                          "headerParameters": {"parameters": [{"name": "X-Token", "value": HEADER_KEY}]}},
              credentials={"httpHeaderAuth": {"id": "11", "name": "CRM key"}},
              retryOnFail=True, maxTries=3, waitBetweenTries=1000),
        _node("Triage Agent", LC + "agent", parameters={"text": "={{ $json.body }}"}),
        _node("OpenAI Model", LC + "lmChatOpenAi", parameters={"model": "gpt-4o-mini"},
              credentials={"openAiApi": {"id": "12", "name": "OpenAI prod"}}),
        _node("Lookup Tool", LC + "toolHttpRequest", parameters={"url": "https://kb.example.com/search"}),
        _node("Create Ticket", BASE + "httpRequest",
              parameters={"method": "POST", "url": "https://desk.example.com/tickets"}),
        _node("Ticket OK?", BASE + "if"),
        _node("Wait", BASE + "wait", parameters={"amount": 5}),
        _node("Merge", BASE + "merge"),
        _node("Notify Slack", BASE + "slack",
              parameters={"resource": "message", "operation": "post", "channel": SLACK_TOKEN},
              credentials={"slackApi": {"id": "13", "name": "Ops Slack"}},
              onError="continueRegularOutput"),
        _node("Legacy Email", BASE + "emailSend", disabled=True,
              credentials={"smtp": {"id": "14", "name": "Old SMTP"}}),
        _node("Orphan Sheet", BASE + "googleSheets", parameters={"operation": "frobnicate"}),
    ],
    "connections": {
        "Order Webhook": {"main": [_to(("Is Priority?", 0))]},
        "Is Priority?": {"main": [_to(("Fetch Customer", 0)), _to(("Create Ticket", 0))]},
        "Fetch Customer": {"main": [_to(("Triage Agent", 0))]},
        "OpenAI Model": {"ai_languageModel": [[{"node": "Triage Agent", "type": "ai_languageModel", "index": 0}]]},
        "Lookup Tool": {"ai_tool": [[{"node": "Triage Agent", "type": "ai_tool", "index": 0}]]},
        "Triage Agent": {"main": [_to(("Merge", 1))]},
        "Create Ticket": {"main": [_to(("Ticket OK?", 0))]},
        "Ticket OK?": {"main": [_to(("Merge", 0)), _to(("Wait", 0))]},
        "Wait": {"main": [_to(("Create Ticket", 0))]},
        "Merge": {"main": [_to(("Notify Slack", 0), ("Legacy Email", 0))]},
        "Notify Slack": {"main": [None]},
    },
}


@pytest.fixture
def wf():
    return load(copy.deepcopy(FIXTURE))


def test_load_accepts_dict_and_json_string_and_keeps_extra_fields(wf):
    assert load(json.dumps(FIXTURE)).model_dump() == wf.model_dump()
    assert len(wf.nodes) == 13 and wf.nodes[0].webhookId == "wh-1"
    assert sum(e.kind == "main" for e in wf.edges) == 11      # the null slot adds no edge


def test_graph_keeps_control_flow_and_attachments_apart(wf):
    assert wf.forward()["Is Priority?"] == ["Fetch Customer", "Create Ticket"]
    assert wf.forward()["OpenAI Model"] == []                 # ai_* edges are not control flow
    assert wf.inverse()["Merge"] == ["Triage Agent", "Ticket OK?"]
    assert ("Wait", "Create Ticket") in wf.main_edges() and len(wf.main_edges()) == 11
    assert wf.attachments() == {"Triage Agent": [
        {"node": "OpenAI Model", "kind": "ai_languageModel", "type": LC + "lmChatOpenAi"},
        {"node": "Lookup Tool", "kind": "ai_tool", "type": LC + "toolHttpRequest"}]}


def test_duplicate_node_names_are_rejected():
    bad = copy.deepcopy(FIXTURE)
    bad["nodes"].append(_node("Merge", BASE + "noOp"))
    with pytest.raises(WorkflowError, match="duplicate node name: 'Merge'"):
        load(bad)


def test_dangling_target_and_unknown_source_are_rejected():
    bad = copy.deepcopy(FIXTURE)
    bad["connections"]["Merge"]["main"][0].append({"node": "Ghost", "type": "main", "index": 0})
    with pytest.raises(WorkflowError, match="missing node: 'Ghost'"):
        load(bad)
    bad = copy.deepcopy(FIXTURE)
    bad["connections"]["Ghost"] = {"main": [[]]}
    with pytest.raises(WorkflowError, match="source 'Ghost' is not a node"):
        load(bad)


def test_hostile_size_caps(monkeypatch):
    too_many = {"nodes": [_node(f"n{i}", BASE + "noOp") for i in range(workflow.MAX_NODES + 1)],
                "connections": {}}
    with pytest.raises(WorkflowError, match="too many nodes"):
        load(too_many)
    bad = copy.deepcopy(FIXTURE)
    bad["connections"]["Merge"]["main"][0][0]["index"] = workflow.MAX_INPUT_INDEX + 1
    with pytest.raises(WorkflowError, match="input index"):
        load(bad)
    monkeypatch.setattr(workflow, "MAX_SLOTS", 5)
    with pytest.raises(WorkflowError, match="too many connection slots"):
        load(copy.deepcopy(FIXTURE))


def test_malformed_input_is_a_workflow_error():
    for bad in ("{not json", "[]", {"nodes": "x"}, {"nodes": [{"name": "a"}]},
                {"nodes": [], "connections": []}):
        with pytest.raises(WorkflowError):
            load(bad)


def test_analyse_structure(wf):
    a = analyse(wf)
    json.dumps(a)                                              # plain JSON-serialisable
    assert a["triggers"] == [{"node": "Order Webhook", "kind": "webhook", "disabled": False}]
    assert a["execution_order"] == [
        "Order Webhook", "Is Priority?", "Fetch Customer", "Triage Agent", "Create Ticket",
        "Ticket OK?", "Wait", "Merge", "Notify Slack", "Legacy Email", "Orphan Sheet"]
    assert a["cycles"] == [["Create Ticket", "Ticket OK?", "Wait"]]      # reported, not rejected
    assert a["branch_points"] == [
        {"node": "Is Priority?", "outputs": [
            {"output": 0, "label": "true", "targets": ["Fetch Customer"]},
            {"output": 1, "label": "false", "targets": ["Create Ticket"]}]},
        {"node": "Ticket OK?", "outputs": [
            {"output": 0, "label": "true", "targets": ["Merge"]},
            {"output": 1, "label": "false", "targets": ["Wait"]}]}]
    assert a["merge_points"] == [
        {"node": "Create Ticket", "inputs": ["Is Priority?", "Wait"]},
        {"node": "Merge", "inputs": ["Triage Agent", "Ticket OK?"]}]
    assert a["unreachable"] == ["Orphan Sheet"]               # attached sub-nodes are reachable
    assert a["disabled"] == ["Legacy Email"]
    assert a["attachments"] == wf.attachments()


def test_analyse_error_handling_credentials_and_systems(wf):
    a = analyse(wf)
    handling = {h["node"]: h for h in a["error_handling"]}
    assert handling["Fetch Customer"] == {
        "node": "Fetch Customer", "on_error": "stopWorkflow", "retry": True, "max_tries": 3,
        "wait_between_tries_ms": 1000, "handled": True}
    assert handling["Notify Slack"]["on_error"] == "continueRegularOutput"
    assert handling["Notify Slack"]["handled"] and not handling["Create Ticket"]["handled"]
    assert a["error_workflow"] is False
    # external, enabled, and neither retried nor allowed to continue on error
    assert a["unhandled_external"] == ["OpenAI Model", "Lookup Tool", "Create Ticket", "Orphan Sheet"]
    assert a["credentials"] == [
        {"type": "httpHeaderAuth", "name": "CRM key", "nodes": ["Fetch Customer"]},
        {"type": "openAiApi", "name": "OpenAI prod", "nodes": ["OpenAI Model"]},
        {"type": "slackApi", "name": "Ops Slack", "nodes": ["Notify Slack"]},
        {"type": "smtp", "name": "Old SMTP", "nodes": ["Legacy Email"]}]
    assert a["external_systems"] == [
        {"system": "api.crm.example.com", "nodes": ["Fetch Customer"]},
        {"system": "desk.example.com", "nodes": ["Create Ticket"]},
        {"system": "emailsend", "nodes": ["Legacy Email"]},
        {"system": "googlesheets", "nodes": ["Orphan Sheet"]},
        {"system": "kb.example.com", "nodes": ["Lookup Tool"]},
        {"system": "openai", "nodes": ["OpenAI Model"]},
        {"system": "slack", "nodes": ["Notify Slack"]}]
    assert a["counts"] == {
        "nodes": 13, "steps": 11, "main_edges": 11, "attachment_edges": 2, "cycles": 1,
        "external_nodes": 7, "triggers": 1, "branch_points": 2, "merge_points": 2,
        "unreachable": 1, "disabled": 1, "unhandled_external": 4, "credentials": 4,
        "external_systems": 7}


def test_secret_looking_parameters_are_never_echoed(wf):
    out = json.dumps([analyse(wf), to_plan(wf), required_permissions(wf)])
    for secret in (URL_KEY, HEADER_KEY, SLACK_TOKEN):
        assert secret not in out
    slack = next(s for s in to_plan(wf) if s["node"] == "Notify Slack")
    assert slack["does"] == "slack: message post ([API_KEY])"       # summarised, then redacted
    assert "$json" not in out                                       # expressions are not echoed


def test_secret_in_a_node_name_fails_closed():
    data = {"nodes": [_node(f"call {URL_KEY}", BASE + "noOp")], "connections": {}}
    for fn in (analyse, to_plan):
        with pytest.raises(WorkflowError, match="secret-looking"):
            fn(load(data))


def test_to_plan_order_inputs_and_branches(wf):
    plan = to_plan(wf)
    assert [s["step"] for s in plan] == list(range(1, 12))
    assert [s["node"] for s in plan] == analyse(wf)["execution_order"]
    by = {s["node"]: s for s in plan}
    assert by["Order Webhook"]["does"] == "starts when a webhook is called (/orders)"
    assert by["Order Webhook"]["inputs"] == []
    assert by["Is Priority?"]["does"] == "branches on a condition"
    assert by["Is Priority?"]["branches"] == [{"label": "true", "to": [3]}, {"label": "false", "to": [5]}]
    assert by["Fetch Customer"]["does"] == "calls GET api.crm.example.com"
    assert by["Create Ticket"]["does"] == "calls POST desk.example.com"
    assert by["Create Ticket"]["inputs"] == [2, 7]                   # the branch and the loop back
    assert by["Triage Agent"]["does"] == "runs an AI agent"
    assert by["Triage Agent"]["uses"] == ["OpenAI Model (ai_languageModel)", "Lookup Tool (ai_tool)"]
    assert by["Merge"]["inputs"] == [4, 6] and by["Merge"]["next"] == [9, 10]
    assert by["Legacy Email"]["does"].startswith("(disabled) ")
    assert to_plan(wf) == plan                                       # deterministic


def test_required_permissions(wf):
    perms = {p["node"]: p for p in required_permissions(wf)}
    assert set(perms) == {"Fetch Customer", "OpenAI Model", "Lookup Tool", "Create Ticket",
                          "Notify Slack", "Legacy Email", "Orphan Sheet"}
    assert perms["Fetch Customer"] == {
        "node": "Fetch Customer", "system": "api.crm.example.com", "operation": "read",
        "credential": {"type": "httpHeaderAuth", "name": "CRM key"}, "disabled": False}
    assert perms["Create Ticket"]["operation"] == "write"            # POST
    assert perms["Create Ticket"]["credential"] is None
    assert perms["Notify Slack"]["operation"] == "send"
    assert perms["Orphan Sheet"]["operation"] == "execute"           # unknown operation
    assert perms["Lookup Tool"]["operation"] == "execute"            # no method given
    assert perms["OpenAI Model"]["operation"] == "execute"
    assert perms["Legacy Email"]["disabled"] is True


def test_operation_inference_and_dynamic_urls():
    def perm(type_, **parameters):
        return required_permissions(load({"nodes": [_node("n", BASE + type_, parameters=parameters)]}))[0]

    assert perm("httpRequest", method="DELETE", url="https://a.example/x")["operation"] == "delete"
    dynamic = perm("httpRequest", method="={{ $json.m }}", url="={{ $json.url }}")
    assert (dynamic["system"], dynamic["operation"]) == ("http", "execute")
    # HTTP Request with no method key: n8n omits defaults from the export, and the default is GET.
    assert perm("httpRequest", url="https://a.example/x")["operation"] == "read"
    assert perm("httpRequest", url="https://a.example/x", requestMethod="POST")["operation"] == "write"
    assert perm("httpRequest", url="https://a.example/x", requestMethod="GET")["operation"] == "read"
    # Present but not a recognised literal: still fails closed.
    for method in ("", "PURGE", None, {"a": 1}, "={{ $json.m }}"):
        assert perm("httpRequest", url="https://a.example/x", method=method)["operation"] == "execute"
    assert perm("httpRequest", url="https://a.example/x", method="", requestMethod="GET")["operation"] == "execute"
    # The GET default belongs to the HTTP Request node only, not to look-alike tool nodes.
    assert required_permissions(load({"nodes": [_node("t", LC + "toolHttpRequest", parameters={
        "url": "https://a.example/x"})]}))[0]["operation"] == "execute"
    assert perm("postgres", operation="select")["operation"] == "read"
    assert perm("postgres", operation="executeQuery")["operation"] == "execute"
    assert perm("airtable", operation="deleteRecord")["operation"] == "delete"
    assert perm("gmailTrigger") == {"node": "n", "system": "gmail", "operation": "read",
                                    "credential": None, "disabled": False}


def test_error_output_label_disabled_trigger_and_self_loop():
    data = {"nodes": [_node("Cron", BASE + "scheduleTrigger", disabled=True),
                      _node("Manual", BASE + "manualTrigger"),
                      _node("Call", BASE + "httpRequest", onError="continueErrorOutput"),
                      _node("Ok", BASE + "noOp"), _node("Failed", BASE + "noOp"),
                      _node("Note", BASE + "stickyNote")],
            "connections": {"Manual": {"main": [_to(("Call", 0))]},
                            "Call": {"main": [_to(("Ok", 0)), _to(("Failed", 0))]},
                            "Ok": {"main": [_to(("Ok", 0))]}}}
    a = analyse(load(data))
    assert a["triggers"] == [{"node": "Cron", "kind": "schedule", "disabled": True},
                             {"node": "Manual", "kind": "manual", "disabled": False}]
    assert [o["label"] for o in a["branch_points"][0]["outputs"]] == ["output 0", "error"]
    assert a["cycles"] == [["Ok"]]
    assert a["unreachable"] == ["Cron"]                       # a disabled trigger starts nothing
    assert a["unhandled_external"] == [] and "Note" not in a["execution_order"]


def test_http_request_without_method_is_described_as_get():
    wf = load({"nodes": [_node("Read", BASE + "httpRequest", parameters={"url": "https://a.example/x"}),
                         _node("Dyn", BASE + "httpRequest", parameters={"method": "={{ $json.m }}",
                                                                        "url": "https://a.example/x"})]})
    described = {s["node"]: s["does"] for s in to_plan(wf)}
    assert described["Read"] == "calls GET a.example"
    assert described["Dyn"] == "calls an unspecified method on a.example"
