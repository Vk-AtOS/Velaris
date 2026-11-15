"""Semantic check of one agent's harness entry and eval set against the CODE (the test walks every manifest with this).

Beyond the structure (harness_spec): every exposed method exists and may be exposed; its kind agrees with the allowlist
where that has a rule and is never "read" where the code can change something; the sensitivity is not below what the
department and the code require; every other public method is accounted for in `excluded`; a not_harnessed reason is true
(stub / unreachable / no_methods are re-derived); the eval set exists and only names tools the agent exposes.
"""
from __future__ import annotations

from typing import Any, List

from velaris.agentkit.harness_derive import RANK, derived_kind, min_sensitivity, source_of, unreachable_reason
from velaris.agentkit.harness_spec import eval_path, load_json, manifest_path, validate_entry, validate_evalset
from velaris.agentkit.harness_tools import candidate_methods, public_methods
from velaris.agents.inventory import classify
from velaris.api.allowlist import METHODS, rule_for


def check_agent(agent: str, department: str, engine: Any) -> List[str]:
    mpath = manifest_path(department, agent)
    if not mpath.exists():
        return [f"{agent}: no manifest.json"]
    entry = load_json(mpath).get("harness")
    problems = validate_entry(agent, entry)
    if problems:
        return problems
    source = source_of(engine.router.get_agent(agent))
    if RANK[entry["sensitivity"]] < RANK[min_sensitivity(department, source)]:
        problems.append(f"{agent}: sensitivity {entry['sensitivity']} is below what {department}/the code require")
    tools = entry["tools"]
    if entry["status"] == "not_harnessed":
        code = entry["reason_code"]
        stub = classify(source) == "not_implemented" and agent not in METHODS
        if code == "stub" and not stub:
            problems.append(f"{agent}: reason_code stub, but the inventory does not call it a stub")
        if code == "unreachable" and not unreachable_reason(engine, agent):
            problems.append(f"{agent}: reason_code unreachable, but the engine can build it")
        if code == "no_methods" and (unreachable_reason(engine, agent) or any(not w for w in candidate_methods(
                agent, engine.agent_class(agent)).values())):
            problems.append(f"{agent}: reason_code no_methods, but the agent has methods a model can call")
    else:
        cls = engine.agent_class(agent)
        cands = candidate_methods(agent, cls)
        for m, meta in tools.items():
            if m not in cands or cands[m]:
                problems.append(f"{agent}.{m}: cannot be exposed ({cands.get(m, 'no such public method')})")
                continue
            rule = rule_for(agent, m)
            if rule and rule.kind != meta["kind"]:
                problems.append(f"{agent}.{m}: kind {meta['kind']} but the allowlist says {rule.kind}")
            elif not rule and meta["kind"] == "read" and derived_kind(agent, department, source, cls.__name__, m, getattr(cls, m)) != "read":
                problems.append(f"{agent}.{m}: declared read, but the code can change state, reach outside, or never checks who is asking")
        loose = sorted(set(public_methods(cls)) - set(tools) - set(entry.get("excluded", {})))
        if loose:
            problems.append(f"{agent}: public methods neither exposed nor excluded with a reason: {loose[:5]}")
    epath = eval_path(department, agent)
    if entry.get("eval") != f"evals/{department}/{agent}.json" or not epath.exists():
        return problems + [f"{agent}: eval set missing at evals/{department}/{agent}.json"]
    try:
        data = load_json(epath)
    except ValueError as e:
        return problems + [str(e)]
    return problems + validate_evalset(agent, data, sorted(tools), entry["status"])
