"""
Velaris Flow Engine
Phase 3 — Higher-Level System Reconstruction
Executes multi-step flows and chained action sequences.
"""
from velaris.core.utils import log
from velaris.agents.router import router
from velaris.memory.mesh import mesh

class FlowEngine:

    def __init__(self):
        log('[FlowEngine] Initialized')

    def run_flow(self, flow_name: str, steps: list):
        log(f'[FlowEngine] Running flow: {flow_name}')
        results = []
        for index, step in enumerate(steps):
            log(f'[FlowEngine] Executing step {index}: {step}')
            try:
                output = step()
                results.append(output)
            except Exception as e:
                log(f'[FlowEngine] Step {index} failed: {e}')
                results.append({'error': str(e)})
        mesh.set(f'flow:{flow_name}:results', results)
        router.publish('flow_engine_out', {'flow': flow_name, 'results': results})
        return results
flow_engine = FlowEngine()