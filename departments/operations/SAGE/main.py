"""Alias agent SAGE: fronts STRATEGOS, STRATEGIC_INTEL, CSM_CORE. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['STRATEGOS', 'STRATEGIC_INTEL', 'CSM_CORE']


class SAGEAgent(Delegator):
    name = "SAGE"
    components = _COMPONENTS
