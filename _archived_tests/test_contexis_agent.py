"""
Contexis Agent Test Harness
Phase 4B — Core Intelligence Agents (Agent #2)
Validates: merge, get, expand operations.
"""

from velaris.core_agents.contexis import contexis
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def contexis_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset tree
    mesh.set("contexis:tree", {})

    # Subscribe to output
    router.subscribe("contexis_out", contexis_callback)

    # Test merge
    router.publish("contexis_in", {
        "command": "merge",
        "payload": {"user": "velan", "mode": "test"}
    })

    # Test retrieval
    router.publish("contexis_in", {
        "command": "get"
    })

    # Test expansion
    router.publish("contexis_in", {
        "command": "expand",
        "payload": "Contexis Deep Context Engine 42"
    })

    return {
        "callback_results": RESULTS,
        "tree_state": mesh.get("contexis:tree")
    }

if __name__ == "__main__":
    print(run_test())
