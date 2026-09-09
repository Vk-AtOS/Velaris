"""
Econos Agent Test Harness
Phase 4B — Core Intelligence Agent #6
Validates numeric extraction, trend detection, and economic scoring.
"""

from velaris.core_agents.econos import econos
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def econos_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset dummy mesh state
    mesh.set("econos:dummy", "ok")

    # Subscribe to Econos output
    router.subscribe("econos_out", econos_callback)

    # Test message containing numbers and upward indicators
    router.publish("econos_in", {
        "command": "analyze",
        "payload": "Revenue increased from 120 to 180 showing strong growth and profit."
    })

    # Test message with negative trend and numeric loss
    router.publish("econos_in", {
        "command": "analyze",
        "payload": "Sales dropped from 300 to 150, indicating a significant loss and decrease."
    })

    # Test neutral message with no numerical indicators
    router.publish("econos_in", {
        "command": "analyze",
        "payload": "Market conditions remain stable overall."
    })

    return {
        "callback_results": RESULTS
    }

if __name__ == "__main__":
    print(run_test())
