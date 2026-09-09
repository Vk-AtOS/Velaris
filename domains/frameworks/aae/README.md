# frameworks/aae — Adaptive Action Engine

Action modelling and execution framework. AAE agents model potential actions, evaluate their consequences in a sandbox, and execute approved actions via a governed policy layer.

| Agent | Description |
|-------|-------------|
| AAE_POLICY | Defines and enforces action execution policies |
| AAE_RUNTIME | Runtime executor — dispatches approved actions to target systems |
| ADAPTIVE_ACTION_ENGINE | Core adaptive engine — selects actions based on real-time feedback |
| ACTION_MODELING_CORE | Models action outcomes before execution |
| ACTION_SANDBOX | Safe sandbox for testing actions without side effects |
