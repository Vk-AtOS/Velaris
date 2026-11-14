"""Scheduled work for the API process (KAN-108): the mail outbox worker and the chat retention sweep.

Both used to run only when somebody called them by hand (python -m velaris.mail.outbound, POST /chat/admin/sweep), so
approved mail was never sent on its own and retention never ran. Each job here repeats every `interval` seconds
(VELARIS_MAIL_WORKER_S default 30, VELARIS_CHAT_SWEEP_S default 3600; 0 turns a job off) while the server is up.

Several worker processes can run this: a tick takes a non-blocking file lock first, so one process runs a job at a time
and the others skip that tick. Every tick does one bounded batch (process_due(limit), sweep's batch size) in a thread, so
the event loop is never blocked, and an exception is logged and the loop carries on.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import Any, AsyncIterator, Callable, List, Tuple

from velaris.core.filelock import FileLock
from velaris.intel.paths import data_dir

logger = logging.getLogger("velaris.api.background")
Job = Tuple[str, float, Callable[[], Any]]          # (name, interval seconds, function run in a thread)


def interval(env: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(env, default)))
    except ValueError:
        logger.warning("%s is not a number; using %s", env, default)
        return default


def run_once(name: str, fn: Callable[[], Any]) -> bool:
    """Run `fn` unless another process is running the job right now. True when it ran."""
    try:
        with FileLock(data_dir() / "shared" / f"job-{name}.lock", timeout=0):
            fn()
        return True
    except TimeoutError:
        return False
    except Exception as e:          # a failing job must not stop the loop or the server
        logger.warning("background job %s failed: %s: %s", name, type(e).__name__, e)
        return True


async def _loop(name: str, every: float, fn: Callable[[], Any]) -> None:
    while True:
        await asyncio.sleep(every)
        await asyncio.to_thread(run_once, name, fn)


def lifespan(jobs: List[Job]) -> Callable[[Any], Any]:
    @contextlib.asynccontextmanager
    async def _lifespan(_app: Any) -> AsyncIterator[None]:
        tasks = [asyncio.create_task(_loop(n, e, f)) for n, e, f in jobs if e > 0]
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    return _lifespan
