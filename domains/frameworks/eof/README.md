# EOF — Execution Oversight Framework

Monitors all active pipelines, enforces pre/post execution checks, and applies policy rules to halt or flag anomalous runs.

| Agent | Purpose |
|-------|---------|
| EOF_CORE | Pipeline monitor — detects anomalies across active runs |
| EOF_GATEWAY | Entry/exit gate — enforces checks before and after execution |
| EOF_POLICY | Policy ruleset — defines halt conditions and flag triggers |
