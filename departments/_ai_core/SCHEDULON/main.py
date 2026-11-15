# ================================================================================

"""Schedulon: greedy load distribution across workers and least-loaded worker lookup.

SchedulonAgent(config): health_check() returns agent, status and version (config
"version", default 0.1.0); distribute_load(tasks, workers) assigns each integer load in
order to the bucket with the smallest running total and returns the list of buckets;
next_available_slot(schedule) takes {worker: load} and returns the worker with the
smallest load.
State: keeps no state.
Failure: distribute_load returns [] when workers is not an int (or is a bool) or is below
1; next_available_slot returns None for an empty schedule; non-numeric loads raise TypeError.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger("SCHEDULON")

class SchedulonAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "SCHEDULON", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def distribute_load(self, tasks: List[int], workers: int) -> List[List[int]]:
        """
        Distribute task loads (ints) across N workers as evenly as possible.
        Returns list of worker buckets with assigned loads.
        """
        logger.debug("Distributing tasks=%s across workers=%s", tasks, workers)
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            return []                      # nobody to give work to
        buckets = [[] for _ in range(workers)]
        loads = [0] * workers

        for t in tasks:
            idx = loads.index(min(loads))
            buckets[idx].append(t)
            loads[idx] += t

        logger.debug("Distribution result: %s", buckets)
        return buckets

    def next_available_slot(self, schedule: Dict[str, int]) -> str:
        """
        Return worker ID (str) with smallest assigned load.
        schedule: {"worker1": load, "worker2": load}
        """
        if not schedule:
            logger.debug("Empty schedule")
            return None
        best = min(schedule, key=lambda k: schedule[k])
        logger.debug("Next available slot: %s", best)
        return best

# ================================================================================