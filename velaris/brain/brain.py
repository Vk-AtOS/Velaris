"""The central brain (KAN-32): goal -> departments -> orchestrators -> merged answer, or a question to a person.

  1. plan     the model (task class "planner", routed, with a sensitivity) turns the goal into steps
              {"id", "department", "goal", "depends_on"} or into questions for the person. Code validates the plan:
              known departments, at most MAX_STEPS, no cycle and no unknown dependency (agentkit.graph.order). One retry
              with the reason; then it asks the person which department. Names the model invents are dropped, never guessed.
  2. run      steps in dependency order, each by that department's orchestrator, as the caller. A step gets the
              outputs of its dependencies as fenced data. A step whose dependency did not finish is "blocked".
              A step that waits for approval pauses its branch only.
  3. merge    deterministic: each step's status and output, one overall status. No second model call.
  4. resume   `resume(run_id, caller)` moves a run on after an approval (waiting steps are re-read, then the steps that
              were blocked on them run).

Overall status: done | waiting_approval | needs_human (a step was refused or stopped and escalated) | question (the
brain needs an answer first) | failed. The brain never approves anything and never lowers a sensitivity; every
sensitive decision is the department's, in code. A model that is unavailable, refused or over budget does not stop
the system from answering: the brain says so and asks the person to name the department.

ponytail: steps of one level run one after another in this process; run them in threads when latency matters.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit.graph import order
from velaris.core.access import AccessDenied, Caller, org_denied
from velaris.intel import guard, router, trace
from velaris.intel.errors import LLMError
from velaris.intel.llm import LLM, extract_json
from velaris.orchestration.base import REFUSAL, DepartmentOrchestrator
from velaris.brain import memory

logger = logging.getLogger("velaris.brain")
MAX_STEPS, MAX_GOAL = 8, 4000
_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_-")


class PlanError(ValueError):
    """The model's plan is unusable; the message says why (and goes back to the model once)."""


