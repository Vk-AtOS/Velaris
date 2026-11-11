"""
Velaris Flow Engine Test Harness
Phase 3 — Higher-Level System Reconstruction
Validates flow execution, storage, and event routing.
"""

from velaris.backend.flow_engine import flow_engine
from velaris.agents.agents.router import router
from velaris.memory.mesh import mesh

RESULTS = []

def flow_callback(msg):
    RESULTS.append(msg)

def step_one():
    return "step1_ok"

def step_two():
    return {"value": 42}

def step_three():
    return ["a", "b", "c"]

def run_test():
    # Reset mesh
    mesh.store = {}

    # Subscribe to flow engine output
    router.subscribe("flow_engine_out", flow_callback)

    # Run flow
    out = flow_engine.run_flow("demo_flow", [
        step_one,
        step_two,
        step_three
    ])

    return {
        "flow_engine_returned": out,
        "router_messages": RESULTS,
        "mesh_state": mesh.get("flow:demo_flow:results")
    }

if __name__ == "__main__":
    print(run_test())
