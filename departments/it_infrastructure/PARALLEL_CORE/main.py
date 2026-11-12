"""PARALLEL_CORE: run one function over many inputs on a bounded thread pool.

map() returns one record per input, in input order: {"ok": True, "value": ...}
or {"ok": False, "error": "..."} - one failing input never loses the others.
Threads suit I/O-bound work (model calls, files, HTTP); CPU-bound pure Python
gains nothing from them.

ponytail: a Python thread cannot be killed, so an input that outlives
`timeout_s` is reported as timed out while its thread runs on to completion in
the background. Use a subprocess (OFFLINE_SANDBOX) for work that must be stoppable.
"""
from __future__ import annotations

import concurrent.futures
import os
import time
from typing import Any, Callable, Dict, Optional, Sequence

from velaris.agentkit.infra_store import invalid, is_number, ok

NAME = "PARALLEL_CORE"
MAX_WORKERS = 32
MAX_ITEMS = 10000


class PARALLEL_COREAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def default_workers(self) -> int:
        return min(8, os.cpu_count() or 1)

    def map(self, fn: Callable[[Any], Any], items: Sequence[Any], workers: Optional[int] = None,
            timeout_s: Optional[float] = None) -> Dict[str, Any]:
        """Apply fn to each item concurrently; `timeout_s` bounds the whole call."""
        if not callable(fn):
            return invalid("fn must be callable")
        if not isinstance(items, (list, tuple)) or len(items) > MAX_ITEMS:
            return invalid(f"items must be a list of at most {MAX_ITEMS}")
        if workers is None:
            workers = self.default_workers()
        if not is_number(workers, 1, MAX_WORKERS) or isinstance(workers, float):
            return invalid(f"workers must be a whole number from 1 to {MAX_WORKERS}")
        if timeout_s is not None and not is_number(timeout_s, 0.001):
            return invalid("timeout_s must be a positive number")
        start = time.monotonic()
        deadline = None if timeout_s is None else start + timeout_s
        results = []
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="parallel-core")
        try:
            futures = [pool.submit(fn, item) for item in items]
            for future in futures:
                try:
                    left = None if deadline is None else max(0.0, deadline - time.monotonic())
                    results.append({"ok": True, "value": future.result(timeout=left)})
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    results.append({"ok": False, "error": "timed out"})
                except Exception as e:  # the callable is the caller's code: report its failure, keep going
                    results.append({"ok": False, "error": f"{type(e).__name__}: {e}"})
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        failed = sum(1 for r in results if not r["ok"])
        return {"status": "ok" if not failed else "partial", "results": results, "failed": failed,
                "workers": workers, "seconds": round(time.monotonic() - start, 4)}
