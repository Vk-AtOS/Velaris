"""Alias agent CONVERGENCE_BRIDGE: fronts ORCHESTRIX, COHERENCE_SYNC_CORE, REGISTRY. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['ORCHESTRIX', 'COHERENCE_SYNC_CORE', 'REGISTRY']


class CONVERGENCE_BRIDGEAgent(Delegator):
    name = "CONVERGENCE_BRIDGE"
    components = _COMPONENTS
