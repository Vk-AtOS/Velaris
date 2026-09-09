# memory_knowledge

Memory and knowledge management layer — short-term, long-term, episodic, and cloud-extended memory stores, plus schema normalisation and streaming data ingestion.

## Agents

| Agent | Description |
|-------|-------------|
| MEMORY_FABRIC | Unified memory fabric — routes reads/writes to the correct memory tier |
| MEMORY_MESH | Distributed memory mesh — synchronises state across all active agents |
| MEMORY_CLOUD_EXPAND | Dynamically expands memory capacity to cloud storage when local is saturated |
| MEMORY_REALLOCATOR | Reallocates memory resources between agents based on priority and demand |
| LONGTERM_MEMORY | Persistent long-term store — retains facts, decisions, and outcomes indefinitely |
| SHORTTERM_MEMORY | Working memory — ephemeral state for active tasks and conversations |
| EPISODIC_MEMORY | Episode store — records sequences of events with temporal context |
| LOCAL_MEMORY_STORE | On-device memory — fast local KV store for latency-sensitive access |
| GLOBAL_STATE_MAP | System-wide state registry — single source of truth for current system state |
| CHROMOS | Chromatic memory indexer — semantic colour-coding and retrieval of knowledge |
| STREAM_PROCESSOR | Real-time stream ingestion — processes and indexes continuous data feeds |
