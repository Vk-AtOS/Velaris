"""Fallback chains and circuit breakers across providers (KAN-16).

A task class (planner, worker, classifier, embedding) has an ordered list of "provider:model".
complete() tries them in order. A failure that another provider may fix (timeout, HTTP 429, 5xx,
or an open breaker) moves on to the next entry; any other failure (a bad request, a refusal by
policy or budget) is raised at once, because trying elsewhere would not change it.

  * Sensitivity: entries whose provider may not see the call's level are SKIPPED, never used,
    whatever the chain says. If nothing in the chain may see it, PolicyRefused.
  * Breaker per provider: closed -> open after `failures` consecutive failures -> after `open_s`
    seconds half-open (one trial call) -> closed on success, open again on failure.
  * Caps: at most `max_attempts` calls and `max_seconds` in total per request; reaching either is a
    clear LLMError listing what was tried.

ponytail: breaker state is per process. With several workers each learns on its own (a provider
that is down costs each worker `failures` calls); share it through Redis if that matters.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from velaris.agentkit.state import JsonState
from velaris.intel import llm as gateway
from velaris.intel import policy, trace
from velaris.intel.errors import LLMError, PolicyRefused, Retryable

TASK_CLASSES = ("planner", "worker", "classifier", "embedding")
MAX_CHAIN = 10


def _chains() -> JsonState:
    return JsonState("llm_router", "chains.json", {"chains": {}}, version=1)


def set_chain(task_class: str, models: List[str], by: str = "") -> None:
    if task_class not in TASK_CLASSES:
        raise ValueError(f"task class is one of {', '.join(TASK_CLASSES)}")
    if not models or len(models) > MAX_CHAIN or not all(isinstance(m, str) and ":" in m for m in models):
        raise ValueError(f"a chain is 1 to {MAX_CHAIN} entries of the form provider:model")
    _chains().update(lambda d: d["chains"].__setitem__(task_class, list(models)))
    trace.append("router", "chain.set", {"task_class": task_class, "models": list(models), "by": by})


def chain(task_class: str) -> List[str]:
    return list(_chains().load()["chains"].get(task_class, []))


@dataclass
class _State:
    failures: int = 0
    opened_at: float = 0.0
    trial_out: bool = False


class Breaker:
    """closed / open / half-open per provider. Thread-safe. `clock` is injectable for tests."""

    def __init__(self, failures: Optional[int] = None, open_s: Optional[float] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.threshold = failures or int(os.environ.get("VELARIS_BREAKER_FAILURES", "5"))
        self.open_s = open_s if open_s is not None else float(os.environ.get("VELARIS_BREAKER_OPEN_S", "30"))
        self._clock, self._lock, self._s = clock, threading.Lock(), {}  # type: ignore[var-annotated]

    def state(self, provider: str) -> str:
        with self._lock:
            s = self._s.get(provider)
            if s is None or s.failures < self.threshold:
                return "closed"
            return "half_open" if self._clock() - s.opened_at >= self.open_s else "open"

    def allow(self, provider: str) -> bool:
        """May a call go to this provider now? Half-open lets exactly one trial through."""
        with self._lock:
            s = self._s.get(provider)
            if s is None or s.failures < self.threshold:
                return True
            if self._clock() - s.opened_at < self.open_s or s.trial_out:
                return False
            s.trial_out = True
            return True

    def success(self, provider: str) -> None:
        with self._lock:
            self._s.pop(provider, None)

    def failure(self, provider: str) -> None:
        with self._lock:
            s = self._s.setdefault(provider, _State())
            s.failures += 1
            s.trial_out = False
            if s.failures >= self.threshold:
                s.opened_at = self._clock()


DEFAULT_BREAKER = Breaker()


def complete(task_class: str, prompt: str, *, llm: Optional["gateway.LLM"] = None, sensitivity: Optional[str] = None,
             models: Optional[List[str]] = None, breaker: Optional[Breaker] = None, max_attempts: int = 3,
             max_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic, **kw) -> "gateway.Completion":
    """Run `prompt` on the first provider of the task class's chain that may see it and answers."""
    llm, breaker = llm or gateway.LLM(), breaker or DEFAULT_BREAKER
    entries = models or chain(task_class)
    if not entries:
        raise LLMError(f"no model chain is configured for task class '{task_class}'")
    level = policy.effective(sensitivity)
    allowed = [m for m in entries if policy.permits(m.split(":")[0], level)]
    if not allowed:
        raise PolicyRefused(f"no provider in the '{task_class}' chain accepts {level} data; the call was not made")
    start, tried, attempts = clock(), [], 0
    for model in allowed:
        provider = model.split(":")[0]
        if attempts >= max_attempts:
            break
        if clock() - start >= max_seconds:
            break
        if not breaker.allow(provider):
            tried.append(f"{model} (breaker open)")
            trace.append("router", "skip.breaker", {"model": model, "task_class": task_class})
            continue
        attempts += 1
        try:
            with gateway.call_timeout(max(1.0, max_seconds - (clock() - start))):
                out = llm.complete(prompt, model=model, sensitivity=level, **kw)
        except Retryable as e:
            breaker.failure(provider)
            tried.append(f"{model} ({type(e).__name__})")
            trace.append("router", "failover", {"model": model, "task_class": task_class, "error": str(e)[:200]})
            continue
        breaker.success(provider)
        return out
    raise LLMError(f"no provider answered for '{task_class}' ({attempts} attempts, cap {max_attempts} attempts / "
                   f"{max_seconds:.0f}s): " + ("; ".join(tried) or "none reachable"))
