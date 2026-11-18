"""Usage metering and spend limits for model calls (KAN-14, and the cost rules of decision D6).

Every call is recorded, success or failure: org, agent, action, provider, model, tokens in and out
(from the provider's reply, else an estimate that is flagged as one), latency, status, a cost
estimate from the catalogue (None when a price is unknown) and the sensitivity level. NEVER the
prompt or the reply: only sizes. Records are append-only JSON lines under VELARIS_DATA, one file
per month, written with the cross-process lock; running totals per organisation live in a small
JSON document next to them so a budget check is O(1) however long the log is.

Limits, checked BEFORE every call by check():
  * kill switch   VELARIS_LLM_KILL_SWITCH=1, or the file <data>/llm.kill (set_kill_switch)
  * monthly budget per organisation, in USD and/or tokens, from set_budget() or the deployment
    defaults VELARIS_ORG_BUDGET_USD / VELARIS_ORG_BUDGET_TOKENS. At 100% the call is refused with
    BudgetExceeded and the reason; at 80% a warning goes to the trace and the log, once a month.
  * A model whose price is unknown cannot be metered against a USD budget, so it is refused while
    an org has one (fail closed). Set its price in the catalogue (0 for a model you host yourself).

Limits of this version: the check is read-then-call, so calls already in flight when the budget runs
out can overshoot it by their own cost; and the plan a deployment sells is not known here, so the
default budget is an environment setting, not read from a plan.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from velaris.agentkit.state import JsonState, append_line
from velaris.core import access
from velaris.intel import catalogue, providers, trace
from velaris.intel.errors import BudgetExceeded
from velaris.intel.paths import agent_dir, write_private

logger = logging.getLogger("velaris.intel.usage")
ALERT_AT = 0.8
MAX_SCAN_LINES = 1_000_000
_ctx: contextvars.ContextVar[Dict[str, str]] = contextvars.ContextVar("velaris_usage_ctx", default={})


@contextlib.contextmanager
def usage_context(*, org: Optional[str] = None, agent: Optional[str] = None) -> Iterator[None]:
    """Calls inside the block are metered to this organisation and agent."""
    token = _ctx.set({**_ctx.get(), **{k: v for k, v in (("org", org), ("agent", agent)) if v}})
    try:
        yield
    finally:
        _ctx.reset(token)


def _month(ts: Optional[float] = None) -> str:
    return time.strftime("%Y%m", time.gmtime(ts or time.time()))


def current_org() -> str:
    who = access.current_caller()
    return _ctx.get().get("org") or (who.org if who else None) or access.deployment_org() or "default"


def _agent(purpose: str) -> str:
    return _ctx.get().get("agent") or (purpose.split(".")[0] if purpose else "unknown")


def _log_path(month: str) -> Path:
    return agent_dir("llm_usage") / f"usage-{month}.jsonl"


def _totals(month: str) -> JsonState:
    return JsonState("llm_usage", f"totals-{month}.json", {"orgs": {}}, version=1)


def _budgets() -> JsonState:
    return JsonState("llm_usage", "budgets.json", {"orgs": {}}, version=1)


# ── kill switch ──────────────────────────────────────────────────────────────

def _kill_file() -> Path:
    return Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris") / "llm.kill"


def kill_switch_on() -> bool:
    return os.environ.get("VELARIS_LLM_KILL_SWITCH", "").lower() in ("1", "true", "yes") or _kill_file().exists()


def set_kill_switch(on: bool, by: str = "") -> None:
    if on:
        write_private(_kill_file(), f"set by {by or 'unknown'} at {time.time()}")
    else:
        _kill_file().unlink(missing_ok=True)
    trace.append("usage", "kill_switch", {"on": on, "by": by})


# ── budgets ──────────────────────────────────────────────────────────────────

def set_budget(org: str, *, usd: Optional[float] = None, tokens: Optional[int] = None, by: str = "") -> None:
    for v in (usd, tokens):
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0):
            raise ValueError("a budget is a number of at least 0, or None for 'use the default'")
    _budgets().update(lambda d: d["orgs"].__setitem__(org, {"usd": usd, "tokens": tokens}))
    trace.append("usage", "budget.set", {"org": org, "usd": usd, "tokens": tokens, "by": by})


def budget_for(org: str) -> Dict[str, Optional[float]]:
    own = _budgets().load()["orgs"].get(org, {})
    env_usd, env_tok = os.environ.get("VELARIS_ORG_BUDGET_USD"), os.environ.get("VELARIS_ORG_BUDGET_TOKENS")
    return {"usd": own.get("usd") if own.get("usd") is not None else (float(env_usd) if env_usd else None),
            "tokens": own.get("tokens") if own.get("tokens") is not None else (int(env_tok) if env_tok else None)}


def _free_local(provider_id: str) -> bool:
    if provider_id == "ollama":
        return True
    p = providers.get(provider_id)
    return bool(p and p.kind == "ollama")


def month_totals(org: str, month: Optional[str] = None) -> Dict[str, Any]:
    blank = {"calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
             "unpriced_calls": 0, "alerted": False}
    return {**blank, **_totals(month or _month()).load()["orgs"].get(org, {})}


def check(model: str, *, org: Optional[str] = None) -> None:
    """Raise BudgetExceeded unless a call to `model` may be made now. Call it before every model call."""
    if kill_switch_on():
        raise BudgetExceeded("model calls are switched off (kill switch); nothing was sent")
    org = org or current_org()
    limit = budget_for(org)
    if limit["usd"] is None and limit["tokens"] is None:
        return
    used = month_totals(org)
    if limit["tokens"] is not None and used["tokens_in"] + used["tokens_out"] >= limit["tokens"]:
        raise BudgetExceeded(f"organisation '{org}' used its monthly token budget of {limit['tokens']:.0f}; "
                             "calls resume next month or when an admin raises it")
    if limit["usd"] is not None:
        provider = model.split(":")[0]
        priced = _free_local(provider) or catalogue.cost_estimate(model, 1, 1) is not None
        if not priced:
            raise BudgetExceeded(f"'{model}' has no price in the catalogue, so it cannot be counted against the "
                                 f"monthly budget of organisation '{org}'; set its price (0 if you host it)")
        if used["cost_usd"] >= limit["usd"]:
            raise BudgetExceeded(f"organisation '{org}' used its monthly budget of ${limit['usd']:.2f} "
                                 f"(${used['cost_usd']:.2f}); calls resume next month or when an admin raises it")


def estimate_tokens(chars: int) -> int:
    return math.ceil(chars / 4)


def record(*, model: str, purpose: str, sensitivity: str, status: str, seconds: float, prompt_chars: int = 0,
           output_chars: int = 0, usage: Optional[Dict[str, int]] = None, error: str = "",
           org: Optional[str] = None) -> Dict[str, Any]:
    """Append one usage record and update the totals. Raises if it cannot be written: unmetered spend is refused."""
    org = org or current_org()
    estimated = not usage
    t_in = usage["tokens_in"] if usage else estimate_tokens(prompt_chars)
    t_out = usage["tokens_out"] if usage else estimate_tokens(output_chars)
    cost = 0.0 if _free_local(model.split(":")[0]) else catalogue.cost_estimate(model, t_in, t_out)
    ts = time.time()
    row = {"ts": ts, "org": org, "agent": _agent(purpose), "action": purpose, "provider": model.split(":")[0],
           "model": model, "tokens_in": t_in, "tokens_out": t_out, "estimate": estimated,
           "latency_s": round(seconds, 3), "status": status, "error": error[:80], "cost_usd": cost,
           "sensitivity": sensitivity}
    append_line(_log_path(_month(ts)), row)

    def add(d: Dict[str, Any]) -> bool:
        t = d["orgs"].setdefault(org, {"calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                                       "unpriced_calls": 0, "alerted": False})
        t["calls"] += 1
        t["errors"] += status != "ok"
        t["tokens_in"] += t_in
        t["tokens_out"] += t_out
        t["cost_usd"] = round(t["cost_usd"] + (cost or 0.0), 8)
        t["unpriced_calls"] += cost is None
        limit = budget_for(org)
        near = (limit["usd"] and t["cost_usd"] >= ALERT_AT * limit["usd"]) or \
               (limit["tokens"] and t["tokens_in"] + t["tokens_out"] >= ALERT_AT * limit["tokens"])
        fire = bool(near and not t["alerted"])
        t["alerted"] = t["alerted"] or bool(near)
        return fire
    if _totals(_month(ts)).update(add):
        logger.warning("organisation %s passed %d%% of its monthly model budget", org, int(ALERT_AT * 100))
        trace.append("usage", "budget.alert", {"org": org, "at": ALERT_AT})
    return row


# ── summaries ────────────────────────────────────────────────────────────────

def _rows(month: str) -> Iterator[Dict[str, Any]]:
    path = _log_path(month)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for n, line in enumerate(f):
            if n >= MAX_SCAN_LINES:
                logger.warning("usage summary stopped at %d lines", MAX_SCAN_LINES)
                return
            try:
                yield json.loads(line)
            except ValueError:
                continue                                 # a torn last line


def summary(by: str = "org", *, month: Optional[str] = None, org: Optional[str] = None) -> List[Dict[str, Any]]:
    """Totals grouped by "day", "org", "agent" or "model" for one month (default: this one).
    `org` limits it to one organisation (what a signed-in admin of that organisation may see)."""
    if by not in ("day", "org", "agent", "model"):
        raise ValueError("by is one of day, org, agent, model")
    groups: Dict[str, Dict[str, Any]] = {}
    for r in _rows(month or _month()):
        if org and r["org"] != org:
            continue
        key = time.strftime("%Y-%m-%d", time.gmtime(r["ts"])) if by == "day" else r[by]
        g = groups.setdefault(key, {"key": key, "calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0,
                                    "cost_usd": 0.0, "unpriced_calls": 0, "estimated_calls": 0})
        g["calls"] += 1
        g["errors"] += r["status"] != "ok"
        g["tokens_in"] += r["tokens_in"]
        g["tokens_out"] += r["tokens_out"]
        g["cost_usd"] = round(g["cost_usd"] + (r["cost_usd"] or 0.0), 8)
        g["unpriced_calls"] += r["cost_usd"] is None
        g["estimated_calls"] += bool(r["estimate"])
    return sorted(groups.values(), key=lambda g: g["key"])



def daily(days: int = 7, *, org: Optional[str] = None) -> List[Dict[str, Any]]:
    """Per-day totals for the last `days` days (UTC, today included), oldest first, empty days as zeros.
    Reads this month's and last month's log, so it works across a month boundary."""
    days = max(1, min(days, 31))
    now = time.time()
    keys = [time.strftime("%Y-%m-%d", time.gmtime(now - 86400 * i)) for i in range(days - 1, -1, -1)]
    out = {k: {"day": k, "calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
               "unpriced_calls": 0} for k in keys}
    for month in sorted({k[:7].replace("-", "") for k in keys}):
        for g in summary("day", month=month, org=org):
            if g["key"] in out:
                out[g["key"]].update({k: g[k] for k in ("calls", "errors", "tokens_in", "tokens_out", "cost_usd",
                                                         "unpriced_calls")})
    return list(out.values())
