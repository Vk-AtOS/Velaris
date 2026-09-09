# CCSF — Cross-Context State Fusion

Merges state signals from multiple agents into a unified context snapshot. Resolves conflicts when agents produce contradictory outputs.

| Agent | Purpose |
|-------|---------|
| CCSF_CORE | Core fusion engine — collects and normalises agent state |
| CCSF_FUSION | Weighted merging of multi-agent outputs into single context |
| CCSF_RESOLVER | Conflict resolution — priority-based tie-breaking between agents |
