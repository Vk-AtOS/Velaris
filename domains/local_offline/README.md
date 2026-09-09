# local_offline

Local and offline execution layer — enables the BOS to operate without cloud connectivity, with full local agent registry, routing, and sandboxed execution.

## Agents

| Agent | Description |
|-------|-------------|
| LOCAL_AUTONOMY_CORE | Core local autonomy engine — governs fully offline operation mode |
| LOCAL_REGISTRY_CACHE | Cached local copy of the agent registry for offline discovery |
| LOCAL_ROUTER | Local-only request router — no cloud calls, all traffic stays on-device |
| OFFLINE_EXECUTION_ENGINE | Executes agent tasks in fully air-gapped environments |
| OFFLINE_REGISTRY | Full agent manifest registry for offline deployments |
| OFFLINE_SANDBOX | Isolated execution sandbox for testing agents without network access |
