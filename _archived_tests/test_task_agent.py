"""
Velaris Task Agent Test Harness
Phase 3 — Higher-Level System Reconstruction
Validates basic task command handling.
"""

from velaris.agents.agents.task_agent import TaskAgent
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

TEST_RESULTS = []

def task_callback(msg):
    TEST_RESULTS.append(msg)

def run_test():
    # Reset mesh for clean testing
    mesh.store = {}

    # Instantiate agent
    TaskAgent()

    # Subscribe to output channel
    router.subscribe("task_agent_out", task_callback)

    # Send "store" command
    router.publish("task_agent_in", {"command": "store", "payload": "hello"})

    # Send "echo" command
    router.publish("task_agent_in", {"command": "echo", "payload": "world"})

    # Send unknown command
    router.publish("task_agent_in", {"command": "xyz", "payload": "???"})

    return {
        "callback_results": TEST_RESULTS,
        "mesh_last_store": mesh.get("task_agent:last_store")
    }

if __name__ == "__main__":
    print(run_test())
