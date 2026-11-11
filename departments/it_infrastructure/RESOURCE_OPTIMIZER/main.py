import logging, psutil
logger=logging.getLogger("RESOURCE_OPTIMIZER")
logger.setLevel(logging.DEBUG)
handler=logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - RESOURCE_OPTIMIZER - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class ResourceOptimizer:
    def __init__(self,name="RESOURCE_OPTIMIZER"):
        self.name=name
    def profile(self):
        return {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent}
    def health_check(self): return {"agent":self.name,"status":"ok"}
