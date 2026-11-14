"""Alias agent GCK: fronts GLOBAL_STATE_MAP. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['GLOBAL_STATE_MAP']


class GCKAgent(Delegator):
    name = "GCK"
    components = _COMPONENTS
