import logging
from typing import Dict, Any, List, Optional
from velaris.agents.MEMORY_FABRIC.main import MemoryFabric
logger = logging.getLogger('NEURAL_MESH')

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
        """Queue `payload` in `to_agent`'s inbox. ok is True only when it was queued; "delivered" is always False
        (this mesh keeps the queue, the receiving agent collects it with receive())."""
        if not isinstance(to_agent, str) or not to_agent or not isinstance(payload, dict):
            return {'routed_to': to_agent, 'ok': False, 'queued': False, 'delivered': False,
                    'reason': 'to_agent must be a name and payload an object'}
        if context_key:
            self.mem.put('neural_context', context_key, {'from': from_agent, 'payload': payload})
        inbox = self.mem.get('neural_inbox', to_agent) or []
        self.mem.put('neural_inbox', to_agent, inbox + [{'from': from_agent, 'payload': payload}])
        logger.debug('Queued a message from %s for %s', from_agent, to_agent)
        return {'routed_to': to_agent, 'ok': True, 'queued': True, 'delivered': False}

    def broadcast(self, agents: List[str], payload: Dict[str, Any], context_key: Optional[str]=None) -> Dict[str, Any]:
        if not isinstance(agents, list):
            return {}
        results = {a: self.route('broadcast', a, payload) for a in agents}
        if context_key:
            self.mem.put('neural_broadcast', context_key, {'payload': payload})
        logger.debug('Broadcast queued for %d agents', len(agents))
        return results

    def receive(self, agent: str) -> List[Dict[str, Any]]:
        """Messages queued for `agent`, oldest first; they are removed from the inbox."""
        queued = self.mem.get('neural_inbox', agent) or []
        self.mem.put('neural_inbox', agent, [])
        return queued
