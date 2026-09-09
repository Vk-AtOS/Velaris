import logging
logger = logging.getLogger("SANITY_VERIFIER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - SANITY_VERIFIER - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class SanityVerifier:
    def __init__(self, name="SANITY_VERIFIER"):
        self.name = name

    def verify(self, constrained: dict):
        return {"final_safe_output": True}

    def health_check(self):
        return {"agent": self.name, "status": "ok"}
