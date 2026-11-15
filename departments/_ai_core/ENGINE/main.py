# ================================================================================

"""Velaris engine: runs methods of registered agents by name, singly or as a pipeline.
VelarisEngine.run(agent, method, params) creates the agent through AgentRegistry.create and calls the
method with params as keyword arguments. pipeline(steps) runs a list of {"agent", "method", "params"}
steps in order and returns [{"step", "result"}]. run_with_balance is a plain passthrough to run (the
load balancer is not consulted). health_check() reports the number of registered agents.
State: keeps none of its own beyond the registry instance; parameters and results are never logged.
Failure: an unknown agent propagates the registry's error, a missing method raises AttributeError, and
an exception from the agent or a malformed pipeline step (KeyError) propagates and stops the pipeline.
Note: __post_init__ is never called by __init__, so self.lifecycle and self.clb are not created.
"""
import logging
from typing import Dict, Any, List
from velaris.agents.REGISTRY.main import AgentRegistry
from velaris.agents.AGENT_LIFECYCLE_MANAGER.main import LifecycleManager
from velaris.agents.COGNITIVE_LOAD_BALANCER.main import LoadBalancer

logger = logging.getLogger("ENGINE")
# No forced DEBUG level and no private handler: the application decides what is logged and where.
# Parameters and results are never logged here; they carry whatever the agent was given (pay, identity, health).


class VelarisEngine:
    def __post_init__(self):
        self.lifecycle = LifecycleManager()
        self.clb = LoadBalancer()

    """
    Central execution engine for all Velaris operations.
    Loads agents through the REGISTRY and executes their methods dynamically.
    Provides:
        - run(agent_name, method, params)
        - pipeline([{agent, method, params}, ...])
        - health_check()
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.registry = AgentRegistry()
        logger.debug("Engine initialized with %s agents", len(self.registry.list_agents()))

    #################################################
    # HEALTH
    #################################################
    def health_check(self):
        status = {
            "agent": "ENGINE",
            "status": "ok",
            "version": self.config.get("version", "0.1.0"),
            "registered_agents": len(self.registry.list_agents())
        }
        logger.debug("Health: %s", status)
        return status

    #################################################
    # RUN SINGLE AGENT METHOD
    #################################################
    def run(self, agent: str, method: str, params: Dict[str, Any] = None):
        logger.debug("Request: agent=%s method=%s", agent, method)

        inst = self.registry.create(agent)

        if not hasattr(inst, method):
            raise AttributeError(f"Agent '{agent}' has no method '{method}'")

        fn = getattr(inst, method)
        if params:
            result = fn(**params)
        else:
            result = fn()

        return result

    #################################################
    # PIPELINE EXECUTION
    #################################################
    def pipeline(self, steps: List[Dict[str, Any]]):
        """
        steps = [
            {"agent": "VIGILIS", "method": "health_check", "params": {}},
            ...
        ]
        """
        results = []
        for step in steps:
            res = self.run(step["agent"], step["method"], step.get("params"))
            results.append({
                "step": step,
                "result": res
            })
        logger.debug("Pipeline finished: %d steps", len(results))
        return results

    def run_with_balance(self, agent, method, params=None):
        # choose agent via CLB (if multiple) - simple passthrough
        return self.run(agent, method, params)

# ================================================================================