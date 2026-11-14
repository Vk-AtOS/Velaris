"""Alias agent SANDE: fronts LOCAL_ACCELERATOR, LOCAL_AUTONOMY_CORE, LOCAL_REGISTRY_CACHE, LOCAL_ROUTER, LOCAL_MEMORY_STORE. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['LOCAL_ACCELERATOR', 'LOCAL_AUTONOMY_CORE', 'LOCAL_REGISTRY_CACHE', 'LOCAL_ROUTER', 'LOCAL_MEMORY_STORE']


class SANDEAgent(Delegator):
    name = "SANDE"
    components = _COMPONENTS
