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
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from velaris.intel import guard, trace
from velaris.intel.llm import LLM, LLMError, extract_json
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

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def call_hash(tool: str, args: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps([tool, args], sort_keys=True, default=str).encode()).hexdigest()


def _hash(prev: str, run_id: str, seq: int, ts: float, kind: str, body: str) -> str:
    return hashlib.sha256(json.dumps([prev, run_id, seq, ts, kind, body]).encode()).hexdigest()


class Flow:
    def __init__(self, tools: Sequence[Tool], *, llm: Optional[LLM] = None, model: Optional[str] = None,
                 instructions: str = "", permit: Optional[Callable[[str, Dict[str, Any]], str]] = None,
                 max_turns: int = 12, path: Optional[str] = None) -> None:
        self.tools = {t.name: t for t in tools}
        self.llm, self.model, self.instructions = llm or LLM(), model, instructions
        self.permit, self.max_turns = permit, max_turns
        self._db = sqlite3.connect(path or str(data_dir() / "flow.db"), check_same_thread=False)
        self._db.executescript(_SCHEMA)

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
        if kind in ("start", "decision", "final", "stop") or body.get("verdict") == "approve":
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
        try:
            reply = self.llm.complete(self._prompt(events), model=self.model, max_tokens=800, temperature=0.0,
                                      purpose="flow.step").text
        except LLMError as e:      # not terminal: resume() asks the model again
            self._append(run_id, events, "model_error", {"error": str(e)[:200]})
            return
        try:
            step = extract_json(reply)
            if not isinstance(step, dict):
                raise LLMError("the reply must be one JSON object")
        except LLMError as e:
            self._append(run_id, events, "invalid", {"error": str(e), "reply": reply[:300]})
            return
        if isinstance(step.get("final"), str):
            self._append(run_id, events, "final", {"output": step["final"]})
            return
        name, args = step.get("tool"), step.get("args", {})
        tool = self.tools.get(name) if isinstance(name, str) else None
        if tool is None:
            self._append(run_id, events, "invalid", {"error": f"there is no tool named {name!r}"})
        elif not isinstance(args, dict) or set(args) - set(tool.params):
            self._append(run_id, events, "invalid", {"error": f"{name} takes only these arguments: "
                                                              f"{sorted(tool.params)}"})
        else:
            self._append(run_id, events, "call", {"tool": name, "args": args, "verdict": self._verdict(tool, args),
                                                  "call_hash": call_hash(name, args)})

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
                                                "flagged": flagged})

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
                return Result(run_id, "stopped", last["reason"], None, turns)
            call = next((e for e in reversed(events) if e["kind"] == "call"), None)
            if call and not any(e["kind"] == "result" and e["call_seq"] == call["seq"] for e in events):
                after = events[call["seq"] + 1:]
                started = next((e for e in reversed(after) if e["kind"] == "exec"), None)
                decision = next((e for e in reversed(after) if e["kind"] == "decision"), None)
                reason = ""
                if call["verdict"] == "deny":
                    self._append(run_id, events, "result", {"call_seq": call["seq"], "ok": False, "flagged": False,
                                                            "output": "not permitted by policy"})
                    continue
                if started and not self.tools[call["tool"]].idempotent and (
                        not decision or decision["seq"] < started["seq"]):
                    reason = "interrupted: this step had started when the run stopped and may already have happened"
                elif call["verdict"] == "approve" and not decision:
                    reason = "needs approval"
                if reason:
                    return Result(run_id, "waiting_approval", reason, {
                        "tool": call["tool"], "args": call["args"], "reason": reason,
                        "call_hash": call["call_hash"]}, turns)
                if decision and not decision["approve"]:
                    note = f": {decision['note']}" if decision["note"] else ""
                    self._append(run_id, events, "result", {
                        "call_seq": call["seq"], "ok": False, "flagged": False,
                        "output": f"rejected by {decision['by']}{note}"})
                    continue
                self._execute(run_id, events, call)
                continue
            if turns >= self.max_turns:
                self._append(run_id, events, "stop", {"reason": "out_of_turns"})
                continue
            self._propose(run_id, events)
            if events[-1]["kind"] == "model_error":
                return Result(run_id, "model_error", events[-1]["error"], None, turns)

    def start(self, task: str, *, actor: str = "") -> Result:
        run_id = uuid.uuid4().hex
        self._append(run_id, [], "start", {"task": task, "actor": actor, "tools": sorted(self.tools)})
        return self._advance(run_id)

    def resume(self, run_id: str) -> Result:
        """Carry on after a restart. Also the way to read a run's current status: it only
        moves a run that is free to move."""
        return self._advance(run_id)

    def decide(self, run_id: str, pending_call_hash: str, *, approve: bool, by: str, note: str = "") -> Result:
        """A person's answer to a waiting step. `pending_call_hash` must be the one they were shown."""
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
