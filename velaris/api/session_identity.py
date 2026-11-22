"""The production identity resolver: who somebody is NOW, taken from the signed session of THIS request (VEL-12).

Velaris has no user directory; identities arrive signed from the AetherOS gateway. The one identity Velaris can vouch
for at any moment is the person whose signed request it is serving, so that is all this resolver knows:

  * `bind(caller)` is called by the auth dependency once the gateway signature and identity assertion are verified; it
    sets a request-scoped contextvar (every request runs in its own context, worker threads copy it);
  * `resolve(org, user)` returns that Caller when it is exactly (org, user), and otherwise raises IdentityUnavailable.

It never returns None for somebody else: None means "gone or inactive" and makes the absence mode auto-revoke a
delegation, which must not happen just because somebody else's request was being served. No signed session, another
person, or another organisation therefore means "cannot verify": fail closed (the delegation is queued, not used).
Mirroring delegations into Prime, so they can be used without the principal's own request, is a follow-up.
"""
from __future__ import annotations

import contextvars
from typing import Optional

from velaris.core.access import Caller
from velaris.orchestration import identity

_session: contextvars.ContextVar[Optional[Caller]] = contextvars.ContextVar("velaris_signed_session", default=None)


def bind(caller: Optional[Caller]) -> None:
    """Record the verified caller of the current request (None clears it)."""
    _session.set(caller)


def resolve(org: str, user_id: str) -> Optional[Caller]:
    c = _session.get()
    if c is not None and c.id == user_id and c.org == org:
        return c
    raise identity.IdentityUnavailable("no verified signed session for that person in this request")


def install() -> None:
    """Install `resolve` unless the deployment already installed its own resolver."""
    if not identity.has_resolver():
        identity.set_resolver(resolve)
