"""Alias agent CORE_CONVERGENCE: fronts EOF_CORE, EOF_GATEWAY, EOF_POLICY, ENGINE. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['EOF_CORE', 'EOF_GATEWAY', 'EOF_POLICY', 'ENGINE']


class CORE_CONVERGENCEAgent(Delegator):
    name = "CORE_CONVERGENCE"
    components = _COMPONENTS
