# frameworks/vcas — Velaris Cognitive Autopilot System

Autonomous decision and autopilot framework. VCAS agents operate the BOS in fully autonomous mode — supervising, routing, and self-correcting without human intervention.

| Agent | Description |
|-------|-------------|
| VCAS_AUTOPILOT | Runs autonomous operation loops — full autopilot mode |
| VCAS_CORE | Core VCAS runtime and state machine |
| VCAS_ROUTER | Routes autopilot decisions to the appropriate domain agents |
| VCAS_SUPERVISOR | Supervises autopilot operation — escalates when confidence is low |
