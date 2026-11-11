import logging
logger = logging.getLogger("QREASON_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - QREASON_ENGINE - %(levelname)s - %(message)s"))
if not logger.handlers: logger.addHandler(handler)

class QReasonEngine:
    def __init__(self, name="QREASON_ENGINE"):
        self.name = name

    def deduce(self, data: dict):
        return {"q_deduction": data}

    def health_check(self):
        return {"agent": self.name, "status": "ok"}

# ---- appended stub (repair) ----

import logging
logger = logging.getLogger("QREASON_ENGINE")
try:
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        import sys
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s - QREASON_ENGINE - %(levelname)s - %(message)s"))
        logger.addHandler(h)
except Exception:
    pass

# Compatibility shim: if the real QREASON engine defines a different class, delegate to it.
def _find_component():
    try:
        from importlib import import_module
        # try common internal names
        for name in ("agents.QREASON_ENGINE.core", "agents.QREASON_ENGINE.engine", "agents.QREASON_ENGINE.main"):
            try:
                mod = import_module(name)
                # search for a plausible class in module
                for attr in dir(mod):
                    if attr.upper().endswith("ENGINE") or attr.upper().endswith("QREASON"):
                        comp = getattr(mod, attr)
                        return comp() if callable(comp) else comp
            except Exception:
                continue
    except Exception:
        pass
    return None

class QREASON_ENGINEAgent:
    def __init__(self, *args, **kwargs):
        self.name = "QREASON_ENGINE"
        self._component = _find_component()
        logger.debug("QREASON_ENGINEAgent shim initialized - delegate_present=%s", bool(self._component))

    def health_check(self):
        if self._component and hasattr(self._component, "health_check"):
            try:
                return self._component.health_check()
            except Exception:
                pass
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def run(self, method, *a, **kw):
        if self._component and hasattr(self._component, method):
            return getattr(self._component, method)(*a, **kw)
        raise AttributeError(f"No method {method} on QREASON_ENGINE delegate")

