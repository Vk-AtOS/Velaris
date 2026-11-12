"""ECON_INTEL_CORE: a sourced register of economic indicators, plus cited research.

  record_indicator  store one observation (name, period, value) with the URL it came from;
                    an observation without a source is refused
  series / summary  the stored observations and the latest change, computed in code
  research          a question answered from the web through velaris.intel.research,
                    every finding quote-checked; `not_configured` without a model

The agent holds no built-in economic data and never estimates a missing figure.
State: <VELARIS_DATA>/agents/ECON_INTEL_CORE/indicators.json (owner-only).
"""
import logging
import re
from typing import Any, Callable, Dict, Optional

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_outside

logger = logging.getLogger("ECON_INTEL_CORE")
_PERIOD = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]|Q[1-4]))?$")     # 2026, 2026-09, 2026-Q2
MAX_PER_SERIES = 2000


class ECON_INTEL_COREAgent:
    def __init__(self, name="ECON_INTEL_CORE"):
        self.name = name
        self._state = kit.JsonState("ECON_INTEL_CORE", "indicators.json", {"series": {}})

    def health_check(self):
        return kit.health(self.name)

    def record_indicator(self, name: Any, period: Any, value: Any, source_url: Any, unit: str = "") -> Dict[str, Any]:
        errors = []
        key = kit.ident(name, 80)
        if key is None:
            errors.append("name must be a non-empty string")
        if not isinstance(period, str) or not _PERIOD.match(period):
            errors.append("period must look like 2026, 2026-09 or 2026-Q2")
        if kit.number(value) is None:
            errors.append("value must be a finite number")
        url = kit.ident(source_url, 500)
        if url is None or not url.startswith(("http://", "https://")):
            errors.append("source_url must be the http(s) address the figure was read from")
        if not isinstance(unit, str) or len(unit) > 40:
            errors.append("unit must be a short string")
        if errors:
            return kit.failed(errors)
        data = self._state.load()
        series = data["series"].setdefault(key.lower(), {})
        if period not in series and len(series) >= MAX_PER_SERIES:
            return kit.failed([f"series is full ({MAX_PER_SERIES} observations)"])
        replaced = period in series
        series[period] = {"value": float(value), "source_url": url, "unit": unit}
        self._state.save(data)
        return {"status": "ok", "name": key.lower(), "period": period, "replaced": replaced}

    def series(self, name: Any) -> Dict[str, Any]:
        key = kit.ident(name, 80)
        if key is None:
            return kit.failed(["name must be a non-empty string"])
        rows = self._state.load()["series"].get(key.lower(), {})
        if not rows:
            return kit.needs_data(f"no observations recorded for '{key.lower()}'", observations=[])
        # periods of one granularity sort correctly as text; mixed granularities are the caller's choice
        return {"status": "ok", "name": key.lower(),
                "observations": [{"period": p, **rows[p]} for p in sorted(rows)]}

    def summary(self, name: Any) -> Dict[str, Any]:
        """Latest observation and its change from the one before."""
        got = self.series(name)
        if got["status"] != "ok":
            return got
        obs = got["observations"]
        latest, previous = obs[-1], obs[-2] if len(obs) > 1 else None
        change = None if previous is None else round(latest["value"] - previous["value"], 6)
        pct = (None if previous is None or previous["value"] == 0
               else round(change / abs(previous["value"]) * 100, 4))
        return {"status": "ok", "name": got["name"], "latest": latest, "previous": previous,
                "change": change, "change_pct": pct, "observations": len(obs),
                "sources": sorted({o["source_url"] for o in obs[-2:]})}

    def research(self, question: Any, llm: Any = None, search_fn: Optional[Callable] = None,
                 fetcher: Any = None, **limits: int) -> Dict[str, Any]:
        return biz_outside.cited_research(
            question, llm=llm, search_fn=search_fn, fetcher=fetcher,
            scope_note="Economic conditions relevant to a small IT services company in India.", **limits)