def validate_plan(plan: Any, departments: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise PlanError('reply with {"steps": [...]} or {"questions": [...]}')
    steps = plan["steps"]
    if len(steps) > MAX_STEPS:
        raise PlanError(f"at most {MAX_STEPS} steps")
    out, ids = [], set()
    for s in steps:
        if not isinstance(s, dict):
            raise PlanError("each step is an object")
        sid, dept, goal, deps = s.get("id"), s.get("department"), s.get("goal"), s.get("depends_on", [])
        if not (isinstance(sid, str) and 0 < len(sid) <= 20 and set(sid) <= _ID_CHARS) or sid in ids:
            raise PlanError("step ids are unique lowercase words of at most 20 characters")
        if dept not in departments:
            raise PlanError(f"step {sid}: department must be one of {departments}")
        if not (isinstance(goal, str) and goal.strip()) or len(goal) > 1000:
            raise PlanError(f"step {sid}: goal is text of at most 1000 characters")
        if not (isinstance(deps, list) and all(isinstance(d, str) for d in deps)):
            raise PlanError(f"step {sid}: depends_on is a list of step ids")
        ids.add(sid)
        out.append({"id": sid, "department": dept, "goal": goal.strip(), "depends_on": list(deps), "status": "pending",
                    "run_id": "", "output": ""})
    graph = order({s["id"]: s["depends_on"] for s in out})
    if graph["missing"]:
        raise PlanError(f"unknown dependencies: {graph['missing']}")
    if graph["cycle"]:
        raise PlanError(f"the steps depend on each other: {graph['cycle']}")
    return out


class Brain:
    def __init__(self, orchestrators: Dict[str, DepartmentOrchestrator], *, llm: Optional[LLM] = None,
                 route: Optional[str] = "planner", models: Optional[List[str]] = None, sensitivity: str = "restricted",
                 flow_path: Optional[str] = None, wall: Callable[[], float] = time.time) -> None:
        self.orchestrators, self.llm, self.route, self.models = orchestrators, llm or LLM(), route, models
        self.sensitivity, self.flow_path, self._wall = sensitivity, flow_path, wall

    # ── planning ─────────────────────────────────────────────────────────────
    def _prompt(self, goal: str, caller: Caller, problem: str = "") -> str:
        depts = "\n".join(f"- {n}: {o.scope}" for n, o in sorted(self.orchestrators.items()))
        note, block = guard.wrap(f"Goal: {goal}\n\n{memory.context(caller, self.flow_path)}", label="the request and what is known")
        retry = f"\nYour last plan was refused: {problem}. Reply again.\n" if problem else ""
        return (f"You are the central planner of a company platform. Departments:\n{depts}\n\n{note}\n\n{block}\n{retry}\n"
                'Reply with JSON only. If the goal is clear: {"steps": [{"id": "s1", "department": "<name>", "goal": '
                '"<what that department must do>", "depends_on": []}]}. Use depends_on when a step needs another step '
                'done first. If it is unclear, or you cannot tell which department: {"questions": ["<question for '
                'the person>"]}. Never plan an action the request does not ask for.')

    def _ask(self, prompt: str) -> Any:
        kw = dict(llm=self.llm, sensitivity=self.sensitivity, models=self.models, max_tokens=1200, temperature=0.0,
                  purpose="brain.plan")
        text = router.complete(self.route, prompt, **kw).text if self.route else \
            self.llm.complete(prompt, max_tokens=1200, temperature=0.0, purpose="brain.plan", sensitivity=self.sensitivity).text
        return extract_json(text)

    def _plan(self, goal: str, caller: Caller) -> Dict[str, Any]:
        """{"steps": [...]} or {"questions": [...]}. A model that cannot be used becomes a question for the person."""
        names, problem = sorted(self.orchestrators), ""
        for _ in range(2):
            try:
                reply = self._ask(self._prompt(goal, caller, problem))
                if isinstance(reply, dict) and reply.get("questions"):
                    qs = [q.strip()[:300] for q in reply["questions"] if isinstance(q, str) and q.strip()][:3]
                    if qs:
                        return {"questions": qs}
                return {"steps": validate_plan(reply, names)}
            except PlanError as e:
                problem = str(e)
            except LLMError as e:       # includes: no usable model, policy refused, over budget, no JSON in the reply
                trace.append("brain", "plan.unavailable", {"org": caller.org, "error": type(e).__name__})
                return {"questions": [f"I could not plan this automatically ({type(e).__name__}). "
                                      f"Which department should take it: {', '.join(names)}?"]}
        return {"questions": [f"I could not make a valid plan ({problem}). Which department should take it: {', '.join(names)}?"]}

    # ── running ──────────────────────────────────────────────────────────────
    def handle(self, goal: str, caller: Caller) -> Dict[str, Any]:
        if (why := org_denied(caller)):
            raise AccessDenied(why)
        if not isinstance(goal, str) or not goal.strip() or len(goal) > MAX_GOAL:
            raise ValueError(f"a goal is text of 1 to {MAX_GOAL} characters")
        record: Dict[str, Any] = {"id": uuid.uuid4().hex, "org": caller.org, "caller": caller.id, "goal": goal.strip(),
                                  "created": self._wall(), "steps": [], "status": "planning", "questions": []}
        plan = self._plan(goal, caller)
        trace.append("brain", "plan", {"brain_run": record["id"], "org": caller.org, "caller": caller.id,
                                       "steps": [(s["id"], s["department"], s["depends_on"]) for s in plan.get("steps", [])],
                                       "questions": len(plan.get("questions", []))})
        if "questions" in plan:
            record.update(status="question", questions=plan["questions"])
        else:
            record["steps"] = plan["steps"]
            self._drive(record, caller)
        memory.save_run(record)
        return self._view(record)

    def resume(self, run_id: str, caller: Caller) -> Dict[str, Any]:
        record = memory.get_run(caller, run_id)
        if record is None:
            raise LookupError("no such run")
        if record["steps"]:
            self._drive(record, caller)
            memory.save_run(record)
        return self._view(record)

    def _drive(self, record: Dict[str, Any], caller: Caller) -> None:
        steps = {s["id"]: s for s in record["steps"]}
        for level in order({i: s["depends_on"] for i, s in steps.items()})["levels"]:
            for sid in level:
                s = steps[sid]
                deps = [steps[d] for d in s["depends_on"]]
                if s["status"] == "waiting_approval":
                    self._refresh(s, caller)
                elif s["status"] in ("pending", "blocked"):
                    if any(d["status"] != "done" for d in deps):
                        s["status"] = "blocked"
                        continue
                    self._start(s, deps, record, caller)
        record["status"] = self._overall(record["steps"])

    def _apply(self, s: Dict[str, Any], result: Any) -> None:
        s["run_id"], s["output"] = result.run_id, (result.output or "")[:2000]
        if result.status == "done":
            s["status"] = "refused" if s["output"].startswith(REFUSAL) else "done"
        elif result.status == "waiting_approval":
            s["status"], s["pending"] = "waiting_approval", {k: result.pending[k] for k in ("tool", "reason", "call_hash")}
        else:
            s["status"] = "stopped"          # stopped (escalated by the department) or model_error: a person must look
        if s["status"] != "waiting_approval":
            s.pop("pending", None)

    def _start(self, s: Dict[str, Any], deps: List[Dict[str, Any]], record: Dict[str, Any], caller: Caller) -> None:
        orch = self.orchestrators[s["department"]]
        context = "\n".join(f"[{d['department']}] {d['goal']}: {d['output']}" for d in deps)
        try:
            self._apply(s, orch.run(s["goal"], caller, brain_run=record["id"], context=context))
        except AccessDenied as e:
            s["status"], s["output"] = "refused", f"{REFUSAL} {e.reason}"
        except Exception as e:  # one department failing must not take the others down; the run says which and why
            logger.warning("department %s failed: %s", s["department"], type(e).__name__)
            s["status"], s["output"] = "stopped", f"the {s['department']} orchestrator failed ({type(e).__name__})"

    def _refresh(self, s: Dict[str, Any], caller: Caller) -> None:
        try:
            self._apply(s, self.orchestrators[s["department"]].resume(s["run_id"], caller))
        except Exception as e:  # unreadable right now: it stays waiting, nothing is guessed
            logger.warning("could not refresh %s run: %s", s["department"], type(e).__name__)

    @staticmethod
    def _overall(steps: List[Dict[str, Any]]) -> str:
        kinds = {s["status"] for s in steps}
        if kinds <= {"done"}:
            return "done"
        if kinds & {"refused", "stopped"}:
            return "needs_human"
        return "waiting_approval" if "waiting_approval" in kinds else "needs_human"

    @staticmethod
    def _view(r: Dict[str, Any]) -> Dict[str, Any]:
        answer = "\n".join(f"[{s['department']}] {s['status']}: {s['output']}" if s["output"] else
                           f"[{s['department']}] {s['status']}" for s in r["steps"])
        return {"brain_run": r["id"], "status": r["status"], "questions": r["questions"], "answer": answer,
                "steps": [{k: s.get(k) for k in ("id", "department", "status", "run_id", "depends_on", "pending")}
                          for s in r["steps"]]}
