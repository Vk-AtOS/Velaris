import logging
from typing import Dict, Any, List
import random

logger = logging.getLogger("QUANTUM_BRIDGE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - QUANTUM_BRIDGE - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class QuantumBridge:
    """
    Provides:
      - health_check()
      - simulate_circuit(params) -> returns deterministic pseudo-results
      - backend_list() -> empty list or available hooks
    This is a safe stub; when Qiskit/Pennylane installed, we can plug in real backends.
    """
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.sim_mode = True
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "QUANTUM_BRIDGE", "status": "ok", "sim_mode": self.sim_mode}

    def backend_list(self) -> List[str]:
        # placeholder: real adapter would list remote providers (ibm, rigetti, local_sim)
        return []

    def simulate_circuit(self, shots: int = 1024, seed: int = None) -> Dict[str, Any]:
        r = random.Random(seed or 0)
        # return a trivial binary distribution stub
        zeros = int(shots * 0.6 + r.random()*10)
        ones = shots - zeros
        return {"shots": shots, "0": zeros, "1": ones}
