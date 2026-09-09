"""
Velaris Agent Registry Test Harness
Phase 2 — Module Restoration
Validates agent registration, retrieval, and logging.
"""

from velaris.agents.agents.base import BaseAgent
from velaris.agents.agents.registry import registry

def run_test():
    results = {}

    # Step 1: Create agent
    agent = BaseAgent("RegistryTester")

    # Step 2: Register agent
    registry.register(agent)

    # Step 3: Retrieve agent
    retrieved = registry.get("RegistryTester")
    results["retrieved_is_same_instance"] = (retrieved is agent)

    # Step 4: Attempt duplicate registration
    registry.register(agent)

    # Step 5: Return results
    return results

if __name__ == "__main__":
    print(run_test())
