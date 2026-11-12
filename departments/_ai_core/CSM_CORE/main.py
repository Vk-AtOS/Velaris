"""CSM core: a register of numeric goals, reviewed with the other CSM agents.

set_goal() stores a target, the time allowed and optionally a policy
specification (compiled by CSM_POLICY). review() takes the current value and
time elapsed, gets the standing and posture from CSM_REASONER, checks an
optional record against the goal's policy, and lists what the goal is linked
to in CSM_LINKER. Each review is kept, so the trend of a goal can be read back.
State: <VELARIS_DATA>/agents/CSM_CORE/state.json.
"""
from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, ok
from velaris.agents.CSM_LINKER.main import CSMLinkerAgent
from velaris.agents.CSM_POLICY.main import CSMPolicyAgent
from velaris.agents.CSM_REASONER.main import CSMReasonerAgent
from velaris.intel.paths import agent_dir

NAME = "CSM_CORE"


class CSMCoreAgent:
    def __init__(self):
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"goals": {}})
        self.linker = CSMLinkerAgent()

    def health_check(self):
        return health(NAME)

    def set_goal(self, goal, target, total, start=0, policy=None, owner=None):
        if ident(goal) is None:
            return fail("invalid_input", "goal must be a non-empty name")
        probe = CSMReasonerAgent().quick_strategy({"current": start, "target": target, "elapsed": 0,
                                                   "total": total, "start": start})
        if probe["status"] != "ok":
            return fail("invalid_input", probe["reason"])
        compiled = None
        if policy is not None:
            compiled = CSMPolicyAgent().generate_policy(policy)
            if compiled["status"] != "ok":
                return fail("invalid_input", f"policy: {compiled['reason']}")
        record = {"target": target, "total": total, "start": start, "policy": compiled, "reviews": []}
        self._state.update(lambda data: data["goals"].update({goal: record}))
        if owner is not None:
            linked = self.linker.link(goal, owner, "owned_by")
            if not linked["linked"]:
                return fail("invalid_input", f"owner: {linked['reason']}")
        return ok(goal=goal, policy_version=compiled["version"] if compiled else None)

    def review(self, goal, current, elapsed, record=None):
        def change(data):
            spec = data["goals"].get(goal) if isinstance(goal, str) else None
            if spec is None:
                return fail("not_found", f"no goal named {goal!r}")
            standing = CSMReasonerAgent().quick_strategy({"current": current, "elapsed": elapsed,
                                                          **{k: spec[k] for k in ("target", "total", "start")}})
            if standing["status"] != "ok":
                return fail("invalid_input", standing["reason"])
            compliance = None
            if spec["policy"] is not None:
                compliance = CSMPolicyAgent().check(spec["policy"], record)   # no record: non-compliant
            spec["reviews"] = (spec["reviews"] + [{"elapsed": elapsed, "current": current,
                                                   "situation": standing["situation"]}])[-200:]
            needs_attention = standing["situation"] in ("off_track", "missed") or bool(
                compliance and not compliance["compliant"])
            return ok(goal=goal, **{k: standing[k] for k in ("strategy", "situation", "progress", "pace", "required_rate")},
                      compliance=compliance, needs_attention=needs_attention,
                      linked=self.linker.neighbours(goal), reviews=len(spec["reviews"]))
        return self._state.update(change)

    def goals(self):
        """{goal: latest situation or None} for every registered goal."""
        return {g: (spec["reviews"][-1]["situation"] if spec["reviews"] else None)
                for g, spec in sorted(self._state.load()["goals"].items())}
