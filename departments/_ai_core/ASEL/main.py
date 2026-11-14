"""Alias agent ASEL: fronts ASEL_PLANNER, ASEL_EXECUTOR, ASEL_ROUTER, ASEL_STRATEGIST, ASEL_EVALUATOR. See velaris.agentkit.alias."""
from velaris.agentkit.alias import Delegator

_COMPONENTS = ['ASEL_PLANNER', 'ASEL_EXECUTOR', 'ASEL_ROUTER', 'ASEL_STRATEGIST', 'ASEL_EVALUATOR']


class ASELAgent(Delegator):
    name = "ASEL"
    components = _COMPONENTS
