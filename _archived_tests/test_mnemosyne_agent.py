"""
Mnemosyne Agent Test Harness
Phase 4B — Core Intelligence Agent #3
Validates bucket-based storing, appending, and retrieval.
"""

from velaris.core_agents.mnemosyne import mnemosyne
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def mnemosyne_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset memory storage
    mesh.set("mnemosyne:memory", {})

    # Subscribe to mnemosyne output
    router.subscribe("mnemosyne_out", mnemosyne_callback)

    # Test 1: Store key/value
    router.publish("mnemosyne_in", {
        "command": "store",
        "bucket": "profiles",
        "key": "user1",
        "value": {"name": "Velan", "role": "Builder"}
    })

    # Test 2: Append to list bucket
    router.publish("mnemosyne_in", {
        "command": "append",
        "bucket": "events",
        "value": "initialized"
    })

    router.publish("mnemosyne_in", {
        "command": "append",
        "bucket": "events",
        "value": "mnemosyne_test"
    })

    # Test 3: Retrieve key
    router.publish("mnemosyne_in", {
        "command": "get",
        "bucket": "profiles",
        "key": "user1"
    })

    # Test 4: Retrieve entire bucket
    router.publish("mnemosyne_in", {
        "command": "get",
        "bucket": "events"
    })

    return {
        "callback_results": RESULTS,
        "memory_state": mesh.get("mnemosyne:memory")
    }

if __name__ == "__main__":
    print(run_test())
