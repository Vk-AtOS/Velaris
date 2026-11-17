"""KAN-29/35: ONE ToolSpec and ONE derivation. The harness registers what it derives; the allowlist row is READ/ACT truth."""
from velaris.agentkit import harness_tools
from velaris.api.allowlist import METHODS, rule_for
from velaris.backend.engine import backend
from velaris.core.access import Caller
from velaris.intel import tools
from velaris.orchestration.base import DepartmentOrchestrator


def test_there_is_one_toolspec_class():
    assert harness_tools.ToolSpec is tools.ToolSpec
    assert not hasattr(harness_tools, "params_of") and not hasattr(harness_tools, "json_type")


def test_the_harness_walk_registers_every_exposed_method_and_agrees_with_the_allowlist():
    tools.clear()
    n = harness_tools.register_all(backend)
    specs = tools.list_tools()
    assert n == len(specs) > 218          # the harness adds methods the table lacks
    for s in specs:
        rule = rule_for(s.agent, s.method)
        assert s.allowlisted == (rule is not None)
        if rule:                                           # the table decides READ/ACT; a read never carries a side effect
            assert s.kind == rule.kind and (s.side_effects == "none") == (rule.kind == "read")
        elif s.kind == "act":
            assert s.side_effects != "none"
        assert s.params["type"] == "object" and s.params["additionalProperties"] is False
    # registering twice (allowlist walk, then harness walk) yields identical specs: no ToolError, no second derivation
    assert harness_tools.register_all(backend) == n
    assert all(tools.get(f"{a}.{m}").allowlisted for a, ms in METHODS.items() for m in ms if tools.get(f"{a}.{m}"))


def test_a_method_without_an_allowlist_row_is_never_offered_or_run_by_an_orchestrator():
    tools.clear()
    harness_tools.register_all(backend)
    loose = next(s for s in tools.list_tools() if not s.allowlisted and s.kind == "read")
    orch = DepartmentOrchestrator(loose.department, scope="x", engine=backend)
    assert loose.name not in [s.name for s in orch.offered(Caller("u", "o", frozenset({"hr_admin", "payroll_admin"})))]
    try:
        tools.runner(backend, loose, Caller("u", "o"))
    except tools.ToolError:
        return
    raise AssertionError("runner accepted a tool with no allowlist row")


def test_a_manifest_never_lowers_a_registry_sensitivity():
    """Security review: an allowlisted spec is restricted unless on the reviewed list; a harness-only spec may take the
    manifest level but never below the department/code floor."""
    tools.clear()
    harness_tools.register_all(backend)
    for s in tools.list_tools():
        if s.allowlisted:
            assert s.sensitivity == tools.AGENT_SENSITIVITY.get(s.agent, "restricted"), s.name
        elif s.department in ("hr", "finance", "legal_compliance", "security"):
            assert s.sensitivity == "restricted", s.name
        else:
            assert tools.LEVEL_RANK[s.sensitivity] >= tools.LEVEL_RANK["internal"], s.name
    # a manifest that says "internal" for an HR agent still registers restricted
    hr = next(s for s in tools.list_tools() if s.department == "hr")
    tools._manifest_level.cache_clear()
    orig = tools._manifest_level
    tools._manifest_level = lambda agent, department: "internal"
    try:
        fn = getattr(backend.agent_class(hr.agent), hr.method)
        assert tools.sensitivity_of(hr.agent, "hr", fn, allowlisted=False) == "restricted"
        assert tools.sensitivity_of("LEAVE_MANAGEMENT", "hr", fn, allowlisted=True) == "restricted"
        assert tools.sensitivity_of("X", "operations", fn, allowlisted=True) == "restricted"      # allowlisted ignores the manifest
    finally:
        tools._manifest_level = orig
