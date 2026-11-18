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

from velaris.agentkit import checks, results, state
from velaris.agents.OFFLINE_SANDBOX import main as sandbox

_NAME = "OFFLINE_EXECUTION_ENGINE"
_MAX_JOURNAL = 500          # full records kept
_MAX_SEEN = 50_000           # ids remembered for at-most-once; ponytail: beyond this an old id could run again


class OfflineExecutionEngine:
    def __init__(self, name=_NAME):
        self.name = name
        self._state = state.JsonState(_NAME, "journal.json")
        self._sandbox = sandbox.OfflineSandbox()

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def execute(self, task: dict):
        if not isinstance(task, dict) or "argv" not in task:
            return results.invalid("task must be an object with an 'argv' list", executed=False)
        task_id = task.get("id", uuid.uuid4().hex)
        if not checks.is_name(task_id):
            return results.invalid("task id must be a short name", executed=False)
        def claim(data):
            """Reserve the id under the lock, so two workers cannot both run it; the lock is NOT held while it runs."""
            jobs, seen = data.setdefault("jobs", {}), data.setdefault("seen", {})
            if task_id in jobs:
                return {**jobs[task_id], "executed": False, "replayed": True}
            if task_id in seen:                      # claimed by someone else (running) or its record was trimmed
                return {**results.fail("in_progress_or_done", "this task id was already run or is running"),
                        "executed": False, "replayed": True}
            seen[task_id] = time.time()
            for old in sorted(seen, key=seen.get)[:max(0, len(seen) - _MAX_SEEN)]:
                del seen[old]
            return None
        replay = self._state.update(claim)
        if replay is not None:
            return replay
        result = self._sandbox.run(task["argv"], timeout_s=task.get("timeout_s", 5.0),
                                   files=task.get("files"), stdin=task.get("stdin", ""))
        if not result.get("ran"):
            # Refused (not allow-listed, bad arguments ...): nothing ran, so the id is released and a corrected retry
            # is a fresh request instead of replaying the old refusal.
            self._state.update(lambda data: data.setdefault("seen", {}).pop(task_id, None))
            return {**result, "id": task_id, "executed": False, "replayed": False}
        record = {"id": task_id, "finished_at": time.time(), "command": str(task["argv"][0])[:40]
                  if isinstance(task["argv"], list) and task["argv"] else "", **result}

        def finish(data):
            jobs = data.setdefault("jobs", {})
            jobs[task_id] = record
            for old in sorted(jobs, key=lambda j: jobs[j]["finished_at"])[:max(0, len(jobs) - _MAX_JOURNAL)]:
                del jobs[old]                        # the full record is trimmed; the id stays in "seen"
        self._state.update(finish)
        return {**record, "executed": True, "replayed": False}

    def get(self, task_id):
        job = self._state.load().get("jobs", {}).get(task_id) if isinstance(task_id, str) else None
        return job if job else results.fail("unknown_task", "no such task in the journal")

    def history(self, n=20):
        if not checks.is_number(n, 1) or isinstance(n, float):
            return []
        jobs = self._state.load().get("jobs", {})
        return sorted(jobs.values(), key=lambda j: j["finished_at"])[-n:]
