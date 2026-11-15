import logging
from typing import List, Dict, Any

logger = logging.getLogger("FLUXOR")

class FluxorAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.spike_threshold = self.config.get("spike_threshold", 1.5)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "FLUXOR", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def compute_throughput(self, loads: List[int]) -> float:
        """
        Throughput = sum(loads) / len(loads)
        """
        if not loads:
            logger.debug("Empty loads for throughput")
            return 0.0
        tp = sum(loads) / len(loads)
        logger.debug("Computed throughput=%s loads=%s", tp, loads)
        return tp

    def detect_spike(self, loads: List[int]) -> bool:
        """
        Spike detected if last_value > avg * spike_threshold
        """
        if len(loads) < 2:
            logger.debug("Not enough data for spike detection")
            return False
        avg = sum(loads[:-1]) / (len(loads) - 1)
        last = loads[-1]
        spike = last > avg * self.spike_threshold
        logger.debug("Spike check: avg=%s last=%s spike=%s", avg, last, spike)
        return spike

    def balance_load(self, loads: List[int], target: int) -> List[int]:
        """
        Attempts to adjust each load closer to target:
        If load > target → reduce by 1
        If load < target → increase by 1
        """
        balanced = []
        for l in loads:
            if l > target:
                balanced.append(l - 1)
            elif l < target:
                balanced.append(l + 1)
            else:
                balanced.append(l)
        logger.debug("Balanced loads: %s -> %s", loads, balanced)
        return balanced
