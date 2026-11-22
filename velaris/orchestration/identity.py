"""Who somebody is NOW: the one lookup of a user's current roles, shared by the orchestrators and the absence mode.

A run or a delegation keeps the roles a person had when it was made. Roles change (a demotion, a leaver), so using
the saved roles later is using authority the person may no longer have. Rules, here and nowhere else:

  * the person acting in THIS request is the one fact that is current: their roles come from the signed request;
  * anybody else's current identity comes from the resolver the deployment installs (`set_resolver`), a function
    (org, user_id) -> Caller | None; None means the person no longer exists or is inactive;
  * effective authority is the saved roles AND the current roles: saved roles are an upper bound, never an grant;
  * no resolver, or a resolver that fails: the identity cannot be verified and the caller is refused (fail closed).

Velaris has no user directory of its own (identities arrive signed from the AetherOS gateway). The API installs
velaris.api.session_identity at startup: it vouches only for the person whose verified signed request is being served,
so anybody else's identity stays unverifiable (their runs and any delegation use wait) until the gateway offers a lookup.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable, Optional

from velaris.core.access import AccessDenied, Caller

logger = logging.getLogger("velaris.orchestration.identity")
Resolver = Callable[[str, str], Optional[Caller]]
_resolver: Optional[Resolver] = None


class IdentityUnavailable(RuntimeError):
    """The person's current identity could not be established (no resolver, or it failed)."""


def set_resolver(fn: Optional[Resolver]) -> None:
    global _resolver
    _resolver = fn


def has_resolver() -> bool:
    return _resolver is not None


def current(org: str, user_id: str) -> Optional[Caller]:
    """The person's current Caller, None when they no longer exist or are inactive. Raises IdentityUnavailable."""
    if _resolver is None:
        raise IdentityUnavailable("no identity resolver is installed")
    try:
        c = _resolver(org, user_id)
    except Exception as e:  # the lookup is not trusted to behave; its failure is "cannot verify"
        logger.warning("identity lookup failed: %s", type(e).__name__)
        raise IdentityUnavailable("the identity lookup failed") from e
    if c is None:
        return None
    if not isinstance(c, Caller) or c.id != user_id or c.org != org:
        raise IdentityUnavailable("the identity lookup returned somebody else")
    return c


def narrow(saved: Caller, now: Caller) -> Caller:
    """`saved` with only the roles `now` also holds."""
    return Caller(id=saved.id, org=saved.org, roles=saved.roles & now.roles, employee_id=saved.employee_id)


def current_owner(saved: Caller, asking: Caller) -> Caller:
    """The owner of a run as they are now (saved roles AND current roles); AccessDenied when that cannot be established."""
    if asking.id == saved.id and asking.org == saved.org:
        return narrow(saved, asking)
    try:
        now = current(saved.org, saved.id)
    except IdentityUnavailable:
        raise AccessDenied("the run's owner cannot be verified right now, so only the owner can move it") from None
    if now is None:
        raise AccessDenied("the run's owner no longer exists or is inactive")
    return narrow(saved, now)


def holds(user: Caller, roles: Iterable[str]) -> bool:
    return bool(user.roles & set(roles))
