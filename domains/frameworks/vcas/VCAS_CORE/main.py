# ================================================================================

import logging
logger = logging.getLogger("VCAS_CORE")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h=logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - VCAS_CORE - %(message)s"))
    logger.addHandler(h)

class VCASCoreAgent:
    def __init__(self):
        logger.debug("VCAS Core initialized.")
    def health_check(self):
        return {"agent":"VCAS_CORE","status":"ok","version":"0.1.0"}

# ================================================================================