# ================================================================================

import logging
from typing import Dict, Any, List
from velaris.agents.REGISTRY.main import AgentRegistry
from velaris.agents.AGENT_LIFECYCLE_MANAGER.main import LifecycleManager
from velaris.agents.COGNITIVE_LOAD_BALANCER.main import LoadBalancer

logger = logging.getLogger("ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - ENGINE - %(levelname)s - %(message)s"))
logger.addHandler(handler)


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
        logger.debug("Request: agent=%s method=%s params=%s", agent, method, params)

        inst = self.registry.create(agent)

        if not hasattr(inst, method):
            raise AttributeError(f"Agent '{agent}' has no method '{method}'")

        fn = getattr(inst, method)
        if params:
            result = fn(**params)
        else:
            result = fn()

        logger.debug("Response: %s", result)
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
        logger.debug("Pipeline results: %s", results)
        return results

    def run_with_balance(self, agent, method, params=None):
        # choose agent via CLB (if multiple) - simple passthrough
        return self.run(agent, method, params)

# ================================================================================