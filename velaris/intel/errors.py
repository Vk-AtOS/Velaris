"""Errors of the model gateway, in one place so the policy, metering and routing modules can raise them
without importing the gateway."""
from __future__ import annotations


class LLMError(RuntimeError):
    """A model call failed. The message never contains a credential."""


class PolicyRefused(LLMError):
    """No enabled provider may see data of this sensitivity; the call was not made."""


class BudgetExceeded(LLMError):
    """The organisation's monthly model budget is used up (or the kill switch is on); the call was not made."""


class Retryable(LLMError):
    """A failure the next provider in a fallback chain may fix: timeout, 429, 5xx or an open breaker."""
