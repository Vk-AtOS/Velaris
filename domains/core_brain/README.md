# core_brain

Central orchestration layer — the boot sequence and runtime identity of the Velaris BOS. These agents form the command spine that every other domain routes through.

## Agents

| Agent | Description |
|-------|-------------|
| PRIME | Primary system controller — first agent to boot, owns the master process loop |
| ENGINE | Agent registry and execution pipeline — discovers and dispatches all other agents |
| REGISTRY | Manifest store — tracks agent identities, versions, and health state |
| ORCHESTRIX | Task ordering and dependency resolution across the full agent mesh |
| SOUL_VELARIS | System identity and mission anchor — holds the core intent and values of the BOS |
| SOUL_CORE_EXT | Extended soul bindings — secondary identity hooks for multi-persona deployments |
| NAVARCH | Navigation architect — routes inter-agent calls and manages control flow |
| SCHEDULON | Time-based scheduler — cron-like trigger layer for periodic agent execution |
