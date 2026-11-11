import logging
logger = logging.getLogger("RECURSIVE_GOAL_PLANNER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - RECURSIVE_GOAL_PLANNER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class RecursiveGoalPlanner:
    def __init__(self, name="RECURSIVE_GOAL_PLANNER"):
        self.name = name
        logger.debug(f"{self.name} initialized.")

    def recurse(self, plan: dict):
        return {"expanded": plan}

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}
