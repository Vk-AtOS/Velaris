"""OFFLINE_EXECUTION_ENGINE: a durable, replay-safe journal of local command runs.

execute(task) runs task["argv"] through OFFLINE_SANDBOX (allow-listed commands
only, no shell, temporary directory, scrubbed environment, timeout, capped
output) and writes the outcome to a journal on disk. A task that carries an
"id" runs at most once: asking again returns the recorded result instead of
running it a second time, so a retry after a crash or a lost reply is safe.

The containment is OFFLINE_SANDBOX's: process isolation, not a security sandbox.
"""
from __future__ import annotations

import time
import uuid

from velaris.agentkit import infra_store
from velaris.agents.OFFLINE_SANDBOX import main as sandbox

_NAME = "OFFLINE_EXECUTION_ENGINE"
_MAX_JOURNAL = 500


class OfflineExecutionEngine:
    def __init__(self, name=_NAME):
        self.name = name
        self._state = infra_store.State(_NAME, "journal.json")
        self._sandbox = sandbox.OfflineSandbox()

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def execute(self, task: dict):
        if not isinstance(task, dict) or "argv" not in task:
            return infra_store.invalid("task must be an object with an 'argv' list", executed=False)
        task_id = task.get("id", uuid.uuid4().hex)
        if not infra_store.is_name(task_id):
            return infra_store.invalid("task id must be a short name", executed=False)
        with self._state.lock:
            state = self._state.load()
            jobs = state.setdefault("jobs", {})
            if task_id in jobs:
                return {**jobs[task_id], "executed": False, "replayed": True}
            result = self._sandbox.run(task["argv"], timeout_s=task.get("timeout_s", 5.0),
                                       files=task.get("files"), stdin=task.get("stdin", ""))
            record = {"id": task_id, "finished_at": time.time(), "command": str(task["argv"][0])[:40]
                      if isinstance(task["argv"], list) and task["argv"] else "", **result}
            jobs[task_id] = record
            for old in sorted(jobs, key=lambda j: jobs[j]["finished_at"])[:max(0, len(jobs) - _MAX_JOURNAL)]:
                del jobs[old]
            self._state.save(state)
        return {**record, "executed": bool(result.get("ran")), "replayed": False}

    def get(self, task_id):
        job = self._state.load().get("jobs", {}).get(task_id) if isinstance(task_id, str) else None
        return job if job else infra_store.fail("unknown_task", "no such task in the journal")

    def history(self, n=20):
        if not infra_store.is_number(n, 1) or isinstance(n, float):
            return []
        jobs = self._state.load().get("jobs", {})
        return sorted(jobs.values(), key=lambda j: j["finished_at"])[-n:]
