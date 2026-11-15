"""
Velaris Worker Agent Test Harness
Phase 4 — Functional Agents & Advanced Orchestration
Validates WorkerAgent tasks: uppercase, reverse, length.
"""

from velaris.agents.agents.worker_agent import WorkerAgent
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def worker_callback(msg):
    RESULTS.append(msg)

def run_test():
    # Reset mesh for clean testing
    mesh.store = {}

    # Instantiate worker agent
    WorkerAgent()

    # Subscribe to worker output
    router.subscribe("worker_out", worker_callback)

    # Send uppercase task
    router.publish("worker_in", {
        "task": "uppercase",
        "payload": "hello"
    })

    # Send reverse task
    router.publish("worker_in", {
        "task": "reverse",
        "payload": "world"
    })

    # Send length task
    router.publish("worker_in", {
        "task": "length",
        "payload": "velaris"
    })

    # Send unknown task
    router.publish("worker_in", {
        "task": "something_else",
        "payload": "???"
    })

    return {
        "worker_results": RESULTS
    }

if __name__ == "__main__":
    print(run_test())
