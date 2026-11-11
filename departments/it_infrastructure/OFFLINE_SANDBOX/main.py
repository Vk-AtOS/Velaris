import logging
logger=logging.getLogger("OFFLINE_SANDBOX")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OFFLINE_SANDBOX - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class OfflineSandbox:
    def __init__(self,name="OFFLINE_SANDBOX"):
        self.name=name
    def safe(self,payload):
        return {"safe": False, "payload": payload, "status": "not_implemented", "reason": "no real check exists yet; denied (fail closed)"}
    def health_check(self): return {"agent":self.name,"status":"ok"}
