import logging, hashlib
logger = logging.getLogger("LOCAL_EMBEDDING_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_EMBEDDING_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class LocalEmbeddingEngine:
    def __init__(self,name="LOCAL_EMBEDDING_ENGINE"):
        self.name=name
    def embed(self,text:str):
        return [int(hashlib.sha256(text.encode()).hexdigest()[:4],16)]
    def health_check(self): return {"agent":self.name,"status":"ok"}
