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
        """True when the latest value is more than `threshold` standard deviations
        from the values before it.

        The baseline excludes the latest value: including it lets a spike inflate
        its own mean and stdev, which caps z at (n-1)/sqrt(n) and hides the spike
        in short series.
        """
        if not values or len(values) < 3:
            return False
        baseline, latest = values[:-1], values[-1]
        mean = statistics.mean(baseline)
        stdev = statistics.stdev(baseline)
        if stdev == 0:
            # A perfectly flat history: any departure from it is anomalous.
            return latest != mean
        z = abs((latest - mean) / stdev)
        anomaly = z > self.threshold
        logger.debug("Anomaly check: latest=%s mean=%s stdev=%s z=%s anomaly=%s",
                     latest, mean, stdev, z, anomaly)
        return anomaly
