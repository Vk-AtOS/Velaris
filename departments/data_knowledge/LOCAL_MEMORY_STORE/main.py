import json, logging, os
logger = logging.getLogger("LOCAL_MEMORY_STORE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_MEMORY_STORE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class LocalMemoryStore:
    def __init__(self, path="local_store.json"):
        self.path = path
        if not os.path.exists(self.path): json.dump({}, open(self.path,"w"))
    def put(self,k,v): 
        d=json.load(open(self.path)); d[k]=v; json.dump(d,open(self.path,"w"))
    def get(self,k): 
        d=json.load(open(self.path)); return d.get(k)
    def health_check(self): return {"agent":"LOCAL_MEMORY_STORE","status":"ok"}
