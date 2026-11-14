"""Alias agent HYPERSYNC: fronts COHERENCE_SYNC_CORE, CSG_STATEALIGN. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['COHERENCE_SYNC_CORE', 'CSG_STATEALIGN']


class HYPERSYNCAgent(Delegator):
    name = "HYPERSYNC"
    components = _COMPONENTS
