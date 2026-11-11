"""
Velaris Backend Engine Test Harness
Phase 2 — Module Restoration
Validates processing, logging, router dispatch, and memory mesh integration.
"""

from velaris.backend.engine import backend
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

TEST_RESULTS = []

def backend_callback(message):
    TEST_RESULTS.append(message)

def run_test():
    # Reset memory mesh to clean state
    mesh.store = {}

    # Subscribe to backend processed events
    router.subscribe("backend_processed", backend_callback)

    # Process sample data
    output = backend.process("payload123")

    return {
        "callback_results": TEST_RESULTS,
        "mesh_after": mesh.get("backend:last_processed"),
        "returned_value": output
    }

if __name__ == "__main__":
    print(run_test())
