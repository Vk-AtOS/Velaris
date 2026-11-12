"""LOCAL_AUTONOMY_CORE: can this node keep working with no outside help?

readiness() runs concrete checks on this machine and answers "autonomous" only
if all of them pass, otherwise "degraded" with the failing checks named:

  data_dir_writable   a file can be created and removed in the data directory
  disk_space          free space on that disk is at least min_free_disk_mb
  memory              available memory is at least min_free_mem_mb
  agents_present      every agent the caller lists has a main.py under departments/
  trace_intact        the hash-chained trace verifies

It only inspects; it repairs nothing.
"""
from __future__ import annotations

import os
import time
import uuid

from velaris import agents
from velaris.agentkit import infra_metrics, infra_store
from velaris.intel import paths, trace

_NAME = "LOCAL_AUTONOMY_CORE"
_started = time.time()


class LocalAutonomyCore:
    def __init__(self, name=_NAME):
        self.name = name

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def ping(self):
        return {"local": True, "status": "ok", "pid": os.getpid(), "uptime_s": round(time.time() - _started, 3)}

    @staticmethod
    def _writable():
        try:
            probe = paths.data_dir() / f".autonomy-probe-{uuid.uuid4().hex}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True, "data directory is writable"
        except OSError as e:
            return False, f"cannot write to the data directory: {e}"

    @staticmethod
    def _trace_ok():
        try:
            v = trace.verify()
        except (OSError, ValueError, KeyError) as e:
            return False, f"trace unreadable: {e}"
        return v["ok"], f"{v['entries']} entries" if v["ok"] else f"broken at entry {v['broken_at']}: {v['reason']}"

    def readiness(self, required_agents=None, min_free_disk_mb=200, min_free_mem_mb=256, sample=None):
        required = [] if required_agents is None else required_agents
        if not isinstance(required, list) or not all(infra_store.is_name(a) for a in required):
            return infra_store.invalid("required_agents must be a list of agent names", mode="degraded")
        if not infra_store.is_number(min_free_disk_mb, 0) or not infra_store.is_number(min_free_mem_mb, 0):
            return infra_store.invalid("minimums must be numbers >= 0", mode="degraded")
        s = infra_metrics.checked(sample)
        if s is None or not all(infra_store.is_number(s.get(k), 0) for k in ("disk_free_mb", "mem_available_mb")):
            return infra_store.invalid("sample needs numeric disk_free_mb and mem_available_mb", mode="degraded")
        present = {f.name for d in agents.department_dirs() for f in d.iterdir() if (f / "main.py").is_file()}
        missing = sorted(set(required) - present)
        checks = [
            ("data_dir_writable",) + self._writable(),
            ("disk_space", s["disk_free_mb"] >= min_free_disk_mb, f"{s['disk_free_mb']} MB free, {min_free_disk_mb} needed"),
            ("memory", s["mem_available_mb"] >= min_free_mem_mb, f"{s['mem_available_mb']} MB available, {min_free_mem_mb} needed"),
            ("agents_present", not missing, "all present" if not missing else "missing: " + ", ".join(missing)),
            ("trace_intact",) + self._trace_ok(),
        ]
        failed = [name for name, passed, _ in checks if not passed]
        return infra_store.ok(mode="degraded" if failed else "autonomous", failed=failed,
                              checks=[{"check": n, "passed": bool(p), "detail": d} for n, p, d in checks])
