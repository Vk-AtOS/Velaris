"""
Velaris Base Agent Test Harness
Phase 2 — Module Restoration
Validates basic behavior of the BaseAgent class.
"""

from velaris.agents.agents.base import BaseAgent
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

TEST_RESULTS = []

def test_callback(msg):
    TEST_RESULTS.append(msg)

def run_test():
    # Clear mesh for clean test run
    mesh.store = {}

    # Step 1: Initialize Agent
    agent = BaseAgent("Tester")

    # Step 2: Router Subscription
    router.subscribe("test_agent_channel", test_callback)

    # Step 3: Emit message
    agent.emit("test_agent_channel", "agent_ping")

    # Step 4: Store and Load
    agent.store("foo", "bar")
    loaded = agent.load("foo")

    # Step 5: Return test results
    return {
        "router_callback_results": TEST_RESULTS,
        "loaded_value": loaded
    }

if __name__ == "__main__":
    print(run_test())
