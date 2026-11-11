import logging
logger=logging.getLogger("CLOUD_HANDOFF_CONTROLLER")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CLOUD_HANDOFF_CONTROLLER - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class CloudHandoffController:
    def __init__(self,name="CLOUD_HANDOFF_CONTROLLER"):
        self.name=name
    def sync(self,data):
        return {"synced":True}
    def health_check(self): return {"agent":self.name,"status":"ok"}
