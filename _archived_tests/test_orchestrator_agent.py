"""
Velaris Orchestrator Agent Test Harness
Phase 3 — Higher-Level System Reconstruction
Validates orchestrator dispatch and subsystem orchestration.
"""

from velaris.agents.agents.orchestrator import OrchestratorAgent
from velaris.agents.agents.task_agent import TaskAgent
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def orchestrator_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset memory mesh to clean state
    mesh.store = {}

    # Create agents
    OrchestratorAgent()
    TaskAgent()

    # Subscribe to orchestrator output
    router.subscribe("orchestrator_out", orchestrator_callback)

    # Test: dispatch a task
    router.publish("orchestrator_in", {
        "command": "dispatch_task",
        "payload": {"command": "store", "payload": "orchestrated_value"}
    })

    # Test: ask for last task value
    router.publish("orchestrator_in", {
        "command": "get_last_task"
    })

    return {
        "results": RESULTS,
        "mesh_state": mesh.get("task_agent:last_store")
    }

if __name__ == "__main__":
    print(run_test())
