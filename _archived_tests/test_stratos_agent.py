"""
Stratos Agent Test Harness
Phase 4B — Core Intelligence Agent #4
Validates: text analysis, structural reasoning, metadata extraction.
"""

from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def stratos_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Clear old state (Stratos does not use mesh directly but we reset for consistency)
    mesh.set("stratos:dummy", "ok")

    # Subscribe to Stratos output
    router.subscribe("stratos_out", stratos_callback)

    # Publish an analysis request
    router.publish("stratos_in", {
        "command": "analyze",
        "payload": "Stratos Agent Test 123. Checking Structure."
    })

    return {
        "callback_results": RESULTS
    }

if __name__ == "__main__":
    print(run_test())
