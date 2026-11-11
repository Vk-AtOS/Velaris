import logging
logger = logging.getLogger("LOCAL_EMBEDDING_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LOCAL_EMBEDDING_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class LocalEmbeddingEngine:
    def __init__(self,name="LOCAL_EMBEDDING_ENGINE"):
        self.name=name
    def embed(self,text:str):
        raise NotImplementedError("LOCAL_EMBEDDING_ENGINE.embed: previous version returned one sha256-derived integer; no embedding model exists yet")
    def health_check(self): return {"agent":self.name,"status":"ok"}
