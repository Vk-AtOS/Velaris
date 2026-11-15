"""Agent runs that can stop for a person and survive a restart.

A run is a task, a set of tools and a model. Each turn the model proposes one
step as JSON; code decides what happens to it:

  allow     the tool runs
  approve   the run stops with status "waiting_approval" until decide() is called
  deny      the tool does not run and the model is told so

The verdict comes from `permit(tool, args)` (default: the tool's own
`needs_approval`, which is True unless stated otherwise). Anything unclear -
an exception, an unknown answer - means "approve". The model cannot widen it.

Everything a run does is one row in an append-only, hash-chained event table,
and the run's state is nothing but those rows. So:

  - a paused run needs no live process; decide() can come days later, from
    another process
  - a finished tool call is never repeated on resume
  - a tool that had started when the process died is not blindly re-run: unless
    the tool is marked idempotent, the run waits for a person to say "run it
    again" (it may already have happened)
  - an approval names the exact call it approves (hash of tool + arguments)
  - two processes advancing one run cannot both win (the sequence number is unique)

  flow = Flow([Tool("pay", pay, "Pay a vendor", {"vendor": "name", "amount": "rupees"})])
  r = flow.start("Pay Acme 40,000")        # r.status == "waiting_approval", r.pending shows the call
  r = flow.decide(r.run_id, r.pending["call_hash"], approve=True, by="finance.head")

Approvals made elsewhere (a `gate`)
-----------------------------------
With `gate=` set, a waiting step is not decided through decide() (it refuses) but by
an outside approver such as AetherOS Prime (velaris.core.prime.PrimeGate). The gate
has two methods:

  submit(run_id, pending, meta) -> record     ask once; the record is kept as a "gate" event
  check(record) -> record                      ask again later, on every resume()

A record is {"state": "pending" | "approved" | "rejected", "call_hash", "decided_by",
"note", ...}. Only a record whose call_hash is the waiting call's own becomes a
decision; anything else, an exception, or an unreachable approver leaves the step
waiting. It never runs. A step interrupted mid-run is asked about afresh.

call(tool, args) starts a run of exactly one step chosen by code, not by a model:
the same verdict, approval and record, then the tool's output as the final answer.

Limits and escalation (KAN-30)
------------------------------
Before every model turn code checks, from the event rows alone (so they hold across a restart and a
resume): turns (`max_turns`), model spend (`max_cost`, summed `cost` of the turns, priced by `meter`),
active seconds (`max_seconds`, model time plus tool time, NOT the days a run waits for an approval), the
same call proposed `max_repeat` times (loop), `max_invalid` unusable replies in a row, and `max_model_errors`
model failures (these last three are off at 0, the default, so existing callers behave as before; the
orchestrators in velaris.orchestration turn them on). A model call the sensitivity policy or the budget refuses stops the run at once. Each of
these ends the run as `stop` with a reason and calls `escalate(info)` once (to the brain or a person); the
Result carries what was escalated. The limits never touch a call that is already waiting or approved.

With `route=` (a task class of velaris.intel.router) the model call goes through the fallback chain; every
call carries `sensitivity` (None means restricted, see velaris.intel.policy).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from velaris.core.sqlite_util import connect as connect_db
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from velaris.intel import catalogue, guard, router, trace, usage
from velaris.intel.errors import BudgetExceeded, PolicyRefused
from velaris.intel.llm import LLM, Completion, LLMError, extract_json

logger = logging.getLogger("velaris.intel.flow")
from velaris.intel.paths import data_dir

GENESIS = "0" * 64
MAX_OUTPUT_CHARS = 4000       # how much of a tool's output is kept and shown to the model
TERMINAL = ("final", "stop")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL, seq INTEGER NOT NULL, ts REAL NOT NULL, kind TEXT NOT NULL,
    body TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""


class FlowError(RuntimeError):
    pass


@dataclass
class Tool:
    name: str
    fn: Callable[..., Any]
    description: str
    params: Dict[str, str] = field(default_factory=dict)          # argument name -> what it is
    needs_approval: Union[bool, Callable[[Dict[str, Any]], bool]] = True
    idempotent: bool = False     # safe to run twice (a read, or a write keyed by its arguments)


@dataclass
class Result:
    run_id: str
    status: str                  # done | waiting_approval | stopped | model_error (resume() retries)
    output: str = ""             # the final answer, or why the run stopped
    pending: Optional[Dict[str, Any]] = None   # {tool, args, reason, call_hash} when waiting
    turns: int = 0
    escalation: Optional[Dict[str, Any]] = None    # set when the run stopped and was handed on (see escalate=)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def call_hash(tool: str, args: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps([tool, args], sort_keys=True, default=str).encode()).hexdigest()


def _hash(prev: str, run_id: str, seq: int, ts: float, kind: str, body: str) -> str:
    return hashlib.sha256(json.dumps([prev, run_id, seq, ts, kind, body]).encode()).hexdigest()


def model_cost(prompt: str, out: Completion) -> float:
    """USD of one model turn, estimated from sizes and the catalogue price (0.0 when the price is unknown: the
    gateway itself refuses unpriced models while an organisation has a USD budget)."""
    cost = catalogue.cost_estimate(out.model, usage.estimate_tokens(len(prompt)), usage.estimate_tokens(len(out.text)))
    return float(cost or 0.0)


_local = threading.local()


def _connection(path: str) -> sqlite3.Connection:
    """One sqlite connection per (thread, file), reused by every Flow built on that thread: the API builds a
    Flow per request, and opening + running the schema each time was the cost. A thread uses it sequentially."""
    conns = _local.__dict__.setdefault("conns", {})
    c = conns.get(path)
    if c is None:
        c = conns[path] = connect_db(path, timeout=10, check_same_thread=False)
        c.executescript(_SCHEMA)
    return c


class Flow:
    def __init__(self, tools: Sequence[Tool], *, llm: Optional[LLM] = None, model: Optional[str] = None,
                 instructions: str = "", permit: Optional[Callable[[str, Dict[str, Any]], str]] = None,
                 max_turns: int = 12, path: Optional[str] = None, gate: Any = None, max_cost: Optional[float] = None,
                 max_seconds: Optional[float] = None, max_repeat: int = 0, max_invalid: int = 0,
                 max_model_errors: int = 0, meter: Callable[[str, Completion], float] = model_cost,
                 escalate: Optional[Callable[[Dict[str, Any]], Any]] = None, route: Optional[str] = None,
                 models: Optional[List[str]] = None, sensitivity: Optional[str] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.tools = {t.name: t for t in tools}
        self.llm, self.model, self.instructions = llm or LLM(), model, instructions
        self.permit, self.max_turns, self.gate = permit, max_turns, gate
        self.max_cost, self.max_seconds, self.max_repeat = max_cost, max_seconds, max_repeat
        self.max_invalid, self.max_model_errors, self.meter, self.escalate = max_invalid, max_model_errors, meter, escalate
        self.route, self.models, self.sensitivity, self._clock = route, models, sensitivity, clock
        self._spent: Dict[str, Any] = {}          # cost and seconds of the model turn whose call is being appended
        self._db = _connection(path or str(data_dir() / "flow.db"))

    # ── the event log ────────────────────────────────────────────────────────
    def history(self, run_id: str) -> List[Dict[str, Any]]:
        rows = self._db.execute("SELECT seq, ts, kind, body, prev, hash FROM events WHERE run_id=? ORDER BY seq",
                                (run_id,)).fetchall()
        return [{"seq": s, "ts": ts, "kind": k, "prev": p, "hash": h, **json.loads(b)} for s, ts, k, b, p, h in rows]

    def _append(self, run_id: str, events: List[Dict[str, Any]], kind: str, body: Dict[str, Any]) -> Dict[str, Any]:
        seq, prev, ts = len(events), (events[-1]["hash"] if events else GENESIS), time.time()
        raw = json.dumps(body, sort_keys=True, default=str)
        h = _hash(prev, run_id, seq, ts, kind, raw)
        try:
            with self._db:
                self._db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)", (run_id, seq, ts, kind, raw, prev, h))
        except sqlite3.IntegrityError as e:
            raise FlowError(f"run {run_id} is being advanced by another process") from e
        event = {"seq": seq, "ts": ts, "kind": kind, "prev": prev, "hash": h, **json.loads(raw)}
        events.append(event)
        if kind in ("start", "decision", "final", "stop", "gate") or body.get("verdict") == "approve":
            # anchor the moments that matter in the global trace, so cutting the tail off a run is detectable
            trace.append("flow", kind, {"run_id": run_id, "seq": seq, "event_hash": h,
                                        **{k: body[k] for k in ("tool", "verdict", "approve", "by", "call_hash",
                                                                "reason") if k in body}})
        return event

    def verify(self, run_id: str) -> Dict[str, Any]:
        """Recompute the run's hash chain. Returns {"ok", "events", "broken_at"}."""
        rows = self._db.execute("SELECT seq, ts, kind, body, prev, hash FROM events WHERE run_id=? ORDER BY seq",
                                (run_id,)).fetchall()
        prev = GENESIS
        for i, (seq, ts, kind, body, p, h) in enumerate(rows):
            if seq != i or p != prev or h != _hash(prev, run_id, seq, ts, kind, body):
                return {"ok": False, "events": len(rows), "broken_at": i}
            prev = h
        return {"ok": True, "events": len(rows), "broken_at": None}

    # ── deciding what a proposed step may do ─────────────────────────────────
    def _verdict(self, tool: Tool, args: Dict[str, Any]) -> str:
        try:
            if self.permit:
                v = self.permit(tool.name, args)
                return v if v in ("allow", "deny", "approve") else "approve"
            need = tool.needs_approval
            return "approve" if (need(args) if callable(need) else need) else "allow"
        except Exception as e:  # a broken rule must never become a silent "allow"
            trace.append("flow", "permit.error", {"tool": tool.name, "error": type(e).__name__})
            return "approve"

    def _propose(self, run_id: str, events: List[Dict[str, Any]]) -> None:
        """One model turn: append `final`, `call` (with the code's verdict) or `invalid`."""
        prompt, started = self._prompt(events), self._clock()
        try:
            if self.route:
                out = router.complete(self.route, prompt, llm=self.llm, sensitivity=self.sensitivity, models=self.models,
                                      max_tokens=800, temperature=0.0, purpose="flow.step")
            else:
                out = self.llm.complete(prompt, model=self.model, max_tokens=800, temperature=0.0, purpose="flow.step",
                                        sensitivity=self.sensitivity)
        except (PolicyRefused, BudgetExceeded) as e:      # asking again cannot change this: stop and hand it on
            return self._stop(run_id, events, "budget_exceeded" if isinstance(e, BudgetExceeded) else "policy_refused")
        except LLMError as e:      # not terminal: resume() asks the model again (up to max_model_errors)
            self._append(run_id, events, "model_error", {"error": str(e)[:200], "sec": self._clock() - started})
            return
        reply = out.text
        spent = {"cost": self.meter(prompt, out), "sec": self._clock() - started}
        try:
            step = extract_json(reply)
            if not isinstance(step, dict):
                raise LLMError("the reply must be one JSON object")
        except LLMError as e:
            self._append(run_id, events, "invalid", {"error": str(e), "reply": reply[:300], **spent})
            return
        if isinstance(step.get("final"), str):
            self._append(run_id, events, "final", {"output": step["final"], **spent})
            return
        name, args = step.get("tool"), step.get("args", {})
        tool = self.tools.get(name) if isinstance(name, str) else None
        if tool is None:
            self._append(run_id, events, "invalid", {"error": f"there is no tool named {name!r}", **spent})
        elif not isinstance(args, dict) or set(args) - set(tool.params):
            self._append(run_id, events, "invalid", {"error": f"{name} takes only these arguments: "
                                                              f"{sorted(tool.params)}", **spent})
        else:
            self._spent = spent
            self._append_call(run_id, events, tool, args)

    def _append_call(self, run_id: str, events: List[Dict[str, Any]], tool: Tool, args: Dict[str, Any]) -> None:
        h = call_hash(tool.name, args)
        if self.max_repeat and sum(e["kind"] == "call" and e["call_hash"] == h for e in events) >= self.max_repeat - 1:
            return self._stop(run_id, events, "loop_detected")      # the same step again and again: the model is stuck
        spent, self._spent = self._spent, {}
        self._append(run_id, events, "call", {"tool": tool.name, "args": args, "verdict": self._verdict(tool, args),
                                              "call_hash": h, **spent})

    def _stop(self, run_id: str, events: List[Dict[str, Any]], reason: str) -> None:
        """End the run and hand it on once: `escalate(info)` is called, and what happened is part of the stop event."""
        info: Dict[str, Any] = {"run_id": run_id, "reason": reason, "task": events[0].get("task", ""),
                                "meta": events[0].get("meta") or {}, "step": len(events)}
        handled = False
        if self.escalate is not None:
            try:
                self.escalate(info)
                handled = True
            except Exception as e:  # a failing escalation is recorded, never hidden and never a crash of the run
                logger.warning("escalating run %s failed: %s", run_id, type(e).__name__)
        self._append(run_id, events, "stop", {"reason": reason, "escalation": {"handed_on": handled}})

    def _limit(self, events: List[Dict[str, Any]]) -> str:
        """The reason the run may not ask the model again, or "" (computed from the events alone)."""
        if sum(e["kind"] in ("call", "invalid", "final") for e in events) >= self.max_turns:
            return "out_of_turns"
        if self.max_cost is not None and sum(e.get("cost", 0.0) for e in events) >= self.max_cost:
            return "cost_cap"
        if self.max_seconds is not None and sum(e.get("sec", 0.0) for e in events) >= self.max_seconds:
            return "time_cap"
        if self.max_model_errors and sum(e["kind"] == "model_error" for e in events) >= self.max_model_errors:
            return "model_unavailable"
        tail = 0
        for e in reversed(events):
            if e["kind"] != "invalid":
                break
            tail += 1
        return "too_many_invalid" if self.max_invalid and tail >= self.max_invalid else ""

    def _prompt(self, events: List[Dict[str, Any]]) -> str:
        tools = "\n".join(
            f"- {t.name}({', '.join(f'{k}: {v}' for k, v in t.params.items())}): {t.description}"
            for t in self.tools.values())
        lines = []
        for e in events[1:]:
            if e["kind"] == "call":
                lines.append(f"step {e['seq']}: you called {e['tool']} with {json.dumps(e['args'], default=str)}")
            elif e["kind"] == "result":
                lines.append(f"step {e['seq']}: {'result' if e['ok'] else 'NOT DONE'}: {e['output']}")
            elif e["kind"] == "invalid":
                lines.append(f"step {e['seq']}: your reply was rejected: {e['error']}")
        preamble, block = guard.wrap("\n".join(lines) or "(nothing yet)",
                                     label="the record of steps so far, including what the tools returned")
        return (f"{self.instructions}\n\nYou are carrying out a task one step at a time. You can act only through "
                f"these tools:\n{tools}\n\nTask: {events[0]['task']}\n\n{preamble}\n\n{block}\n\n"
                'Reply with JSON only. To take the next step: {"tool": "<name>", "args": {...}}. When the task is '
                'complete, or cannot be completed (say why): {"final": "<answer for the person who asked>"}. '
                "A step marked NOT DONE did not happen; do not claim it did.").strip()

    # ── running ──────────────────────────────────────────────────────────────
    def _execute(self, run_id: str, events: List[Dict[str, Any]], call: Dict[str, Any]) -> None:
        self._append(run_id, events, "exec", {"call_seq": call["seq"]})      # written BEFORE the side effect
        started = self._clock()
        try:
            out, ok = self.tools[call["tool"]].fn(**call["args"]), True
            out = out if isinstance(out, str) else json.dumps(out, default=str, ensure_ascii=False)
        except Exception as e:  # a tool failure is information for the model, not a crash of the run
            out, ok = f"{type(e).__name__}: {e}", False
        out = out[:MAX_OUTPUT_CHARS]
        flagged = guard.scan(out, source=f"flow.tool.{call['tool']}").blocked
        if flagged:
            out = "[the tool's output was withheld because it read like instructions, not data]"
        self._append(run_id, events, "result", {"call_seq": call["seq"], "ok": ok, "output": out,
                                                "flagged": flagged, "sec": self._clock() - started})

    def _advance(self, run_id: str) -> Result:
        events = self.history(run_id)
        if not events:
            raise FlowError(f"no run {run_id}")
        while True:
            last = events[-1]
            turns = sum(e["kind"] in ("call", "invalid", "final") for e in events)
            if last["kind"] == "final":
                return Result(run_id, "done", last["output"], None, turns)
            if last["kind"] == "stop":
                return Result(run_id, "stopped", last["reason"], None, turns, last.get("escalation"))
            call = next((e for e in reversed(events) if e["kind"] == "call"), None)
            if call and not any(e["kind"] == "result" and e["call_seq"] == call["seq"] for e in events):
                after = events[call["seq"] + 1:]
                started = next((e for e in reversed(after) if e["kind"] == "exec"), None)
                decision = next((e for e in reversed(after) if e["kind"] == "decision"), None)
                reason = ""
                if call["verdict"] == "deny" or call["tool"] not in self.tools:
                    self._append(run_id, events, "result", {
                        "call_seq": call["seq"], "ok": False, "flagged": False,
                        "output": "not permitted by policy" if call["verdict"] == "deny" else "tool no longer available"})
                    continue
                if started and not self.tools[call["tool"]].idempotent and (
                        not decision or decision["seq"] < started["seq"]):
                    reason = "interrupted: this step had started when the run stopped and may already have happened"
                elif call["verdict"] == "approve" and not decision:
                    reason = "needs approval"
                if reason:
                    pending = {"tool": call["tool"], "args": call["args"], "reason": reason,
                               "call_hash": call["call_hash"]}
                    if self.gate is not None:
                        decided, record = self._ask_gate(run_id, events, call, pending,
                                                         since=started["seq"] if started else call["seq"])
                        if decided:
                            continue
                        pending["approver"] = record
                    return Result(run_id, "waiting_approval", reason, pending, turns)
                if decision and not decision["approve"]:
                    note = f": {decision['note']}" if decision["note"] else ""
                    self._append(run_id, events, "result", {
                        "call_seq": call["seq"], "ok": False, "flagged": False,
                        "output": f"rejected by {decision['by']}{note}"})
                    continue
                self._execute(run_id, events, call)
                continue
            direct = events[0].get("direct")
            if direct:                       # a one-step run: the step was chosen by code, not by a model
                if call is None:
                    self._append_call(run_id, events, self.tools[direct["tool"]], direct["args"])
                else:
                    done = next(e for e in events if e["kind"] == "result" and e["call_seq"] == call["seq"])
                    self._append(run_id, events, "final", {"output": done["output"], "ok": done["ok"]})
                continue
            if (why := self._limit(events)):
                self._stop(run_id, events, why)
                continue
            self._propose(run_id, events)
            if events[-1]["kind"] == "model_error":
                if self._limit(events) == "model_unavailable":
                    self._stop(run_id, events, "model_unavailable")
                    continue
                return Result(run_id, "model_error", events[-1]["error"], None, turns)

    def _ask_gate(self, run_id: str, events: List[Dict[str, Any]], call: Dict[str, Any], pending: Dict[str, Any],
                  since: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Ask the outside approver about the waiting call. (True, record) once a decision is recorded."""
        asked = next((e for e in reversed(events) if e["kind"] == "gate" and e["seq"] > since), None)
        try:
            if asked is None:
                record = self.gate.submit(run_id, pending, events[0].get("meta") or {})
                self._append(run_id, events, "gate", {"call_seq": call["seq"], "call_hash": call["call_hash"],
                                                      "record": record})
            else:
                record = self.gate.check(asked["record"])
        except Exception as e:  # unreachable or unclear: the step waits, it never runs
            trace.append("flow", "gate.error", {"run_id": run_id, "call_hash": call["call_hash"],
                                                "error": type(e).__name__})
            return False, asked["record"] if asked else None
        if not isinstance(record, dict) or record.get("call_hash") != call["call_hash"] \
                or record.get("state") not in ("approved", "rejected"):
            return False, record if isinstance(record, dict) else None
        self._append(run_id, events, "decision", {
            "approve": record["state"] == "approved", "by": str(record.get("decided_by") or "gate"),
            "note": str(record.get("note") or "")[:500], "call_hash": call["call_hash"]})
        return True, record

    def start(self, task: str, *, actor: str = "", meta: Optional[Dict[str, Any]] = None) -> Result:
        """`meta` is kept with the run (and handed to a gate), e.g. who it runs for."""
        run_id = uuid.uuid4().hex
        body = {"task": task, "actor": actor, "tools": sorted(self.tools)}
        self._append(run_id, [], "start", {**body, "meta": meta} if meta else body)
        return self._advance(run_id)

    def call(self, tool: str, args: Dict[str, Any], *, actor: str = "",
             meta: Optional[Dict[str, Any]] = None) -> Result:
        """A run of exactly this one step. It is permitted, approved and recorded like any other."""
        t = self.tools.get(tool)
        if t is None or not isinstance(args, dict) or set(args) - set(t.params):
            raise FlowError(f"{tool!r} is not a tool here, or takes other arguments")
        run_id = uuid.uuid4().hex
        body = {"task": f"call {tool}", "actor": actor, "tools": [tool], "direct": {"tool": tool, "args": args}}
        self._append(run_id, [], "start", {**body, "meta": meta} if meta else body)
        return self._advance(run_id)

    def waiting(self, *, org: Optional[str] = None, owner: Optional[str] = None,
                limit: Optional[int] = None) -> List[str]:
        """Runs whose last event leaves them waiting for a decision (oldest first). Reads only.

        `org` / `owner` keep only runs whose start event names that caller organisation / user (meta.caller), and
        `limit` keeps the NEWEST that many AFTER that filter, so one person's runs are not crowded out by everyone
        else's."""
        where, args = ["e.kind IN ('call', 'exec', 'gate')"], []
        for key, value in (("org", org), ("id", owner)):
            if value is not None:
                where.append(f"json_extract(s.body, '$.meta.caller.{key}') = ?")
                args.append(value)
        rows = self._db.execute(
            "SELECT e.run_id, e.kind, e.body FROM events e JOIN (SELECT run_id, MAX(seq) AS m FROM events "
            "GROUP BY run_id) last ON e.run_id = last.run_id AND e.seq = last.m "
            "JOIN events s ON s.run_id = e.run_id AND s.seq = 0 "
            f"WHERE {' AND '.join(where)} ORDER BY e.ts", args).fetchall()
        runs = [r for r, kind, body in rows if kind != "call" or json.loads(body).get("verdict") == "approve"]
        return runs[-limit:] if limit else runs

    def resume(self, run_id: str) -> Result:
        """Carry on after a restart. Also the way to read a run's current status: it only
        moves a run that is free to move."""
        return self._advance(run_id)

    def decide(self, run_id: str, pending_call_hash: str, *, approve: bool, by: str, note: str = "") -> Result:
        """A person's answer to a waiting step. `pending_call_hash` must be the one they were shown."""
        if self.gate is not None:
            raise FlowError("decisions for this flow are made by its approver (gate), not here")
        if not by.strip():
            raise FlowError("a decision needs the name of the person who made it")
        state = self._advance(run_id)
        if state.status != "waiting_approval":
            raise FlowError(f"run {run_id} is not waiting for a decision (status: {state.status})")
        if state.pending["call_hash"] != pending_call_hash:  # type: ignore[index]
            raise FlowError("this decision is for a different step than the one now waiting")
        self._append(run_id, self.history(run_id), "decision", {
            "approve": bool(approve), "by": by.strip(), "note": note, "call_hash": pending_call_hash})
        return self._advance(run_id)
