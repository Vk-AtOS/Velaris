"""
Sentinel Agent Test Harness
Phase 4B — Core Intelligence Agent #7
Validates anomaly detection, symbol ratio, extreme numeric ranges, and integrity score.
"""

from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def sentinel_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset dummy state
    mesh.set("sentinel:dummy", "ok")

    # Subscribe to Sentinel output
    router.subscribe("sentinel_out", sentinel_callback)

    # Test 1: High symbol ratio (should trigger anomaly)
    router.publish("sentinel_in", {
        "command": "scan",
        "payload": "ALERT!!! SYSTEM ERROR!!! $$$$ #### @@@@"
    })

    # Test 2: Extreme numeric range (should trigger anomaly)
    router.publish("sentinel_in", {
        "command": "scan",
        "payload": "Values shifted from 5 to 5000 which is unusual."
    })

    # Test 3: Normal message (should NOT trigger anomaly)
    router.publish("sentinel_in", {
        "command": "scan",
        "payload": "The metrics remain stable across the current dataset."
    })

    return {
        "callback_results": RESULTS
    }

if __name__ == "__main__":
    print(run_test())
