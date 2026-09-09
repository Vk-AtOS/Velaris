"""
Oracle Agent Test Harness
Phase 4B — Core Intelligence Agent #5
Validates oracle inference: polarity, confidence, structural score.
"""

from velaris.core_agents.oracle import oracle
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def oracle_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset dummy state (oracle does not use mesh directly)
    mesh.set("oracle:dummy", "ok")

    # Subscribe to oracle output
    router.subscribe("oracle_out", oracle_callback)

    # Test 1: Positive message
    router.publish("oracle_in", {
        "command": "infer",
        "payload": "This is excellent and great work!"
    })

    # Test 2: Negative message
    router.publish("oracle_in", {
        "command": "infer",
        "payload": "This is bad and a complete failure"
    })

    # Test 3: Neutral message
    router.publish("oracle_in", {
        "command": "infer",
        "payload": "The system processed inputs and returned values."
    })

    return {
        "callback_results": RESULTS
    }

if __name__ == "__main__":
    print(run_test())
