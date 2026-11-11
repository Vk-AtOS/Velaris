import logging
logger=logging.getLogger("LOCAL_ROUTER")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_ROUTER - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class LocalRouter:
    def __init__(self,name="LOCAL_ROUTER"):
        self.name=name
    def route(self,task):
        return "offline"  # always offline for now
    def health_check(self): return {"agent":self.name,"status":"ok"}
