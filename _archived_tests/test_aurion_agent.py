"""
Aurion Agent Test Harness
Phase 4B — Core Intelligence Agents
Validates context updates, retrieval, and analysis.
"""

from velaris.core_agents.aurion import aurion
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def aurion_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset context storage
    mesh.set("aurion:context", {})

    # Subscribe to Aurion output
    router.subscribe("aurion_out", aurion_callback)

    # Set context
    router.publish("aurion_in", {
        "command": "set_context",
        "payload": {"project": "Velaris", "phase": 4}
    })

    # Get context
    router.publish("aurion_in", {
        "command": "get_context"
    })

    # Analyze text
    router.publish("aurion_in", {
        "command": "analyze",
        "payload": "Velaris Core Intelligence Test 123"
    })

    return {
        "callback_results": RESULTS,
        "mesh_context": mesh.get("aurion:context")
    }

if __name__ == "__main__":
    print(run_test())
