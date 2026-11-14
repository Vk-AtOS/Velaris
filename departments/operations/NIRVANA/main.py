"""Alias agent NIRVANA: fronts SELF_CORRECTION_ENGINE, SANITY_VERIFIER, FAILOVER_ROUTER. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['SELF_CORRECTION_ENGINE', 'SANITY_VERIFIER', 'FAILOVER_ROUTER']


class NIRVANAAgent(Delegator):
    name = "NIRVANA"
    components = _COMPONENTS
