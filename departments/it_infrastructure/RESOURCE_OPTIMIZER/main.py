"""RESOURCE_OPTIMIZER: how many parallel workers this machine can take right now.

profile() measures the host. recommend() turns a measurement into advice:

    by_cpu    = floor(cpu_count * (100 - cpu_percent) / 100)
    by_memory = floor((mem_available_mb - reserve_mb) / per_worker_mb)
    workers   = clamp(min(by_cpu, by_memory), 1, cpu_count)

plus findings when memory or disk is short. Advice only: nothing on the machine
is changed and no process is touched.
"""
from __future__ import annotations

import math

from velaris.agentkit import infra_metrics, infra_store

_NAME = "RESOURCE_OPTIMIZER"
_RESERVE_MB = 512        # memory left for the rest of the machine


class ResourceOptimizer:
    def __init__(self, name=_NAME):
        self.name = name

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def profile(self):
        """Current host measurement. "cpu" and "ram" are percentages in use."""
        s = infra_metrics.sample()
        return {"cpu": s["cpu_percent"], "ram": s["mem_percent"], **s}

    def recommend(self, sample=None, per_worker_mb=256):
        """Advised worker count for `sample` (measured when omitted) and any resource findings."""
        s = infra_metrics.checked(sample)
        needed = ("cpu_percent", "cpu_count", "mem_available_mb")
        if s is None or not all(infra_store.is_number(s.get(k), 0) for k in needed) or s["cpu_count"] < 1:
            return infra_store.invalid(f"sample needs numeric {', '.join(needed)}")
        if not infra_store.is_number(per_worker_mb, 1):
            return infra_store.invalid("per_worker_mb must be a number of at least 1")
        cores = int(s["cpu_count"])
        by_cpu = math.floor(cores * (100 - s["cpu_percent"]) / 100)
        by_memory = math.floor((s["mem_available_mb"] - _RESERVE_MB) / per_worker_mb)
        workers = max(1, min(by_cpu, by_memory, cores))
        findings = []
        if by_memory < 1:
            findings.append({"severity": "high", "issue": "memory",
                             "detail": f"only {s['mem_available_mb']} MB available; one worker at most"})
        if by_cpu < 1:
            findings.append({"severity": "medium", "issue": "cpu", "detail": f"CPU at {s['cpu_percent']}%"})
        if infra_store.is_number(s.get("disk_percent")) and s["disk_percent"] >= 90:
            findings.append({"severity": "high", "issue": "disk", "detail": f"disk {s['disk_percent']}% full"})
        return infra_store.ok(workers=workers, limited_by="memory" if by_memory < by_cpu else "cpu",
                              by_cpu=by_cpu, by_memory=by_memory, findings=findings)
