"""Read-only measurements of the machine this process runs on (via psutil).

Nothing here changes a setting, signals a process or opens a socket. Every agent
that decides from these numbers also accepts a caller-supplied sample, so the
decision logic can be exercised with declared inputs.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import psutil

from velaris.agentkit.infra_store import is_number
from velaris.intel.paths import data_dir

logger = logging.getLogger("velaris.agentkit.infra")
MB = 1024 * 1024
PERCENT_KEYS = ("cpu_percent", "mem_percent", "disk_percent")


def sample() -> Dict[str, Any]:
    """One measurement: CPU, memory, the data directory's disk, load and power source."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(data_dir()))
    out: Dict[str, Any] = {
        "ts": time.time(),
        "cpu_percent": psutil.cpu_percent(interval=0.05),
        "cpu_count": psutil.cpu_count(logical=True) or 1,
        "mem_percent": mem.percent,
        "mem_total_mb": round(mem.total / MB, 1),
        "mem_available_mb": round(mem.available / MB, 1),
        "disk_percent": disk.percent,
        "disk_free_mb": round(disk.free / MB, 1),
        "load_1m": None, "battery_percent": None, "on_ac": None,
    }
    try:
        out["load_1m"] = round(os.getloadavg()[0], 2)
    except (OSError, AttributeError) as e:          # not available on every platform
        logger.debug("load average unavailable: %s", e)
    try:
        battery = psutil.sensors_battery()
        if battery is not None:
            out["battery_percent"], out["on_ac"] = round(battery.percent, 1), bool(battery.power_plugged)
    except (AttributeError, OSError, NotImplementedError) as e:
        logger.debug("battery sensor unavailable: %s", e)
    return out


def checked(given: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """A measured sample when `given` is None; `given` if it is well formed; else None.

    Well formed: a dict whose percentages (when present) are numbers in 0..100 and whose
    other known fields are non-negative numbers.
    """
    if given is None:
        return sample()
    if not isinstance(given, dict):
        return None
    for key in PERCENT_KEYS + ("battery_percent",):
        if given.get(key) is not None and not is_number(given[key], 0, 100):
            return None
    for key in ("cpu_count", "mem_total_mb", "mem_available_mb", "disk_free_mb", "load_1m"):
        if given.get(key) is not None and not is_number(given[key], 0):
            return None
    return given
