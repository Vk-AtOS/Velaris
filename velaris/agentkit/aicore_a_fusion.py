"""Field-level merge of records from several sources, shared by the ACF and CCSF agents.

A source is {"source": name, "data": {...}, "ts": number?}. Nested objects are
flattened to dotted field names. A field every reporting source agrees on goes
into `merged` with the list of sources that reported it; a field with more than
one distinct value goes into `conflicts` and is left out of `merged`, so a
disagreement is never settled by whichever source happened to come last.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Union

from velaris.agentkit.checks import ident, number


def flatten(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            flat.update(flatten(value, path + "."))
        else:
            flat[path] = value
    return flat


def clean_sources(sources: Any) -> Union[List[Dict[str, Any]], str]:
    """Validated sources with flattened data, or an error string."""
    if not isinstance(sources, list) or not sources:
        return "sources must be a non-empty list"
    out, seen = [], set()
    for src in sources:
        name = ident(src.get("source")) if isinstance(src, dict) else None
        if name is None or name in seen or not isinstance(src.get("data"), dict):
            return f"source {src!r} needs a unique 'source' name and a 'data' object"
        if not all(isinstance(k, str) for k in src["data"]):
            return f"source {name}: field names must be strings"
        ts = src.get("ts")
        if ts is not None and number(ts) is None:
            return f"source {name}: 'ts' must be a number"
        seen.add(name)
        out.append({"source": name, "data": flatten(src["data"]), "ts": ts})
    return out


def fuse(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge cleaned sources. Returns merged, provenance and conflicts."""
    merged: Dict[str, Any] = {}
    provenance: Dict[str, List[str]] = {}
    conflicts: List[Dict[str, Any]] = []
    for field in sorted({f for s in sources for f in s["data"]}):
        reports = [{"source": s["source"], "value": s["data"][field], "ts": s["ts"]}
                   for s in sources if field in s["data"]]
        distinct = {json.dumps(r["value"], sort_keys=True, default=str) for r in reports}
        if len(distinct) == 1:
            merged[field] = reports[0]["value"]
            provenance[field] = [r["source"] for r in reports]
        else:
            conflicts.append({"field": field, "values": reports})
    return {"merged": merged, "provenance": provenance, "conflicts": conflicts}
