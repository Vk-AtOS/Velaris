import logging
import statistics

logger = logging.getLogger("PRAETOR")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - PRAETOR - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class PraetorAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.threshold = self.config.get("threshold", 3.0)

    def health_check(self):
        status = {"agent": "PRAETOR", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def detect_anomaly(self, values):
        if not values or len(values) < 2:
            return False
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        latest = values[-1]
        if stdev == 0:
            return False
        z = abs((latest - mean) / stdev)
        anomaly = z > self.threshold
        logger.debug("Anomaly check: latest=%s mean=%s stdev=%s z=%s anomaly=%s",
                     latest, mean, stdev, z, anomaly)
        return anomaly
