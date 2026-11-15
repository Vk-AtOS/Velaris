"""Sensitivity routing policy (KAN-15): which data may go to which model provider.

Every gateway call carries a level: public, internal or restricted. The rules, all in code:

  * No level given, or one that is not a level  ->  restricted (fail closed).
  * Code that read pay, bank, identity, health or candidate data (velaris.core.access.authorize_read)
    calls force_restricted(): from then on, in that context, every call counts as restricted whatever
    the caller says. A caller cannot lower it, only a new context (a new request) starts clean.
  * A provider accepts a level only if it is enabled and lists it. The built-in providers named
    anthropic, bedrock and ollama (configured from the environment by the operator) accept all levels;
    a provider from the registry accepts exactly what its record says.
  * A call no enabled provider accepts raises PolicyRefused. It is never downgraded or rerouted.
"""
from __future__ import annotations

import contextvars
from typing import Optional

from velaris.intel import providers
from velaris.intel.errors import PolicyRefused

LEVELS = providers.LEVELS
DEFAULT_LEVEL = "restricted"
_forced: contextvars.ContextVar[bool] = contextvars.ContextVar("velaris_llm_forced_restricted", default=False)


def force_restricted() -> None:
    """Everything called from now on in this context is restricted."""
    _forced.set(True)


def new_scope() -> contextvars.Token:
    """Start a request scope with the floor off; pass the token to end_scope(). access.acting_as does this, so
    one request's reading of pay data never makes the next request on the same thread restricted (or the reverse:
    a scope cannot inherit a lowered floor, it can only add)."""
    return _forced.set(False)


def end_scope(token: contextvars.Token) -> None:
    _forced.reset(token)


def effective(level: Optional[str]) -> str:
    if _forced.get() or level not in LEVELS:
        return DEFAULT_LEVEL
    return level  # type: ignore[return-value]


def permits(provider_id: str, level: str) -> bool:
    """May `level` data go to this provider? Unknown or disabled provider: no."""
    if provider_id in providers.BUILTIN_IDS:
        return providers.get(provider_id) is None     # a registry record can never shadow a built-in id
    p = providers.get(provider_id)
    return bool(p and p.accepts(level))


def authorize(provider_id: str, level: Optional[str]) -> str:
    """The effective level if `provider_id` may see it, else PolicyRefused. The only gate before a call."""
    eff = effective(level)
    if not permits(provider_id, eff):
        raise PolicyRefused(f"provider '{provider_id}' does not accept {eff} data; the call was not made")
    return eff
