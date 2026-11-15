# ZERO_TRUST_PIPELINE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/ZERO_TRUST_PIPELINE/main.py` (196 lines)

## Purpose

ZERO_TRUST_PIPELINE: every request is checked for identity, device, context and policy; the default is deny.

evaluate(request) runs these stages in order and stops at the first that fails:

  1. shape      the request names a subject, a token, a resource and an action
  2. identity   the subject is enrolled and active, and the token was issued to
                that subject and has not expired (HMAC tokens signed with this
                agent's own key, so no SECURE_ACTION_TOKENS.generate() call, for
                any purpose string, can produce one)
  3. policy     among the policies whose resource pattern, action and role match:
                  - a "deny" policy whose device/context conditions hold refuses
                  - otherwise at least one "allow" policy must have every one of
                    its device and context conditions satisfied
  4. record     the decision is written to the hash-chained trace; if it cannot
                be recorded, the answer is deny

Roles come from enrolment, never from the request. Enrolment, revocation and policy
changes need a security admin caller (velaris.core.access); issue_token(subject) gives
a token only to the subject themselves or to a security admin. Every change is traced.

Resources are "/"-separated names. A resource holding "..", an empty segment, a
backslash or NUL is denied; policy patterns match segment by segment ("*" never
crosses "/", a final "**" matches the rest). Device and context facts are
supplied by the enforcement point that calls this agent; conditions over them
use velaris.agentkit.conditions (an absent field never satisfies an allow policy's
condition and always satisfies a deny policy's).
No policy, an unknown subject, a malformed request: all deny.

## Class `_IdentityTokens`

SecureActionTokens' format, signed with a key only this agent holds (domain separation).

- `__init__()`

## Class `ZERO_TRUST_PIPELINEAgent`

- `__init__()`
- `health_check()`
- `enroll(subject, roles)`
- `revoke(subject)`
- `issue_token(subject)` — A token proving `subject` for TOKEN_TTL_S seconds, for the subject themselves or a security admin.
- `verify(token, subject)` — True only if `token` was issued to the enrolled, active `subject` and is unexpired.
- `add_policy(policy_id, policy)` — {"effect": "allow"|"deny", "resources": [glob], "actions": [...], "roles": [...],
- `remove_policy(policy_id)`
- `evaluate(request)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.SECURE_ACTION_TOKENS.main`
- `velaris.core.access`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_governance_kernel.py`, `velaris/tests/test_kan88_security_agents.py`, `velaris/tests/test_loader_and_fail_closed.py`
