"""The run report: what was asked, every step with its class, verdict, approver and result, what
verification found, what was changed and what can still be undone. Built from the run's audit
steps, the flow's hash-chained events and the journal. It holds hashes and counts for values and
outputs, never the contents of what was observed."""
from __future__ import annotations

from typing import Any, Dict, List

from velaris.control import audit as A
from velaris.control.checkpoint import CheckpointStore
from velaris.control.core import IRREVERSIBLE, READ


def build(store: CheckpointStore, task_id: str, org: str, flow: Any) -> Dict[str, Any]:
    row = A.load_run(store, task_id, org)
    if row is None:
        raise LookupError("no such run")
    steps = A.Audit(store, task_id, org, row["owner"]).steps()
    approvals = {s["call_hash"]: s for s in steps if s["kind"] == "approval"}
    history = flow.history(row["flow_run_id"]) if row["flow_run_id"] else []
    call_of = {e["seq"]: e["call_hash"] for e in history if e["kind"] == "call"}
    ok_of = {call_of.get(e["call_seq"]): e["ok"] for e in history if e["kind"] == "result"}
    actions = [{"n": s["n"], "action": s["action"], "ref": s["ref"], "snapshot_id": s["snapshot_id"], "class": s["class"],
                "verdict": s["verdict"], "reason": s["reason"], "call_hash": s["call_hash"],
                "approver": (approvals.get(s["call_hash"]) or {}).get("approver"),
                "approved": (approvals.get(s["call_hash"]) or {}).get("approve"),
                "result_ok": ok_of.get(s["call_hash"])} for s in steps if s["kind"] == "proposal"]
    ops = [o for o in store.ops(task_id, org) if o["klass"] != READ]
    return {
        "task_id": task_id, "task": row["task"], "org": org, "owner": row["owner"], "status": row["status"],
        "created": row["created"], "updated": row["updated"], "active_seconds": round(row["active_s"], 3),
        "actions": actions,
        "denied": [a for a in actions if a["verdict"] == "deny"],
        "approvals": [{"call_hash": h, "approver": s["approver"], "approve": s["approve"]} for h, s in approvals.items()],
        "observations": [s["snapshot_id"] for s in steps if s["kind"] == "observation"],
        "stops": [s["reason"] for s in steps if s["kind"] == "stop"],
        "verification": row["verification"] or None,
        "changes": [{"id": o["id"], "kind": o["kind"], "class": o["klass"], "undone": o["undone"]} for o in ops],
        "irreversible": [{"id": o["id"], "kind": o["kind"]} for o in ops if o["klass"] == IRREVERSIBLE],
        "flow_chain": flow.verify(row["flow_run_id"]) if row["flow_run_id"] else None,
    }


def render_text(r: Dict[str, Any]) -> str:
    v = r["verification"]
    out = [f"Run {r['task_id']}  task {r['task']}  org {r['org']}  by {r['owner']}",
           f"Status: {r['status']}   verified: {'yes' if v and v['ok'] else 'NO' if v else 'not run'}",
           f"Actions proposed: {len(r['actions'])}, refused by policy: {len(r['denied'])}"]
    for a in r["actions"]:
        who = f", approved by {a['approver']}" if a["approver"] and a["approved"] else (
            f", REJECTED by {a['approver']}" if a["approver"] else "")
        out.append(f"  #{a['n']} {a['action']} {a['ref']} [{a['class']}] {a['verdict']}{who}"
                   f"{'' if a['result_ok'] is None else ' -> ' + ('ok' if a['result_ok'] else 'failed')}: {a['reason']}")
    for c in (v or {}).get("checks", []):
        out.append(f"  verify: {'PASS' if c['ok'] else 'FAIL'} {c['name']} {c['detail']}".rstrip())
    if r["irreversible"]:
        out.append(f"Irreversible effects needing a person: {len(r['irreversible'])}")
    out.append(f"Changes journaled: {len(r['changes'])} (undone: {sum(c['undone'] for c in r['changes'])})")
    return "\n".join(out)
