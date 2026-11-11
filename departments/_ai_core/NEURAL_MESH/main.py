import logging
from typing import Dict, Any, List, Optional
from velaris.agents.MEMORY_FABRIC.main import MemoryFabric
logger = logging.getLogger('NEURAL_MESH')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - NEURAL_MESH - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class NeuralMesh:
    """
    Simple routing mesh for agent messages.
    Stores conversation context into MemoryFabric and routes messages using scores.
    """

    def __init__(self, config: Dict[str, Any]=None):
        self.config = config or {}
        self.mem = MemoryFabric()
        self.version = self.config.get('version', '0.1.0')

    def health_check(self) -> Dict[str, Any]:
        return {'agent': 'NEURAL_MESH', 'status': 'ok', 'version': self.version}

    def route(self, from_agent: str, to_agent: str, payload: Dict[str, Any], context_key: Optional[str]=None) -> Dict[str, Any]:
        if context_key:
            self.mem.put('neural_context', context_key, {'from': from_agent, 'payload': payload})
        logger.debug('Routing from %s to %s payload=%s', from_agent, to_agent, payload)
        return {'routed_to': to_agent, 'ok': True}

    def broadcast(self, agents: List[str], payload: Dict[str, Any], context_key: Optional[str]=None) -> Dict[str, Any]:
        results = {}
        for a in agents:
            results[a] = {'ok': True}
        if context_key:
            self.mem.put('neural_broadcast', context_key, {'payload': payload})
        logger.debug('Broadcasted to %d agents', len(agents))
        return results