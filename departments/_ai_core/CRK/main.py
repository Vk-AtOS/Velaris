"""Alias agent CRK: fronts CRK_CHAIN, CRK_CONTEXT, CRK_INTENT, CRK_REASONER, CRK_VALIDATOR. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['CRK_CHAIN', 'CRK_CONTEXT', 'CRK_INTENT', 'CRK_REASONER', 'CRK_VALIDATOR']


class CRKAgent(Delegator):
    name = "CRK"
    components = _COMPONENTS
