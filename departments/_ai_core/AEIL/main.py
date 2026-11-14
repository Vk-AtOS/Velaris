"""Alias agent AEIL: fronts ECON_INTEL_CORE, MARKET_GAP_ANALYZER, ECONOVA. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['ECON_INTEL_CORE', 'MARKET_GAP_ANALYZER', 'ECONOVA']


class AEILAgent(Delegator):
    name = "AEIL"
    components = _COMPONENTS
