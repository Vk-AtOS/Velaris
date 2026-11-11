import logging
logger = logging.getLogger("DECISION_GRAPH_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - DECISION_GRAPH_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class DecisionGraphEngine:
    def __init__(self, name="DECISION_GRAPH_ENGINE"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def graph(self, plan: dict):
        return {"graph": {"steps": plan.get("plan", [])}}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}
