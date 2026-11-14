"""Alias agent FSCL: fronts SOUL_VELARIS, PRIME, ENGINE. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['SOUL_VELARIS', 'PRIME', 'ENGINE']


class FSCLAgent(Delegator):
    name = "FSCL"
    components = _COMPONENTS
