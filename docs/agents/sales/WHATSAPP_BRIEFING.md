# WHATSAPP_BRIEFING

- **Department:** `sales`
- **Status (static inventory):** `real`
- **Source:** `departments/sales/WHATSAPP_BRIEFING/main.py` (143 lines)

## Purpose

WHATSAPP_BRIEFING — Velaris BOS agent for Knackforge
Ported from VKatOS whatsapp_briefing. Daily metric logging + WhatsApp Business API dispatch.

## Class `WhatsAppBriefingSystem`

- `__init__(config)`
- `log(name, value, unit, notes)`
- `generate_briefing()`
- `generate_briefing_dict()`
- `send(message)`

## Class `WhatsAppBriefingAgent`

Daily business metric logger + WhatsApp Business dispatch.
Ported from VKatOS whatsapp_briefing.

- `__init__(config)`
- `health_check()`
- `log_metric(name, value, unit, notes)`
- `get_briefing()`
- `get_briefing_dict()`
- `send_briefing()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_no_state_in_source_tree.py`, `velaris/tests/test_requirements.py`
