"""COMPUTE_KERNEL: admission queue for compute jobs.

Not an operating-system kernel. It keeps a durable queue of declared jobs
(CPU cores, memory, priority) and decides which of them may run now:

    schedule(): take queued jobs by priority (highest first, then oldest) and
                admit each one that still fits in the free capacity; a job that
                does not fit is skipped, never split (first-fit by priority).

Capacity is the caller's declaration, or this machine's core count and available
memory when omitted. The kernel only decides and records; the caller runs the
admitted job and calls complete() to free its share.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from velaris.agentkit import infra_metrics
from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "COMPUTE_KERNEL"


class COMPUTE_KERNELAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def submit(self, job_id: str, cpu: float = 1.0, mem_mb: float = 256.0, priority: int = 0) -> Dict[str, Any]:
        if not is_name(job_id):
            return invalid("job_id must be a short name")
        if not is_number(cpu, 0.01, 4096) or not is_number(mem_mb, 1) or not is_number(priority, -1000, 1000):
            return invalid("cpu must be 0.01..4096, mem_mb >= 1 and priority -1000..1000")

        def add(data: Dict[str, Any]) -> Dict[str, Any]:
            jobs = data.setdefault("jobs", {})
            if job_id in jobs:
                return fail("duplicate", "a job with this id already exists", job=jobs[job_id])
            data["seq"] = data.get("seq", 0) + 1
            jobs[job_id] = {"id": job_id, "cpu": cpu, "mem_mb": mem_mb, "priority": priority,
                            "state": "queued", "seq": data["seq"], "submitted_at": time.time()}
            return ok(job=jobs[job_id])
        return self._state.update(add)

    def schedule(self, capacity: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Admit queued jobs into the free capacity. `capacity` is {"cpu": cores, "mem_mb": MB} in total."""
        if capacity is None:
            s = infra_metrics.sample()
            capacity = {"cpu": s["cpu_count"], "mem_mb": s["mem_available_mb"]}
        if not isinstance(capacity, dict) or not (is_number(capacity.get("cpu"), 0) and is_number(capacity.get("mem_mb"), 0)):
            return invalid("capacity must be {'cpu': cores, 'mem_mb': MB}, both >= 0")

        def run(data: Dict[str, Any]) -> Dict[str, Any]:
            jobs = data.get("jobs", {})
            running = [j for j in jobs.values() if j["state"] == "running"]
            free_cpu = capacity["cpu"] - sum(j["cpu"] for j in running)
            free_mem = capacity["mem_mb"] - sum(j["mem_mb"] for j in running)
            admitted, waiting = [], []
            for job in sorted((j for j in jobs.values() if j["state"] == "queued"),
                              key=lambda j: (-j["priority"], j["seq"])):
                if job["cpu"] <= free_cpu and job["mem_mb"] <= free_mem:
                    job["state"], job["started_at"] = "running", time.time()
                    free_cpu, free_mem = free_cpu - job["cpu"], free_mem - job["mem_mb"]
                    admitted.append(job["id"])
                else:
                    waiting.append(job["id"])
            return ok(admitted=admitted, waiting=waiting, free={"cpu": round(free_cpu, 4), "mem_mb": round(free_mem, 2)})
        return self._state.update(run)

    def complete(self, job_id: str, succeeded: bool = True) -> Dict[str, Any]:
        """Mark a running job finished, releasing its capacity."""
        def done(data: Dict[str, Any]) -> Dict[str, Any]:
            job = data.get("jobs", {}).get(job_id) if isinstance(job_id, str) else None
            if not job:
                return fail("unknown_job", "no such job")
            if job["state"] != "running":
                return fail("not_running", f"job is {job['state']}", job=job)
            job["state"], job["finished_at"] = ("done" if succeeded else "failed"), time.time()
            return ok(job=job)
        return self._state.update(done)

    def status(self) -> Dict[str, Any]:
        jobs = self._state.load().get("jobs", {})
        counts: Dict[str, int] = {}
        for j in jobs.values():
            counts[j["state"]] = counts.get(j["state"], 0) + 1
        return ok(counts=counts, jobs=sorted(jobs.values(), key=lambda j: j["seq"]))
