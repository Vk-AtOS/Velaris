"""Runs, approvals, undo and kill for one deployment. Identity comes ONLY from the Caller.

  start(caller, task_id, params)    refuses unknown tasks, other organisations, bad parameters; builds the
                                    surface inside the caller's own workspace folder and runs the planner loop
  state / report / pending          read the run (owner, or a holder of an approver role in the same org)
  decide(caller, run, call_hash...) local approval: another person than the owner, holding an approver role,
                                    quoting the call hash they were shown; with a Prime gate, Prime decides
  undo / kill                       owner or approver; undo replays the journal's inverses newest first

Every row and trace entry carries the organisation. A run of another organisation is "not found".
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from velaris.control import audit as A
from velaris.control import report as R
from velaris.control import library, tasks  # noqa: F401  (library registers the seeded tasks)
from velaris.control.browser import BrowserSurface, PlaywrightDriver
from velaris.control.checkpoint import CheckpointStore, Journal, compensators
from velaris.control.core import ControlError, Refused, Surface
from velaris.control.files import DocSink, FilesSurface, resolve_in
from velaris.control.planner import ControlRun, Limits, set_kill
from velaris.control.terminal import Runner, TerminalSurface
from velaris.core.access import AccessDenied, Caller, org_denied
from velaris.intel import trace
from velaris.intel.flow import Flow, FlowError
from velaris.intel.llm import LLM
from velaris.intel.paths import data_dir, private_dir

APPROVER_ROLES = frozenset({"flow_approver"})
TERMINAL_STATES = ("succeeded", "failed_verification", "undone", "undone_partial")


class DocStoreSink:
    """The document library as a DocSink, scoped to one organisation. Opens the store on first use."""

    def __init__(self, scope: str, store: Any = None) -> None:
        self.scope, self._store = scope, store

    def _s(self) -> Any:
        if self._store is None:
            from velaris.intel.docs import DocStore
            self._store = DocStore()
        return self._store

    def ingest(self, name: str, data: bytes) -> Dict[str, Any]:
        return self._s().ingest(name, data, scope=self.scope, source="control")

    def remove(self, name: str) -> bool:
        return bool(self._s().remove(name, scope=self.scope, reason="control layer undo"))

    def documents(self) -> List[Dict[str, Any]]:
        return self._s().documents(self.scope)


_shared: "Optional[ControlService]" = None


def shared_service() -> "Optional[ControlService]":
    """The service the app mounted at /control, if any, so agents use the same llm, gate and runs."""
    return _shared


def set_shared_service(svc: "ControlService") -> None:
    global _shared
    _shared = svc


class ControlService:
    def __init__(self, *, store: Optional[CheckpointStore] = None, llm: Optional[LLM] = None, gate: Any = None,
                 workspace: Optional[Path] = None, runner: Optional[Runner] = None,
                 driver_factory: Optional[Callable[[], Any]] = None,
                 sink_factory: Optional[Callable[[Caller], DocSink]] = None,
                 resolver: Optional[Callable[[str], list]] = None, flow_path: Optional[str] = None,
                 limits: Optional[Limits] = None) -> None:
        self.store = store or CheckpointStore()
        self.llm, self.gate, self.runner, self.flow_path, self.limits = llm, gate, runner, flow_path, limits
        self.workspace = Path(workspace or os.environ.get("VELARIS_CONTROL_ROOT") or data_dir() / "control" / "workspace")
        self.driver_factory, self.resolver = driver_factory, resolver
        self.sink_factory = sink_factory or (lambda c: DocStoreSink(c.org))
        self._runs: Dict[str, ControlRun] = {}

    # ── building ─────────────────────────────────────────────────────────────
    def _org_root(self, org: str) -> Path:
        base = private_dir(self.workspace)
        if "/" in org or org in ("", ".", ".."):
            raise Refused("bad_org", "organisation names are plain")
        return private_dir(base / org).resolve()

    def _surface(self, task: tasks.Task, params: Dict[str, Any], caller: Caller, journal: Journal) -> Surface:
        root = self._org_root(caller.org)
        if task.surface == "files":
            return FilesSurface(resolve_in(root, params.get("folder", ".")) if params.get("folder", ".") != "." else root,
                                journal=journal, sink=self.sink_factory(caller))
        if task.surface == "terminal":
            return TerminalSurface(root, runner=self.runner, journal=journal)
        if task.surface == "browser":
            hosts = task.hosts(params) if task.hosts else []
            driver = self.driver_factory() if self.driver_factory else PlaywrightDriver(post_hosts=hosts, readback_url=params.get("readback_url", ""))
            return BrowserSurface(driver, hosts, journal=journal, resolver=self.resolver)
        raise Refused("unknown_surface", task.surface)

    def _guard_org(self, caller: Caller) -> None:
        why = org_denied(caller)
        if why:
            raise AccessDenied(why)

    def _build(self, task: tasks.Task, params: Dict[str, Any], caller: Caller, task_id: str,
               expected: Any = None) -> ControlRun:
        journal = Journal(self.store, task_id, caller.org)
        surface = self._surface(task, params, caller, journal)
        if expected is None:
            expected = task.expected(params, surface)
        return ControlRun(self.store, task, params, caller, surface, journal, expected, task_id=task_id,
                          llm=self.llm, gate=self.gate, flow_path=self.flow_path, limits=self.limits)

    # ── the operations ───────────────────────────────────────────────────────
    def tasks(self) -> List[Dict[str, Any]]:
        return tasks.listing()

    def start(self, caller: Caller, task_id: str, params: Any) -> Dict[str, Any]:
        self._guard_org(caller)
        task = tasks.get(task_id)                                        # LookupError: unknown tasks are refused
        try:
            clean = task.validate(params)
            task_run_id = uuid.uuid4().hex
            run = self._build(task, clean, caller, task_run_id)
        except ValueError as e:
            raise ControlError("bad_params", str(e)[:200]) from None
        trace.append("control", "run.requested", {"task_id": task_run_id, "org": caller.org, "actor": caller.id,
                                                  "task": task.id})
        self._runs[task_run_id] = run
        return run.start()

    def _row(self, caller: Caller, run_id: str) -> Dict[str, Any]:
        self._guard_org(caller)
        row = A.load_run(self.store, run_id, caller.org) if isinstance(run_id, str) and run_id.isalnum() else None
        if row is None or (row["owner"] != caller.id and not (caller.roles & APPROVER_ROLES)):
            raise LookupError("no such run")
        return row

    def _owner(self, caller: Caller, row: Dict[str, Any]) -> Caller:
        """The run's owner as it must act after a restart: the roles recorded when the run started (flow meta), capped by
        the owner's current roles when the owner is the one asking. No record means no roles (agent calls fail closed)."""
        roles: frozenset = frozenset()
        employee_id = None
        events = Flow([], llm=self.llm, path=self.flow_path).history(row["flow_run_id"]) if row["flow_run_id"] else []
        meta = (events[0].get("meta") or {}).get("caller") if events else None
        if isinstance(meta, dict) and meta.get("id") == row["owner"] and meta.get("org") == row["org"]:
            roles, employee_id = frozenset(meta.get("roles") or ()), meta.get("employee_id")
        if caller.id == row["owner"]:
            roles &= caller.roles
        return Caller(id=row["owner"], org=row["org"], roles=roles, employee_id=employee_id)

    def _run(self, caller: Caller, run_id: str) -> ControlRun:
        row = self._row(caller, run_id)
        run = self._runs.get(run_id)
        if run is None:
            task = tasks.get(row["task"])
            if task.surface == "browser":
                raise ControlError("session_lost", "this run's browser session ended; it can only be reported and undone")
            owner = self._owner(caller, row)
            run = self._build(task, row["params"], owner, run_id, expected=row["expected"])
            run.flow_run_id, run.active_s = row["flow_run_id"], float(row["active_s"])
            self._runs[run_id] = run
        return run

    def state(self, caller: Caller, run_id: str) -> Dict[str, Any]:
        row = self._row(caller, run_id)
        out: Dict[str, Any] = {"task_id": run_id, "task": row["task"], "status": row["status"], "owner": row["owner"],
                               "verification": row["verification"] or None}
        if row["status"] in ("waiting_approval", "model_error") and row["flow_run_id"]:
            try:
                out.update(self._run(caller, run_id).resume(row["flow_run_id"]))
            except ControlError as e:                     # e.g. the browser session ended: report what is recorded
                out["note"] = e.code
        steps = A.Audit(self.store, run_id, caller.org, row["owner"]).steps()
        out["observations"] = [{"snapshot_id": s["snapshot_id"], "elements": s["elements"]} for s in steps
                               if s["kind"] == "observation"][-5:]
        return out

    def report(self, caller: Caller, run_id: str) -> Dict[str, Any]:
        row = self._row(caller, run_id)
        flow = self._runs[run_id].flow if run_id in self._runs else Flow([], llm=self.llm, path=self.flow_path)
        return R.build(self.store, run_id, caller.org, flow)

    def pending(self, caller: Caller) -> List[Dict[str, Any]]:
        self._guard_org(caller)
        out = []
        for row in A.runs_of(self.store, caller.org, "waiting_approval"):
            if row["owner"] == caller.id or caller.roles & APPROVER_ROLES:
                out.append({"task_id": row["task_id"], "task": row["task"], "owner": row["owner"],
                            "pending": self.state(caller, row["task_id"]).get("pending")})
        return [o for o in out if o["pending"]]

    def decide(self, caller: Caller, run_id: str, call_hash: str, approve: bool, note: str = "") -> Dict[str, Any]:
        row = self._row(caller, run_id)
        if self.gate is not None:
            raise ControlError("decided_in_prime", "steps of this deployment are approved in AetherOS Prime")
        if not (caller.roles & APPROVER_ROLES):
            raise AccessDenied("only a named approver may decide a step")
        if approve and row["owner"] == caller.id:
            raise AccessDenied("a step must be approved by someone other than the person it runs for")
        try:
            return self._run(caller, run_id).decide(call_hash, bool(approve), caller.id, note)
        except FlowError:
            raise ControlError("not_waiting", "the run is not waiting for a decision on that step") from None

    def undo(self, caller: Caller, run_id: str) -> Dict[str, Any]:
        row = self._row(caller, run_id)
        run = self._runs.get(run_id)
        if run is None:                                               # a browser session may be gone: files/terminal rebuild
            try:
                run = self._run(caller, run_id)
            except ControlError:
                run = None
        handlers = {**compensators.handlers(), **(run.surface.undo_handlers() if run else {})}
        if run is not None and not run.killed():
            set_kill(self.store, run_id)                              # nothing may run on while it is being undone
        out = self.store.undo(run_id, caller.org, handlers)
        status = "undone" if not out["conflicts"] and not out["needs_human"] else "undone_partial"
        A.save_run(self.store, task_id=run_id, status=status)
        A.Audit(self.store, run_id, caller.org, caller.id).step("undo", {"undone": len(out["undone"]),
                                                                       "conflicts": len(out["conflicts"]),
                                                                       "needs_human": len(out["needs_human"]), "by": caller.id})
        return {**out, "status": status}

    def kill(self, caller: Caller, run_id: str) -> Dict[str, Any]:
        self._row(caller, run_id)
        set_kill(self.store, run_id)
        A.Audit(self.store, run_id, caller.org, caller.id).step("kill", {"by": caller.id})
        return {"task_id": run_id, "killed": True}
