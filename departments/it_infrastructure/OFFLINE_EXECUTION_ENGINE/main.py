import logging
logger=logging.getLogger("OFFLINE_EXECUTION_ENGINE")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OFFLINE_EXECUTION_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class OfflineExecutionEngine:
    def __init__(self,name="OFFLINE_EXECUTION_ENGINE"):
        self.name=name
    def execute(self,task:dict):
        return {"executed":task}
    def health_check(self): return {"agent":self.name,"status":"ok"}
