import logging
logger = logging.getLogger("QLOGIC_GATEWAY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - QLOGIC_GATEWAY - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class QLogicGateway:
    def __init__(self, name="QLOGIC_GATEWAY"):
        self.name = name

    def branch(self, deduced: dict):
        return {"branched": deduced}

    def health_check(self):
        return {"agent": self.name, "status": "ok"}
